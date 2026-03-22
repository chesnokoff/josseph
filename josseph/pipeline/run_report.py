"""Pipeline-level run reporting."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from josseph.pipeline.config import AnalysisConfig


def _format_utc(timestamp: datetime) -> str:
    return timestamp.astimezone(timezone.utc).replace(microsecond=0).strftime(
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
        self._started_at = (started_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
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
        reason: str,
    ) -> None:
        self._record_event(
            self._skipped_runs,
            {
                "scope": "extractor",
                "repo_url": repo_url,
                "project_name": project_name,
                "extractor": extractor_name,
                "reason": reason,
            },
        )

    def record_extractor_failure(
        self,
        *,
        repo_url: str,
        project_name: str,
        extractor_name: str,
        reason: str,
    ) -> None:
        self._record_event(
            self._failed_runs,
            {
                "scope": "extractor",
                "repo_url": repo_url,
                "project_name": project_name,
                "extractor": extractor_name,
                "reason": reason,
            },
        )

    def record_repository_failure(self, *, repo_url: str, reason: str) -> None:
        self._record_event(
            self._failed_runs,
            {
                "scope": "repository",
                "repo_url": repo_url,
                "reason": reason,
            },
        )

    def write_summary(self, *, finished_at: datetime | None = None, exit_code: int) -> Path:
        finished = (finished_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        duration_seconds = round((finished - self._started_at).total_seconds(), 3)

        payload = {
            "run_id": self._run_id,
            "started_at_utc": _format_utc(self._started_at),
            "finished_at_utc": _format_utc(finished),
            "duration_seconds": duration_seconds,
            "exit_code": exit_code,
            "config": self._config.to_report_dict(),
            "summary": {
                "repository_count": len(self._config.repositories),
                "failed_run_count": len(self._failed_runs),
                "skipped_run_count": len(self._skipped_runs),
            },
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
                    "recorded_at_utc": _format_utc(datetime.now(timezone.utc)),
                }
            )
