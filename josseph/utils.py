import logging
import ssl
import subprocess
import sys
from collections.abc import Iterable
from logging import config
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
PROJECTS_DIR = ROOT / "workspace" / "projects"


class AnalysisError(Exception):
    """Raised when an analysis tool fails."""

def next_logfile(log_dir: Path, prefix: str) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)

    nums = []
    for p in log_dir.glob(f"{prefix}-*.log"):
        try:
            nums.append(int(p.stem.split("-")[-1]))
        except ValueError:
            pass

    n = max(nums, default=0) + 1
    return log_dir / f"{prefix}-{n:04d}.log"

def setup_logconfig():
    logfile = next_logfile(Path("logs"), "josseph")

    logging.config.fileConfig(
        "logging.ini",
        defaults={"sys": sys, "logfile": str(logfile)},
        disable_existing_loggers=False,
    )

    logging.getLogger("josseph").info("Logging to %s", logfile)


def setup_trace():
    TRACE = 5
    logging.addLevelName(TRACE, "TRACE")
    setattr(logging, "TRACE", TRACE)

    def trace(self: logging.Logger, msg, *args, **kwargs):
        if self.isEnabledFor(TRACE):
            self._log(TRACE, msg, args, **kwargs)

    logging.Logger.trace = trace


def setup_logging() -> None:
    setup_trace()
    setup_logconfig()


def create_ssl_context() -> ssl.SSLContext:
    """Create an SSL context seeded with certifi certificates when available."""

    context = ssl.create_default_context()
    if certifi is not None:
        try:
            context.load_verify_locations(certifi.where())
        except Exception:  # pragma: no cover - best effort
            pass
    return context


def run_command(
    cmd: Iterable[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    return (result.stdout + result.stderr).strip()
