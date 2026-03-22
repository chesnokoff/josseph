from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from josseph.pipeline.results import ResultDirectoryManager, ResultWriter


def test_result_directory_manager_requires_parquet_and_metadata(tmp_path):
    manager = ResultDirectoryManager(tmp_path)
    project_dir = manager.prepare("example@repo")
    parquet_path = project_dir / "github.parquet"
    metadata_path = project_dir / "github.json"

    assert manager.has_result("example@repo", "github") is False

    parquet_path.write_text("placeholder", encoding="utf-8")
    assert manager.has_result("example@repo", "github") is False

    metadata_path.write_text("{}\n", encoding="utf-8")
    assert manager.has_result("example@repo", "github") is True


def test_result_writer_persists_parquet_and_metadata(tmp_path):
    writer = ResultWriter()
    output_dir = tmp_path / "example@repo"
    collected_at = datetime(2026, 3, 22, 12, 34, 56, tzinfo=timezone.utc)

    writer.write(
        output_dir,
        "github",
        [{"stars": 42, "language": "Java"}],
        commit_hash="abc123",
        collected_at=collected_at,
    )

    parquet_path = output_dir / "github.parquet"
    metadata_path = output_dir / "github.json"

    assert parquet_path.is_file()
    assert metadata_path.is_file()
    assert pd.read_parquet(parquet_path).to_dict(orient="records") == [
        {"stars": 42, "language": "Java"}
    ]
    assert json.loads(metadata_path.read_text(encoding="utf-8")) == {
        "commit_hash": "abc123",
        "collected_at_utc": "2026-03-22T12:34:56Z",
    }
