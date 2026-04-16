"""Pipeline-level run reporting."""
from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from josseph.domain.repository import RepositoryRef
from josseph.pipeline.config import AnalysisConfig


def _format_utc(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


@dataclass(frozen=True)
class RunArtifacts:
    run_dir: Path
    summary_path: Path


class RunReportCollector:
    def __init__(
        self,
        *,
        config: AnalysisConfig,
        results_dir: Path,
        started_at: datetime | None = None,
    ) -> None:
        self._lock = Lock()
        self._config = config
        self._started_at = (started_at or datetime.now(UTC)).astimezone(UTC)
        self._run_id = self._started_at.strftime("%Y%m%dT%H%M%SZ")
        self._artifacts = self._prepare_artifacts(results_dir)
        self._skipped_runs: list[dict[str, object]] = []
        self._failed_runs: list[dict[str, object]] = []

    @property
    def artifacts(self) -> RunArtifacts:
        return self._artifacts

    def record_skipped_run(
        self,
        *,
        repo_url: str,
        project_name: str,
        extractor_name: str,
        requested_commit_hash: str | None,
        metric_binding: str,
        reason: str,
    ) -> None:
        self._record_event(
            self._skipped_runs,
            {
                "scope": "extractor",
                "repo_url": repo_url,
                "project_name": project_name,
                "extractor": extractor_name,
                "requested_commit_hash": requested_commit_hash,
                "metric_binding": metric_binding,
                "reason": reason,
            },
        )

    def record_extractor_failure(
        self,
        *,
        repo_url: str,
        project_name: str,
        extractor_name: str,
        requested_commit_hash: str | None,
        metric_binding: str,
        reason: str,
    ) -> None:
        self._record_event(
            self._failed_runs,
            {
                "scope": "extractor",
                "repo_url": repo_url,
                "project_name": project_name,
                "extractor": extractor_name,
                "requested_commit_hash": requested_commit_hash,
                "metric_binding": metric_binding,
                "reason": reason,
            },
        )

    def record_repository_failure(
        self,
        *,
        repo_url: str,
        requested_commit_hash: str | None,
        reason: str,
    ) -> None:
        project_name: str | None = None
        with suppress(Exception):
            project_name = RepositoryRef.parse(repo_url).project_name
        self._record_event(
            self._failed_runs,
            {
                "scope": "repository",
                "repo_url": repo_url,
                "project_name": project_name,
                "requested_commit_hash": requested_commit_hash,
                "reason": reason,
            },
        )

    def write_summary(self, *, finished_at: datetime | None = None, exit_code: int) -> Path:
        finished = (finished_at or datetime.now(UTC)).astimezone(UTC)
        duration_seconds = round((finished - self._started_at).total_seconds(), 3)
        repository_failures = [
            event for event in self._failed_runs if event.get("scope") == "repository"
        ]
        extractor_failures = [
            event for event in self._failed_runs if event.get("scope") == "extractor"
        ]
        affected_repositories = {
            event["repo_url"]
            for event in [*self._skipped_runs, *self._failed_runs]
            if "repo_url" in event
        }

        payload = {
            "run_id": self._run_id,
            "status": "success" if exit_code == 0 else "failed",
            "started_at_utc": _format_utc(self._started_at),
            "finished_at_utc": _format_utc(finished),
            "duration_seconds": duration_seconds,
            "exit_code": exit_code,
            "config": self._config.to_report_dict(),
            "summary": {
                "repository_count": len(self._config.repositories),
                "affected_repository_count": len(affected_repositories),
                "repository_failure_count": len(repository_failures),
                "extractor_failure_count": len(extractor_failures),
                "failed_run_count": len(self._failed_runs),
                "skipped_run_count": len(self._skipped_runs),
            },
            "repository_failures": repository_failures,
            "extractor_failures": extractor_failures,
            "failed_runs": list(self._failed_runs),
            "skipped_runs": list(self._skipped_runs),
        }
        self._artifacts.summary_path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        return self._artifacts.summary_path

    def _prepare_artifacts(self, results_dir: Path) -> RunArtifacts:
        run_dir = results_dir / "runs" / self._run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return RunArtifacts(
            run_dir=run_dir,
            summary_path=run_dir / "summary.json",
        )

    def _record_event(self, target: list[dict[str, object]], event: dict[str, object]) -> None:
        with self._lock:
            target.append(
                {
                    **event,
                    "recorded_at_utc": _format_utc(datetime.now(UTC)),
                }
            )
