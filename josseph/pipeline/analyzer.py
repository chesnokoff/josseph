"""Repository-level analysis orchestration."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from josseph.domain.repository import AnalysisTarget, RepositoryRef
from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.pipeline.cloner import RepositoryCloner, cloned_repository
from josseph.process import CommandExecutionError, CommandRunner
from josseph.pipeline.run_report import RunReportCollector
from josseph.pipeline.results import ResultDirectoryManager, ResultWriter
from josseph.utils import AnalysisError


class RepositoryAnalysisError(RuntimeError):
    """Raised when a repository-level failure should be reported for the run."""


class RepositoryAnalyzer:
    def __init__(
        self,
        cloner: RepositoryCloner,
        result_manager: ResultDirectoryManager,
        result_writer: ResultWriter,
        extractors: dict[str, MetricExtractor],
        command_runner: CommandRunner,
        run_reporter: RunReportCollector | None = None,
        force: bool = False,
    ) -> None:
        self.log = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self._cloner = cloner
        self._result_manager = result_manager
        self._result_writer = result_writer
        self._extractors = extractors
        self._command_runner = command_runner
        self._run_reporter = run_reporter
        self._force = force
        self.log.debug(
            "Initializing repository analysis pipeline: %s", extractors.keys()
        )

    def analyze(self, repo_url: str, clone_depth: int | None) -> None:
        target = AnalysisTarget(repository=RepositoryRef.parse(repo_url))
        result_dir = self._result_manager.prepare(target.project_name)
        pending_extractors = self._get_pending_extractors(target)
        if not pending_extractors:
            self.log.info(
                "All metrics already collected for %s. Skipping clone and analysis.",
                target.project_name,
            )
            return

        checkout_required, checkout_not_required = self._split_by_checkout_requirement(
            pending_extractors
        )
        self._run_extractors(
            checkout_not_required,
            target,
            result_dir,
            failure_template=(
                "Analysis of %s with '%s' extractor failed (no checkout path). "
                "Skipping. Reason: %s"
            ),
        )
        if not checkout_required:
            self.log.info(
                "Finished analysis of %s without repository checkout.", target.project_name
            )
            return

        self.log.info("Starting analysis of %s", target.project_name)
        try:
            self._run_checkout_extractors(checkout_required, target, result_dir, clone_depth)
        except RepositoryAnalysisError:
            raise
        except Exception as exc:
            raise RepositoryAnalysisError(
                f"Analysis of {target.project_name} failed for {target.repository.raw}: {exc}"
            ) from exc
        self.log.info("Successfully finished analysis of %s", target.project_name)

    def _get_pending_extractors(self, target: AnalysisTarget) -> dict[str, MetricExtractor]:
        pending: dict[str, MetricExtractor] = {}
        project_name = target.project_name
        for extractor_name, extractor in self._extractors.items():
            if not self._force and self._result_manager.has_result(project_name, extractor_name):
                self.log.info(
                    "Metrics already present for %s with %s extractor. Skipping.",
                    project_name,
                    extractor_name,
                )
                if self._run_reporter is not None:
                    self._run_reporter.record_skipped_run(
                        repo_url=target.repository.raw,
                        project_name=project_name,
                        extractor_name=extractor_name,
                        reason="cached_result",
                    )
                continue
            pending[extractor_name] = extractor
        return pending

    def _split_by_checkout_requirement(
        self,
        extractors: dict[str, MetricExtractor],
    ) -> tuple[dict[str, MetricExtractor], dict[str, MetricExtractor]]:
        checkout_required: dict[str, MetricExtractor] = {}
        checkout_not_required: dict[str, MetricExtractor] = {}
        for extractor_name, extractor in extractors.items():
            if extractor.requires_checkout:
                checkout_required[extractor_name] = extractor
            else:
                checkout_not_required[extractor_name] = extractor
        return checkout_required, checkout_not_required

    def _run_checkout_extractors(
        self,
        extractors: dict[str, MetricExtractor],
        target: AnalysisTarget,
        result_dir: Path,
        clone_depth: int | None,
    ) -> None:
        try:
            with cloned_repository(
                self._cloner,
                target.repository.raw,
                clone_depth,
            ) as project_dir:
                commit_hash = self._resolve_commit_hash(project_dir, target)
                checkout_target = target.with_checkout(
                    checkout_path=project_dir,
                    commit_hash=commit_hash,
                )
                self._run_extractors(
                    extractors,
                    checkout_target,
                    result_dir,
                    failure_template=(
                        "Analysis of %s with '%s' extractor failed. Skipping. Reason: %s"
                    ),
                )
        except RepositoryAnalysisError:
            raise
        except Exception as exc:
            raise RepositoryAnalysisError(
                f"Analysis of {target.project_name} failed while using a checkout for "
                f"{target.repository.raw}: {exc}"
            ) from exc

    def _resolve_commit_hash(self, project_dir: Path, target: AnalysisTarget) -> str:
        try:
            commit_hash = self._command_runner.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_dir,
            ).strip()
        except (CommandExecutionError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise RepositoryAnalysisError(
                f"Unable to resolve HEAD for {target.project_name} at {project_dir}: {exc}"
            ) from exc
        self.log.trace("Resolved HEAD commit hash %s for %s", commit_hash, project_dir)
        return commit_hash

    def _run_extractors(
        self,
        extractors: dict[str, MetricExtractor],
        target: AnalysisTarget,
        result_dir: Path,
        *,
        failure_template: str,
    ) -> None:
        for extractor_name, extractor in extractors.items():
            try:
                rows = extractor.run(target)
            except (
                AnalysisError,
                CommandExecutionError,
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
            ) as exc:
                failure_reason = self._describe_failure(exc)
                self.log.warning(
                    failure_template,
                    target.project_name,
                    extractor_name,
                    failure_reason,
                )
                if self._run_reporter is not None:
                    self._run_reporter.record_extractor_failure(
                        repo_url=target.repository.raw,
                        project_name=target.project_name,
                        extractor_name=extractor_name,
                        reason=failure_reason,
                    )
                continue
            self._result_writer.write(
                result_dir,
                extractor_name,
                rows,
                commit_hash=target.commit_hash or "",
            )

    @staticmethod
    def _describe_failure(exc: Exception) -> str:
        if isinstance(exc, CommandExecutionError):
            return str(exc)
        return f"{exc.__class__.__name__}: {exc}"
