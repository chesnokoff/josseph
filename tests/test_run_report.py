from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from josseph.domain.repository import RepositorySpec
from josseph.pipeline.config import AnalysisConfig
from josseph.pipeline.run_report import RunReportCollector


def make_config(tmp_path) -> AnalysisConfig:
    return AnalysisConfig(
        config_path=tmp_path / "config.yaml",
        repositories=[
            RepositorySpec.from_url(
                "https://github.com/example/repo.git",
                requested_commit_hash="deadbeefcafebabe",
            )
        ],
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
        requested_commit_hash="deadbeefcafebabe",
        metric_binding="observation-bound",
        reason="cached_result",
    )
    collector.record_extractor_failure(
        repo_url="https://github.com/example/repo.git",
        project_name="example@repo",
        extractor_name="sonar",
        requested_commit_hash="deadbeefcafebabe",
        metric_binding="revision-bound",
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
    assert payload["config"]["repositories"] == [
        {
            "repo_url": "https://github.com/example/repo.git",
            "requested_commit_hash": "deadbeefcafebabe",
        }
    ]
    assert payload["summary"]["failed_run_count"] == 1
    assert payload["summary"]["skipped_run_count"] == 1


def test_run_report_records_repository_failures(tmp_path):
    started_at = datetime(2026, 3, 22, 15, 0, 0, tzinfo=timezone.utc)
    collector = RunReportCollector(
        config=make_config(tmp_path),
        results_dir=tmp_path / "results",
        started_at=started_at,
    )

    collector.record_repository_failure(
        repo_url="https://github.com/example/repo.git",
        requested_commit_hash="deadbeefcafebabe",
        reason="clone failed",
    )
    collector.record_extractor_failure(
        repo_url="https://github.com/example/repo.git",
        project_name="example@repo",
        extractor_name="github",
        requested_commit_hash="deadbeefcafebabe",
        metric_binding="observation-bound",
        reason="api failed",
    )

    summary_path = collector.write_summary(
        finished_at=started_at + timedelta(seconds=1),
        exit_code=1,
    )

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["summary"] == {
        "repository_count": 1,
        "affected_repository_count": 1,
        "repository_failure_count": 1,
        "extractor_failure_count": 1,
        "failed_run_count": 2,
        "skipped_run_count": 0,
    }
    assert payload["repository_failures"] == [
        {
            "scope": "repository",
            "repo_url": "https://github.com/example/repo.git",
            "project_name": "example@repo",
            "requested_commit_hash": "deadbeefcafebabe",
            "reason": "clone failed",
            "recorded_at_utc": payload["repository_failures"][0]["recorded_at_utc"],
        }
    ]
    assert payload["failed_runs"][0]["scope"] == "repository"
    assert payload["failed_runs"][0]["repo_url"] == "https://github.com/example/repo.git"
    assert payload["failed_runs"][0]["requested_commit_hash"] == "deadbeefcafebabe"
    assert payload["failed_runs"][0]["reason"] == "clone failed"
    assert payload["failed_runs"][1]["scope"] == "extractor"
    assert payload["failed_runs"][1]["extractor"] == "github"
    assert payload["failed_runs"][1]["metric_binding"] == "observation-bound"
