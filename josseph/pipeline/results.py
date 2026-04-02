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

    def has_result(
        self,
        project_name: str,
        tool_name: str,
        *,
        requested_commit_hash: str | None = None,
        metric_binding: str = "revision-bound",
    ) -> bool:
        base = self._result_base_path(project_name, tool_name)
        parquet_path = base.with_suffix(".parquet")
        metadata_path = base.with_suffix(".json")
        if not (parquet_path.is_file() and metadata_path.is_file()):
            return False
        if metric_binding != "revision-bound" or requested_commit_hash is None:
            return True

        metadata = self._read_metadata(metadata_path)
        if metadata is None:
            return False
        resolved_commit_hash = metadata.get("commit_hash")
        if not isinstance(resolved_commit_hash, str) or not resolved_commit_hash:
            return False
        return resolved_commit_hash == requested_commit_hash or resolved_commit_hash.startswith(
            requested_commit_hash
        )

    def _read_metadata(self, metadata_path: Path) -> dict[str, object] | None:
        try:
            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.log.warning("Failed to read metadata file %s: %s", metadata_path, exc)
            return None
        if not isinstance(loaded, dict):
            self.log.warning("Metadata file %s does not contain a JSON object", metadata_path)
            return None
        return loaded


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
        requested_commit_hash: str | None,
        metric_binding: str,
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
            "requested_commit_hash": requested_commit_hash,
            "metric_binding": metric_binding,
            "collected_at_utc": timestamp_text,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
