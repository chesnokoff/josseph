"""Command execution abstractions."""
from __future__ import annotations

import shlex
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
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


class CommandExecutionError(subprocess.CalledProcessError):
    """Raised when a command exits unsuccessfully or times out."""

    def __init__(
        self,
        returncode: int,
        cmd: Iterable[str],
        *,
        output: str | bytes | None = None,
        stderr: str | bytes | None = None,
        cwd: Path | None = None,
        timed_out: bool = False,
        timeout: int | float | None = None,
    ) -> None:
        super().__init__(returncode, tuple(cmd), output=output, stderr=stderr)
        self.cwd = cwd
        self.timed_out = timed_out
        self.timeout = timeout

    def __str__(self) -> str:
        command = format_command(self.cmd)
        state = "timed out" if self.timed_out else "failed"
        parts = [f"Command {state}: {command}", f"exit code={self.returncode}"]
        if self.cwd is not None:
            parts.append(f"cwd={self.cwd}")
        if self.timeout is not None:
            parts.append(f"timeout={self.timeout}")

        stdout = clean_command_stream(self.output)
        stderr = clean_command_stream(self.stderr)
        if stdout:
            parts.append(f"stdout={stdout}")
        if stderr:
            parts.append(f"stderr={stderr}")
        return "; ".join(parts)


class SubprocessCommandRunner:
    def run(
        self,
        cmd: Iterable[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | float | None = None,
    ) -> str:
        command = tuple(cmd)
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=dict(env) if env is not None else None,
                check=True,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.CalledProcessError as exc:
            raise CommandExecutionError(
                exc.returncode,
                exc.cmd,
                output=exc.output,
                stderr=exc.stderr,
                cwd=cwd,
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CommandExecutionError(
                -1,
                exc.cmd,
                output=exc.stdout,
                stderr=exc.stderr,
                cwd=cwd,
                timed_out=True,
                timeout=exc.timeout,
            ) from exc
        return (result.stdout + result.stderr).strip()


def format_command(command: Iterable[str]) -> str:
    return shlex.join(str(part) for part in command)


def clean_command_stream(stream: object | None) -> str:
    if stream is None:
        return ""
    text = stream.decode("utf-8", errors="replace") if isinstance(stream, bytes) else str(stream)
    text = text.strip()
    if len(text) <= 4000:
        return text
    return f"{text[:4000]}…"


def describe_command_failure(
    tool_name: str,
    command: Iterable[str],
    exc: Exception,
) -> str:
    if isinstance(exc, CommandExecutionError) and exc.timed_out:
        return _describe_command_timeout(
            tool_name,
            command,
            exc.timeout,
            exc.output,
            exc.stderr,
        )
    if isinstance(exc, subprocess.TimeoutExpired):
        return _describe_command_timeout(
            tool_name,
            command,
            exc.timeout,
            exc.stdout,
            exc.stderr,
        )
    if isinstance(exc, (CommandExecutionError, subprocess.CalledProcessError)):
        return _describe_command_exit(
            tool_name,
            command,
            exc.returncode,
            getattr(exc, "stdout", None),
            getattr(exc, "stderr", None),
        )
    return f"{tool_name} execution failed: {exc}"


def _describe_command_exit(
    tool_name: str,
    command: Iterable[str],
    returncode: int,
    stdout: object,
    stderr: object,
) -> str:
    message = (
        f"{tool_name} execution failed with exit code {returncode}: "
        f"{format_command(command)}"
    )
    details = command_output_details(stdout, stderr)
    if details:
        message = f"{message}\n{details}"
    return message


def _describe_command_timeout(
    tool_name: str,
    command: Iterable[str],
    timeout: int | float | None,
    stdout: object,
    stderr: object,
) -> str:
    timeout_text = timeout if timeout is not None else "unknown"
    message = (
        f"{tool_name} execution timed out after {timeout_text} seconds: "
        f"{format_command(command)}"
    )
    details = command_output_details(stdout, stderr)
    if details:
        message = f"{message}\n{details}"
    return message


def command_output_details(stdout: object, stderr: object) -> str:
    parts = []
    if stdout:
        parts.append(f"stdout:\n{clean_command_stream(stdout).strip()}")
    if stderr:
        parts.append(f"stderr:\n{clean_command_stream(stderr).strip()}")
    return "\n".join(parts)
