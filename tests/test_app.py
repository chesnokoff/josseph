from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest

from josseph.pipeline.app import RepositoryAnalysisPipeline
from josseph.utils import AnalysisError


class SuccessfulExtractor:
    requires_checkout = False
    metric_binding = "observation-bound"

    def __init__(self, rows):
        self._rows = rows

    def run(self, target):
        return list(self._rows)


class FailingExtractor:
    requires_checkout = False

    def __init__(self, exc):
        self._exc = exc

    def run(self, target):
        raise self._exc


def write_config(tmp_path, *, tools: list[str] | None = None) -> Namespace:
    repos_file = tmp_path / "repos.yaml"
    repos_file.write_text("- https://github.com/example/repo.git\n", encoding="utf-8")
    config_lines = ["repositories: repos.yaml", "workers: 2"]
    if tools is not None:
        config_lines.append("tools:")
        config_lines.extend(f"  - {tool_name}" for tool_name in tools)
    config_file = tmp_path / "config.yaml"
    config_file.write_text("\n".join(config_lines) + "\n", encoding="utf-8")
    return Namespace(config_path=str(config_file))


def latest_summary(results_dir):
    run_dirs = sorted((results_dir / "runs").iterdir())
    return run_dirs[-1] / "summary.json"


def test_pipeline_run_persists_results_and_summary_for_successful_run(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    monkeypatch.setattr("josseph.pipeline.app.RESULTS_DIR", results_dir)
    monkeypatch.setattr("josseph.pipeline.app.PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr("josseph.pipeline.app.THIRD_PARTY_DIR", tmp_path / "third_party")
    monkeypatch.setattr("josseph.pipeline.app.setup_logging", lambda: None)
    monkeypatch.setattr(
        "josseph.pipeline.app.select_extractors",
        lambda registry, tools: {
            "github": SuccessfulExtractor([{"stars": 42, "language": "Java"}]),
        },
    )

    exit_code = RepositoryAnalysisPipeline().run(write_config(tmp_path, tools=["github"]))

    assert exit_code == 0
    summary_path = latest_summary(results_dir)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "success"
    assert summary["exit_code"] == 0
    assert summary["summary"]["repository_count"] == 1
    assert summary["summary"]["failed_run_count"] == 0
    assert summary["config"]["repositories"] == [
        {
            "repo_url": "https://github.com/example/repo.git",
            "requested_commit_hash": None,
        }
    ]

    project_dir = results_dir / "example@repo"
    assert pd.read_parquet(project_dir / "github.parquet").to_dict(orient="records") == [
        {"stars": 42, "language": "Java"}
    ]
    metadata = json.loads((project_dir / "github.json").read_text(encoding="utf-8"))
    assert metadata["commit_hash"] == ""
    assert metadata["requested_commit_hash"] is None
    assert metadata["metric_binding"] == "observation-bound"
    assert metadata["collected_at_utc"].endswith("Z")


def test_pipeline_run_records_partial_extractor_failure_in_summary(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    monkeypatch.setattr("josseph.pipeline.app.RESULTS_DIR", results_dir)
    monkeypatch.setattr("josseph.pipeline.app.PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr("josseph.pipeline.app.THIRD_PARTY_DIR", tmp_path / "third_party")
    monkeypatch.setattr("josseph.pipeline.app.setup_logging", lambda: None)
    monkeypatch.setattr(
        "josseph.pipeline.app.select_extractors",
        lambda registry, tools: {
            "github": SuccessfulExtractor([{"stars": 7}]),
            "sonar": FailingExtractor(AnalysisError("scanner unavailable")),
        },
    )

    exit_code = RepositoryAnalysisPipeline().run(
        write_config(tmp_path, tools=["github", "sonar"])
    )

    summary = json.loads(latest_summary(results_dir).read_text(encoding="utf-8"))
    assert exit_code == summary["exit_code"]
    assert summary["summary"]["extractor_failure_count"] == 1
    assert summary["summary"]["failed_run_count"] == 1
    assert summary["extractor_failures"][0]["extractor"] == "sonar"
    assert (results_dir / "example@repo" / "github.parquet").is_file()


def test_pipeline_fails_on_invalid_config(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    config_file = tmp_path / "config.yaml"
    config_file.write_text("repositories: [broken\n", encoding="utf-8")

    monkeypatch.setattr("josseph.pipeline.app.RESULTS_DIR", results_dir)
    monkeypatch.setattr("josseph.pipeline.app.setup_logging", lambda: None)

    exit_code = RepositoryAnalysisPipeline().run(Namespace(config_path=str(config_file)))

    assert exit_code == 2
    assert not (results_dir / "runs").exists()


def test_pipeline_returns_invalid_input_exit_code_when_tool_jar_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results_dir = tmp_path / "results"
    empty_third_party = tmp_path / "third_party"
    empty_third_party.mkdir()
    monkeypatch.setattr("josseph.pipeline.app.RESULTS_DIR", results_dir)
    monkeypatch.setattr("josseph.pipeline.app.PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr("josseph.pipeline.app.THIRD_PARTY_DIR", empty_third_party)
    monkeypatch.setattr("josseph.pipeline.app.setup_logging", lambda: None)

    exit_code = RepositoryAnalysisPipeline().run(write_config(tmp_path, tools=["ck"]))

    assert exit_code == 2
    summary = json.loads(latest_summary(results_dir).read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["exit_code"] == 2


def test_pipeline_writes_failed_summary_when_runtime_preparation_fails(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    monkeypatch.setattr("josseph.pipeline.app.RESULTS_DIR", results_dir)
    monkeypatch.setattr("josseph.pipeline.app.PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr("josseph.pipeline.app.THIRD_PARTY_DIR", tmp_path / "third_party")
    monkeypatch.setattr("josseph.pipeline.app.setup_logging", lambda: None)

    def fail_to_select_extractors(registry, tools):
        raise ValueError("unknown tool requested")

    monkeypatch.setattr("josseph.pipeline.app.select_extractors", fail_to_select_extractors)

    exit_code = RepositoryAnalysisPipeline().run(write_config(tmp_path, tools=["github"]))

    assert exit_code == 2
    summary = json.loads(latest_summary(results_dir).read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["exit_code"] == 2
    assert summary["summary"]["failed_run_count"] == 0
