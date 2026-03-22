from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from josseph.pipeline.config import AnalysisConfig
from josseph.pipeline.run_report import RunReportCollector


def make_config(tmp_path) -> AnalysisConfig:
    return AnalysisConfig(
        config_path=tmp_path / "config.yaml",
        repositories=["https://github.com/example/repo.git"],
        clone_depth=1,
        tools=["github"],
        extractor_settings={"github": {"token": "secret-token"}},
        github_token="secret-token",
        workers=2,
    )


def test_run_report_writes_summary(tmp_path):
    started_at = datetime(2026, 3, 22, 15, 0, 0, tzinfo=timezone.utc)
    collector = RunReportCollector(
        config=make_config(tmp_path),
        results_dir=tmp_path / "results",
        started_at=started_at,
    )

    collector.record_skipped_run(
        repo_url="https://github.com/example/repo.git",
        project_name="example@repo",
        extractor_name="github",
        reason="cached_result",
    )
    collector.record_extractor_failure(
        repo_url="https://github.com/example/repo.git",
        project_name="example@repo",
        extractor_name="sonar",
        reason="scanner failed",
    )

    summary_path = collector.write_summary(
        finished_at=started_at + timedelta(seconds=12),
        exit_code=1,
    )

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["started_at_utc"] == "2026-03-22T15:00:00Z"
    assert payload["finished_at_utc"] == "2026-03-22T15:00:12Z"
    assert payload["duration_seconds"] == 12.0
    assert payload["config"]["github_token"] == "***redacted***"
    assert payload["summary"]["failed_run_count"] == 1
    assert payload["summary"]["skipped_run_count"] == 1
