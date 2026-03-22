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

EXTRACTOR_NAME = "ck"


class CkExtractor(MetricExtractor):
    """Run CK and emit CSV files for a repository."""

    def __init__(self, *, third_party_path: Path, command_runner: CommandRunner) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._command_runner = command_runner
        self.ck_jar = third_party_path / "ck" / "ck.jar"

        if not self.ck_jar.exists():
            raise AnalysisError(f"CK jar not found at {self.ck_jar}. Build it before running the analysis.")

    def run(self, target: AnalysisTarget) -> list[dict[str, str]]:
        repo_path = _require_checkout(target)
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            self.log.info(f"Running CK metrics on {repo_path}")

            try:
                self.log.trace(
                    self._command_runner.run(
                        ["java", "-jar", str(self.ck_jar), str(repo_path), "true", "0", "false", str(temp_dir) + "/"]
                    )
                )
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


def _require_checkout(target: AnalysisTarget) -> Path:
    if target.checkout_path is None:
        raise AnalysisError("CK extractor requires a local repository checkout.")
    return target.checkout_path


def build_extractor(
    context: ExtractorFactoryContext,
    settings: dict[str, object],
) -> CkExtractor:
    if settings:
        unknown = ", ".join(sorted(settings))
        raise ValueError(f"Unknown setting(s) for extractor 'ck': {unknown}")
    return CkExtractor(
        third_party_path=context.third_party_path,
        command_runner=context.command_runner,
    )
