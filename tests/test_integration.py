"""Integration test: clone a real public repository and assert artifacts exist."""
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest

from josseph.pipeline.app import RepositoryAnalysisPipeline
from josseph.utils import THIRD_PARTY_DIR

REAL_REPOSITORY = "https://github.com/junit-team/junit4.git"
REAL_COMMIT = "300468b1efd48d76fac2f7bd6d576846dcbbf5ed"


class ObservationExtractor:
    requires_checkout = False
    metric_binding = "observation-bound"

    def run(self, target):
        return [{"repo_slug": target.repo_slug, "project_name": target.project_name}]


class CheckoutExtractor:
    requires_checkout = True
    metric_binding = "revision-bound"

    def run(self, target):
        assert target.checkout_path is not None
        assert target.checkout_path.exists()
        assert target.commit_hash
        return [{"project_name": target.project_name, "checkout_exists": True}]


def _write_config(tmp_path) -> Namespace:
    repos_file = tmp_path / "repos.yaml"
    repos_file.write_text(
        f"- url: {REAL_REPOSITORY}\n  commit: {REAL_COMMIT}\n",
        encoding="utf-8",
    )

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "repositories: repos.yaml",
                "workers: 1",
                "tools:",
                "  - github",
                "  - ck",
                "  - cm",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return Namespace(config_path=str(config_file), force=True)


@pytest.mark.integration
def test_pipeline_clones_real_public_repository_and_writes_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results_dir = tmp_path / "results"
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr("josseph.pipeline.app.RESULTS_DIR", results_dir)
    monkeypatch.setattr("josseph.pipeline.app.PROJECTS_DIR", projects_dir)
    monkeypatch.setattr("josseph.pipeline.app.THIRD_PARTY_DIR", THIRD_PARTY_DIR)
    monkeypatch.setattr("josseph.pipeline.app.setup_logging", lambda: None)

    observation_extractor = ObservationExtractor()
    checkout_extractor = CheckoutExtractor()
    monkeypatch.setattr(
        "josseph.pipeline.app.select_extractors",
        lambda registry, tools: {
            "github": observation_extractor,
            "checkout": checkout_extractor,
            "ck": registry.get("ck"),
            "cm": registry.get("cm"),
        },
    )

    exit_code = RepositoryAnalysisPipeline().run(_write_config(tmp_path))

    assert exit_code == 0

    project_dir = results_dir / "junit-team@junit4"
    assert (project_dir / "github.parquet").is_file()
    assert (project_dir / "github.json").is_file()
    assert (project_dir / "ck.parquet").is_file()
    assert (project_dir / "ck.json").is_file()
    assert (project_dir / "cm.parquet").is_file()
    assert (project_dir / "cm.json").is_file()

    assert (project_dir / "checkout.parquet").is_file()
    assert (project_dir / "checkout.json").is_file()

    assert not pd.read_parquet(project_dir / "github.parquet").empty
    ck_frame = pd.read_parquet(project_dir / "ck.parquet")
    assert not ck_frame.empty
    assert "cbo" in ck_frame.columns
    cm_frame = pd.read_parquet(project_dir / "cm.parquet")
    assert not cm_frame.empty
    assert "file" in cm_frame.columns
    assert cm_frame["file"].str.endswith(".java").all()

    github_metadata = json.loads((project_dir / "github.json").read_text(encoding="utf-8"))
    ck_metadata = json.loads((project_dir / "ck.json").read_text(encoding="utf-8"))
    cm_metadata = json.loads((project_dir / "cm.json").read_text(encoding="utf-8"))
    assert "collected_at_utc" in github_metadata
    assert "collected_at_utc" in ck_metadata
    assert "collected_at_utc" in cm_metadata
    assert "commit_hash" in github_metadata
    assert "commit_hash" in ck_metadata
    assert "commit_hash" in cm_metadata
    assert github_metadata["requested_commit_hash"] == REAL_COMMIT
    assert ck_metadata["requested_commit_hash"] == REAL_COMMIT
    assert cm_metadata["requested_commit_hash"] == REAL_COMMIT
    assert ck_metadata["commit_hash"] == REAL_COMMIT
    assert cm_metadata["commit_hash"] == REAL_COMMIT

    runs_dir = results_dir / "runs"
    assert runs_dir.is_dir()
    run_dirs = sorted((results_dir / "runs").iterdir())
    assert run_dirs
    summary = json.loads((run_dirs[-1] / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "success"
    assert summary["exit_code"] == 0
