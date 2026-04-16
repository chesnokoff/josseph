from __future__ import annotations

import csv
import logging
import subprocess
import tempfile
from pathlib import Path

from josseph.domain.repository import AnalysisTarget
from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.metrics.registry import ExtractorFactoryContext
from josseph.process import (
    CommandExecutionError,
    CommandRunner,
    clean_command_stream,
    describe_command_failure,
)
from josseph.utils import AnalysisError

EXTRACTOR_NAME = "ck"


class CkExtractor(MetricExtractor):
    """Run CK and emit CSV files for a repository."""

    def __init__(self, *, third_party_path: Path, command_runner: CommandRunner) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._command_runner = command_runner
        self.ck_jar = third_party_path / "ck" / "ck.jar"

        if not self.ck_jar.exists():
            raise AnalysisError(
                f"CK jar not found at {self.ck_jar}. Build it before running the analysis."
            )

    def run(self, target: AnalysisTarget) -> list[dict[str, object]]:
        repo_path = _require_checkout(target)
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            self.log.info("Running CK metrics on %s", repo_path)

            self._run_ck_command(repo_path, temp_dir)

            csv_file = temp_dir / "class.csv"

            if not csv_file.exists():
                raise AnalysisError(f"CK metrics output file not found: {csv_file}")

            metrics: list[dict[str, object]] = []

            with csv_file.open(newline="") as fh:
                for row in csv.DictReader(fh):
                    metrics.append(row)
            return metrics

    def _run_ck_command(self, repo_path: Path, temp_dir: Path) -> None:
        command = [
            "java",
            "-jar",
            str(self.ck_jar),
            str(repo_path),
            "true",
            "0",
            "false",
            f"{temp_dir}/",
        ]
        try:
            output = self._command_runner.run(command)
        except AnalysisError:
            raise
        except (
            CommandExecutionError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as exc:
            raise AnalysisError(describe_command_failure("CK", command, exc)) from exc
        except Exception as exc:
            raise AnalysisError(f"CK execution failed: {exc}") from exc

        if output:
            self.log.log(
                5,
                "CK command output for %s:\n%s",
                repo_path,
                clean_command_stream(output).strip(),
            )


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
