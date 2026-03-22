from __future__ import annotations

import csv
import logging
import tempfile
from pathlib import Path

from josseph.domain.repository import AnalysisTarget
from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.metrics.registry import ExtractorFactoryContext
from josseph.process import CommandRunner
from josseph.utils import AnalysisError

EXTRACTOR_NAME = "cm"


class CmExtractor(MetricExtractor):
    def __init__(
        self,
        *,
        third_party_path: Path,
        command_runner: CommandRunner,
        timeout_seconds: int,
    ) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._command_runner = command_runner
        self.cm_timeout_seconds = timeout_seconds
        self.cm_jar = third_party_path / "cm" / "cm.jar"
        if not self.cm_jar.exists():
            raise AnalysisError(f"CM jar not found at {self.cm_jar}. Build it before running the analysis.")

    def run(self, target: AnalysisTarget) -> list[dict[str, str]]:
        repo_path = _require_checkout(target)
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            self.log.info(f"Running CM metrics on {repo_path}")

            try:
                self.log.trace(
                    self._command_runner.run(
                        ["java", "-jar", str(self.cm_jar), str(repo_path), temp_dir / "results.csv", "single"],
                        timeout=self.cm_timeout_seconds,
                    )
                )
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


def _require_checkout(target: AnalysisTarget) -> Path:
    if target.checkout_path is None:
        raise AnalysisError("CM extractor requires a local repository checkout.")
    return target.checkout_path


def build_extractor(
    context: ExtractorFactoryContext,
    settings: dict[str, object],
) -> CmExtractor:
    allowed = {"timeout_seconds"}
    unknown = sorted(set(settings) - allowed)
    if unknown:
        unknown_list = ", ".join(unknown)
        raise ValueError(f"Unknown setting(s) for extractor 'cm': {unknown_list}")

    timeout_value = settings.get("timeout_seconds", int(context.env.get("CM_TIMEOUT_SECONDS", "3600")))
    if isinstance(timeout_value, bool) or not isinstance(timeout_value, int) or timeout_value < 1:
        raise ValueError("Extractor setting 'cm.timeout_seconds' must be a positive integer")

    return CmExtractor(
        third_party_path=context.third_party_path,
        command_runner=context.command_runner,
        timeout_seconds=timeout_value,
    )
