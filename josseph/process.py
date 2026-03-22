"""Command execution abstractions."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
import subprocess
from typing import Protocol


class CommandRunner(Protocol):
    def run(
        self,
        cmd: Iterable[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | float | None = None,
    ) -> str:
        """Run a command and return combined stdout/stderr."""


class SubprocessCommandRunner:
    def run(
        self,
        cmd: Iterable[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | float | None = None,
    ) -> str:
        result = subprocess.run(
            tuple(cmd),
            cwd=cwd,
            env=dict(env) if env is not None else None,
            check=True,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return (result.stdout + result.stderr).strip()
