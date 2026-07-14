import json

import pandas as pd

from josseph.utils import ROOT

PINNED_COMMIT = "300468b1efd48d76fac2f7bd6d576846dcbbf5ed"


def test_checked_in_sample_matches_quickstart_contract() -> None:
    sample_dir = ROOT / "examples" / "sample-run"
    repository_dir = sample_dir / "junit-team@junit4"

    assert {path.name for path in repository_dir.iterdir()} == {
        "ck.json",
        "ck.parquet",
        "cm.json",
        "cm.parquet",
    }

    for tool in ("ck", "cm"):
        metadata = json.loads((repository_dir / f"{tool}.json").read_text(encoding="utf-8"))
        assert metadata["commit_hash"] == PINNED_COMMIT
        assert metadata["requested_commit_hash"] == PINNED_COMMIT
        assert metadata["metric_binding"] == "revision-bound"
        assert not pd.read_parquet(repository_dir / f"{tool}.parquet").empty

    summaries = list((sample_dir / "runs").glob("*/summary.json"))
    assert len(summaries) == 1
    summary = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert summary["status"] == "success"
    assert summary["exit_code"] == 0
    assert summary["config"]["tools"] == ["ck", "cm"]
    assert summary["config"]["github_token"] is None
    assert summary["config"]["repositories"] == [
        {
            "repo_url": "https://github.com/junit-team/junit4.git",
            "requested_commit_hash": PINNED_COMMIT,
        }
    ]
    assert summary["summary"] == {
        "repository_count": 1,
        "affected_repository_count": 0,
        "repository_failure_count": 0,
        "extractor_failure_count": 0,
        "failed_run_count": 0,
        "skipped_run_count": 0,
    }
