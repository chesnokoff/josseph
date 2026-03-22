"""Clone repositories and run metric analyses."""
from __future__ import annotations

import json
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from josseph.utils import run_command, ROOT, PROJECTS_DIR, setup_logging, RESULTS_DIR
from josseph.metrics.extractor import ExtractorConfig, MetricExtractor
from josseph.metrics.registry import ExtractorRegistry


def sanitize_repo_name(repo_url: str) -> str:
    """Convert a repository URL to <owner>@<repo>."""
    parsed = urlparse(repo_url.strip())

    path = parsed.path.strip("/")

    if path.endswith(".git"):
        path = path[: -len(".git")]

    parts = [p for p in path.split("/") if p]

    owner, repo = parts
    return f"{owner}@{repo}"


@dataclass(frozen=True)
class AnalysisConfig:
    repos_file: Path
    clone_depth: str | None
    tools: list[str] | None
    github_token: str | None
    workers: int


def build_config(args) -> AnalysisConfig:
    return AnalysisConfig(
        repos_file=Path(args.repos_file),
        clone_depth=args.clone_depth,
        tools=args.tools,
        github_token=args.github_token or os.environ.get("GITHUB_TOKEN"),
        workers=args.workers,
    )


def select_extractors(registry: ExtractorRegistry, tools, cfg) -> dict[str, MetricExtractor]:
    if not tools:
        return registry.create_all(cfg)

    available = set(registry.names())
    extractors = {}
    for name in tools:
        if name in available:
            extractors[name] = registry.get(name, cfg)

    return extractors


class RepositoryCloner:
    def __init__(self, projects_dir: Path) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._projects_dir = projects_dir

    def clone(self, repo_url: str, clone_depth: str | None) -> Path:
        project_name = sanitize_repo_name(repo_url)
        target = self._projects_dir / project_name
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        self.log.info("Cloning %s -> %s", repo_url, target)
        cmd = ["git", "clone", repo_url, str(target)]
        if clone_depth:
            cmd[2:2] = ["--depth", clone_depth]

        self.log.trace(run_command(cmd))
        self.log.info("Finished cloning %s", repo_url)
        return target

    def cleanup(self, repo_path: Path) -> None:
        shutil.rmtree(repo_path, ignore_errors=True)


class ResultDirectoryManager:
    def __init__(self, results_dir: Path) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._results_dir = results_dir

    def prepare(self, project_name: str) -> Path:
        result_dir = self._results_dir / project_name
        result_dir.mkdir(parents=True, exist_ok=True)
        return result_dir

    def _result_base_path(self, project_name: str, tool_name: str) -> Path:
        return self._results_dir / project_name / tool_name

    def has_result(self, project_name: str, tool_name: str) -> bool:
        base = self._result_base_path(project_name, tool_name)
        return any(p.is_file() for p in base.parent.glob(base.name + ".*"))


class ResultWriter:
    def __init__(self) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def write(self, path: Path, tool_name: str, rows: list[dict], commit_hash: str) -> None:
        path.mkdir(parents=True, exist_ok=True)

        out = path / f"{tool_name}.parquet"
        df = pd.DataFrame(rows)
        df.to_parquet(out, index=False, engine="pyarrow", compression="zstd")
        metadata_path = path / f"{tool_name}.json"
        metadata_path.write_text(json.dumps({"commit_hash": commit_hash}, indent=2) + "\n")


@contextmanager
def cloned_repository(cloner: RepositoryCloner, repo_url: str, clone_depth: str | None):
    repo_path = cloner.clone(repo_url, clone_depth)
    try:
        yield repo_path
    finally:
        cloner.cleanup(repo_path)


class RepositoryAnalyzer:
    def __init__(
        self,
        cloner: RepositoryCloner,
        result_manager: ResultDirectoryManager,
        result_writer: ResultWriter,
        extractors,
    ) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        self._cloner = cloner
        self._result_manager = result_manager
        self._result_writer = result_writer
        self._extractors = extractors
        self.log.debug("Initializing repository analysis pipeline: %s", extractors.keys())

    def analyze(self, repo_url: str, clone_depth: str | None) -> None:
        project_name = sanitize_repo_name(repo_url)
        result_dir = self._result_manager.prepare(project_name)
        pending_extractors = {}
        for extractor_name, extractor in self._extractors.items():
            if not self._result_manager.has_result(project_name, extractor_name):
                pending_extractors[extractor_name]= extractor
            else:
                self.log.info(
                    "Metrics already present for %s with %s extractor. Skipping.",
                    project_name,
                    extractor_name,
                )

        self.log.info("Starting analysis of %s", project_name)

        with cloned_repository(self._cloner, repo_url, clone_depth) as project_dir:
            commit_hash = self.log.trace(run_command(["git", "rev-parse", "HEAD"], cwd=project_dir))
            for extractor_name, extractor in pending_extractors.items():
                try:
                    rows = extractor.run(project_dir, project_name)
                except Exception as exc:
                    self.log.warning(f"Analysis of {project_name} with '{extractor_name}' extractor failed. Skipping. Reason: {exc}")
                    continue
                self._result_writer.write(result_dir, extractor_name, rows, commit_hash)

        self.log.info("Successfully finished analysis of %s", project_name)


class AnalysisRunner:
    def __init__(self) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def run(self, repos, analyzer: RepositoryAnalyzer, clone_depth: str | None, workers: int, ) -> int:
        max_workers = min(workers, len(repos))
        failures = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyzer.analyze, repo, clone_depth): repo
                for repo in repos
            }
            for future in as_completed(futures):
                repo = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    failures += 1
                    self.log.warning("Failed to analyse %s: %s", repo, exc)
        return failures


class RepositoryAnalysisPipeline:
    def __init__(self) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def _read_repositories(self, path: Path) -> list[str]:
        """Load repository URLs from a file, skipping comments and blanks."""

        if not path.exists():
            raise FileNotFoundError(f"Repository list {path} not found")

        repos = []
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            repos.append(line)
        return repos

    def run(self, args) -> None:
        setup_logging()

        config = build_config(args)
        registry = ExtractorRegistry()
        env = dict(os.environ)
        if config.github_token:
            env["GITHUB_TOKEN"] = config.github_token
        extractor_cfg = ExtractorConfig(tools_path=ROOT / "tools", env=env)
        extractors = select_extractors(registry, config.tools, extractor_cfg)
        repos = self._read_repositories(config.repos_file)

        if not repos:
            self.log.info("No repositories to process.")
            return

        if config.workers < 1:
            raise ValueError("--workers must be a positive integer")

        analyzer = RepositoryAnalyzer(
            cloner=RepositoryCloner(PROJECTS_DIR),
            result_manager=ResultDirectoryManager(RESULTS_DIR),
            result_writer=ResultWriter(),
            extractors=extractors,
        )

        failures = AnalysisRunner().run(repos, analyzer, config.clone_depth, config.workers)
        if failures:
            self.log.error("%s repositories failed to analyse. See logs above for details.", failures)
