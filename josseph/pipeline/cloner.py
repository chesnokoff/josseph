"""Repository cloning utilities."""
from __future__ import annotations

import logging
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from josseph.domain.repository import RepositoryRef
from josseph.process import CommandRunner


class RepositoryCloner:
    def __init__(self, projects_dir: Path, command_runner: CommandRunner) -> None:
        self.log = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self._projects_dir = projects_dir
        self._command_runner = command_runner

    def clone(self, repo_url: str, clone_depth: int | None) -> Path:
        project_name = RepositoryRef.parse(repo_url).project_name
        target = self._projects_dir / project_name
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        max_attempts = 3
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            self.log.info(
                "Cloning %s -> %s (attempt %s/%s)",
                repo_url,
                target,
                attempt,
                max_attempts,
            )
            cmd = ["git", "clone", "--single-branch", "--no-tags", repo_url, str(target)]
            if clone_depth:
                cmd[2:2] = ["--depth", str(clone_depth)]
            try:
                self.log.trace(self._command_runner.run(cmd))
                self.log.info("Finished cloning %s", repo_url)
                return target
            except Exception as exc:  # noqa: BLE001 - preserved behavior
                last_exc = exc
                shutil.rmtree(target, ignore_errors=True)
                if attempt < max_attempts:
                    sleep_seconds = attempt * 2
                    self.log.warning(
                        "Clone failed for %s on attempt %s/%s: %s. Retrying in %ss",
                        repo_url,
                        attempt,
                        max_attempts,
                        exc,
                        sleep_seconds,
                    )
                    time.sleep(sleep_seconds)
                else:
                    self.log.warning(
                        "Clone failed for %s after %s attempts: %s",
                        repo_url,
                        max_attempts,
                        exc,
                    )
        assert last_exc is not None
        raise last_exc

    def cleanup(self, repo_path: Path) -> None:
        shutil.rmtree(repo_path, ignore_errors=True)


@contextmanager
def cloned_repository(cloner: RepositoryCloner, repo_url: str, clone_depth: int | None):
    repo_path = cloner.clone(repo_url, clone_depth)
    try:
        yield repo_path
    finally:
        cloner.cleanup(repo_path)
