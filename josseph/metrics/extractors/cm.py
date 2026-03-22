from __future__ import annotations

import csv
import logging
import tempfile
from pathlib import Path

from josseph.metrics.extractor import ExtractorConfig, MetricExtractor, extractor
from josseph.utils import AnalysisError, run_command


@extractor("cm")
class CmExtractor(MetricExtractor):
    def __init__(self, cfg: ExtractorConfig) -> None:
        super().__init__(cfg)

        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        self.cm_jar = self.cfg.tools_path / "cm" / "cm.jar"
        if not self.cm_jar.exists():
            raise AnalysisError(f"CM jar not found at {self.cm_jar}. Build it before running the analysis.")

    def run(self, repo_path: Path, project_name: str) -> list[dict[str, str]]:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            self.log.info(f"Running CM metrics on {repo_path}")

            try:
                self.log.trace(run_command(["java", "-jar", str(self.cm_jar), str(repo_path), temp_dir / "results.csv", "single"]))
            except Exception as exc:
                raise AnalysisError(f"CM execution failed: {exc}") from exc

            csv_file = temp_dir / "results.csv"

            if not csv_file.exists():
                raise AnalysisError(f"CM metrics output file not found: {csv_file}")

            metrics = []

            with csv_file.open(newline="") as fh:
                for row in csv.DictReader(fh):
                    if not row.get("file").endswith(".java"):
                        continue
                    metrics.append(row)
            return metrics
