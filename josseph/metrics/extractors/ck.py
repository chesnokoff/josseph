from __future__ import annotations

import csv
import logging
import tempfile
from pathlib import Path

from josseph.metrics.extractor import ExtractorConfig, MetricExtractor, extractor
from josseph.utils import AnalysisError, run_command


@extractor("ck")
class CkExtractor(MetricExtractor):
    """Run CK and emit CSV files for a repository."""

    def __init__(self, cfg: ExtractorConfig) -> None:
        super().__init__(cfg)
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.ck_jar = cfg.tools_path / "ck" / "ck.jar"

        if not self.ck_jar.exists():
            raise AnalysisError(f"CK jar not found at {self.ck_jar}. Build it before running the analysis.")

    def run(self, repo_path: Path, project_name: str) -> list[dict[str, str]]:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            self.log.info(f"Running CK metrics on {repo_path}")

            try:
                self.log.trace(run_command(["java", "-jar", str(self.ck_jar), str(repo_path), "true", "0", "false", str(temp_dir) + "/", ]))
            except Exception as exc:
                raise AnalysisError(f"CK execution failed: {exc}") from exc

            csv_file = temp_dir / "class.csv"

            if not csv_file.exists():
                raise AnalysisError(f"CM metrics output file not found: {csv_file}")

            metrics = []

            with csv_file.open(newline="") as fh:
                for row in csv.DictReader(fh):
                    metrics.append(row)
            return metrics
