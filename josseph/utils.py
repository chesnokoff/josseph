import logging
import logging.config
import os
import ssl
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, TypeVar
from urllib.error import HTTPError, URLError

import certifi

ROOT = Path(__file__).resolve().parents[1]
CONFIGS_DIR = ROOT / "configs"
RESULTS_DIR = ROOT / "results"
THIRD_PARTY_DIR = ROOT / "third_party"

# The workspace directory where repositories are cloned.
# Override with JOSSEPH_WORKSPACE env var to use a custom path
# (e.g. inside a Docker volume mount or a CI workspace).
_workspace_env = os.environ.get("JOSSEPH_WORKSPACE")
PROJECTS_DIR = (
    Path(_workspace_env) / "projects"
    if _workspace_env
    else ROOT / "workspace" / "projects"
)

_LOGGING_CONFIGURED = False
TRACE_LEVEL = 5
T = TypeVar("T")


class AnalysisError(Exception):
    """Raised when an analysis tool fails."""


def next_logfile(log_dir: Path, prefix: str) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)

    nums = []
    for p in log_dir.glob(f"{prefix}-*.log"):
        with suppress(ValueError):
            nums.append(int(p.stem.split("-")[-1]))

    n = max(nums, default=0) + 1
    return log_dir / f"{prefix}-{n:04d}.log"


def setup_logconfig() -> None:
    logfile = next_logfile(ROOT / "logs", "josseph")
    defaults: dict[str, Any] = {"sys": sys, "logfile": str(logfile)}

    logging.config.fileConfig(
        ROOT / "logging.ini",
        defaults=defaults,
        disable_existing_loggers=False,
    )

    logging.getLogger("josseph").info("Logging to %s", logfile)


def setup_trace() -> None:
    if getattr(logging, "TRACE", None) != TRACE_LEVEL:
        logging.addLevelName(TRACE_LEVEL, "TRACE")
    logging.TRACE = TRACE_LEVEL  # type: ignore[attr-defined]

    def trace(self: logging.Logger, msg: object, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(TRACE_LEVEL):
            kwargs.setdefault("stacklevel", 2)
            self._log(TRACE_LEVEL, msg, args, **kwargs)

    logging.Logger.trace = trace  # type: ignore[attr-defined]


def setup_logging() -> None:
    global _LOGGING_CONFIGURED
    setup_trace()
    if _LOGGING_CONFIGURED:
        return
    setup_logconfig()
    _LOGGING_CONFIGURED = True


def create_ssl_context() -> ssl.SSLContext:
    """Create an SSL context seeded with certifi certificates when available."""

    context = ssl.create_default_context()
    if certifi is not None:
        with suppress(Exception):
            context.load_verify_locations(certifi.where())
    return context


def retry_http_request(
    *,
    url: str,
    request_name: str,
    logger: logging.Logger,
    max_retries: int,
    initial_backoff_seconds: float,
    request: Callable[[], T],
    should_retry_http_error: Callable[[HTTPError], bool],
    retry_delay: Callable[[HTTPError, float], float],
    is_retryable_url_error: Callable[[URLError], bool],
) -> T:
    backoff = initial_backoff_seconds
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return request()
        except HTTPError as exc:
            last_exc = exc
            if should_retry_http_error(exc) and attempt < max_retries:
                wait_seconds = retry_delay(exc, backoff)
                logger.debug(
                    "%s to %s failed with HTTP %s on attempt %s/%s; sleeping for %ss",
                    request_name,
                    url,
                    exc.code,
                    attempt,
                    max_retries,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                backoff *= 2
                continue
            raise
        except URLError as exc:
            last_exc = exc
            if attempt < max_retries and is_retryable_url_error(exc):
                logger.debug(
                    "%s to %s failed on attempt %s/%s; sleeping for %ss",
                    request_name,
                    url,
                    attempt,
                    max_retries,
                    backoff,
                )
                time.sleep(backoff)
                backoff *= 2
                continue
            raise
    assert last_exc is not None
    raise last_exc


setup_trace()
