from __future__ import annotations

import csv
import logging
import subprocess
import tempfile
from pathlib import Path

from josseph.domain.repository import AnalysisTarget
from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.metrics.registry import ExtractorFactoryContext
from josseph.process import CommandExecutionError
from josseph.process import CommandRunner
from josseph.process import clean_command_stream
from josseph.process import describe_command_failure
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
            self.log.info("Running CM metrics on %s", repo_path)

            self._run_cm_command(repo_path, temp_dir)

            csv_file = temp_dir / "results.csv"

            if not csv_file.exists():
                raise AnalysisError(f"CM metrics output file not found: {csv_file}")

            metrics = []

            with csv_file.open(newline="") as fh:
                for row in csv.DictReader(fh):
                    if not (row.get("file") or "").endswith(".java"):
                        continue
                    metrics.append(row)
            return metrics

    def _run_cm_command(self, repo_path: Path, temp_dir: Path) -> None:
        command = [
            "java",
            "-jar",
            str(self.cm_jar),
            str(repo_path),
            str(temp_dir / "results.csv"),
            "single",
        ]
        try:
            output = self._command_runner.run(
                command,
                timeout=self.cm_timeout_seconds,
            )
        except AnalysisError:
            raise
        except (CommandExecutionError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise AnalysisError(describe_command_failure("CM", command, exc)) from exc
        except Exception as exc:
            raise AnalysisError(f"CM execution failed: {exc}") from exc

        if output:
            self.log.log(5, "CM command output for %s:\n%s", repo_path, clean_command_stream(output).strip())


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

    timeout_default = _parse_positive_int(context.env.get("CM_TIMEOUT_SECONDS", "3600"), "CM_TIMEOUT_SECONDS")
    timeout_value = _parse_positive_int(settings.get("timeout_seconds", timeout_default), "cm.timeout_seconds")

    return CmExtractor(
        third_party_path=context.third_party_path,
        command_runner=context.command_runner,
        timeout_seconds=timeout_value,
    )


def _parse_positive_int(value: object, setting_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Setting '{setting_name}' must be a positive integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(f"Setting '{setting_name}' must be a positive integer") from exc
    else:
        raise ValueError(f"Setting '{setting_name}' must be a positive integer")

    if parsed < 1:
        raise ValueError(f"Setting '{setting_name}' must be a positive integer")
    return parsed
