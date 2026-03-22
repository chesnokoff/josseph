"""Result directory and persistence helpers."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


class ResultDirectoryManager:
    def __init__(self, results_dir: Path) -> None:
        self.log = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self._results_dir = results_dir

    def prepare(self, project_name: str) -> Path:
        result_dir = self._results_dir / project_name
        result_dir.mkdir(parents=True, exist_ok=True)
        return result_dir

    def _result_base_path(self, project_name: str, tool_name: str) -> Path:
        return self._results_dir / project_name / tool_name

    def has_result(self, project_name: str, tool_name: str) -> bool:
        base = self._result_base_path(project_name, tool_name)
        parquet_path = base.with_suffix(".parquet")
        metadata_path = base.with_suffix(".json")
        return parquet_path.is_file() and metadata_path.is_file()


class ResultWriter:
    def __init__(self) -> None:
        self.log = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def write(
        self,
        path: Path,
        tool_name: str,
        rows: list[dict],
        commit_hash: str,
        *,
        collected_at: datetime | None = None,
    ) -> None:
        path.mkdir(parents=True, exist_ok=True)

        out = path / f"{tool_name}.parquet"
        df = pd.DataFrame(rows)
        df.to_parquet(out, index=False, engine="pyarrow", compression="zstd")
        metadata_path = path / f"{tool_name}.json"
        timestamp = collected_at or datetime.now(timezone.utc)
        timestamp_text = timestamp.astimezone(timezone.utc).replace(microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        metadata = {
            "commit_hash": commit_hash,
            "collected_at_utc": timestamp_text,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
