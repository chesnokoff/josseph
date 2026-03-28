"""Repository cloning utilities."""
from __future__ import annotations

import logging
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from josseph.domain.repository import RepositoryRef
from josseph.process import CommandRunner
from josseph.utils import setup_trace


class RepositoryCloner:
    def __init__(self, projects_dir: Path, command_runner: CommandRunner) -> None:
        setup_trace()
        self.log = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self._projects_dir = projects_dir
        self._command_runner = command_runner

    def clone(self, repo_url: str, clone_depth: int | None) -> Path:
        project_name = RepositoryRef.parse(repo_url).project_name
        target = self._projects_dir / project_name
        target.parent.mkdir(parents=True, exist_ok=True)

        max_attempts = 3
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            staging_dir = Path(
                tempfile.mkdtemp(
                    prefix=f".{project_name}.clone-",
                    dir=target.parent,
                )
            )
            self.log.info(
                "Cloning %s -> %s (attempt %s/%s)",
                repo_url,
                target,
                attempt,
                max_attempts,
            )
            cmd = ["git", "clone", "--single-branch", "--no-tags", repo_url, str(staging_dir)]
            if clone_depth:
                cmd[2:2] = ["--depth", str(clone_depth)]
            try:
                self.log.trace(self._command_runner.run(cmd))
                self._remove_path(target)
                staging_dir.replace(target)
                self.log.info("Finished cloning %s", repo_url)
                return target
            except Exception as exc:  # noqa: BLE001 - preserved behavior
                last_exc = exc
                self._remove_path(staging_dir)
                if attempt == max_attempts:
                    self._annotate_clone_failure(exc, repo_url, target, max_attempts)
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
        self._remove_path(repo_path)

    def _remove_path(self, path: Path) -> None:
        if not path.exists() and not path.is_symlink():
            return
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        except FileNotFoundError:
            return
        except Exception as exc:  # noqa: BLE001 - cleanup should not fail the run
            self.log.warning("Failed to remove %s: %s", path, exc)

    def _annotate_clone_failure(
        self,
        exc: Exception,
        repo_url: str,
        target: Path,
        max_attempts: int,
    ) -> None:
        note = (
            f"Failed to clone {repo_url} into {target} after {max_attempts} attempts."
        )
        add_note = getattr(exc, "add_note", None)
        if callable(add_note):
            add_note(note)


@contextmanager
def cloned_repository(cloner: RepositoryCloner, repo_url: str, clone_depth: int | None):
    repo_path = cloner.clone(repo_url, clone_depth)
    try:
        yield repo_path
    finally:
        cloner.cleanup(repo_path)
