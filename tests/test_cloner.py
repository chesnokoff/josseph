from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from josseph.domain.repository import RepositorySpec
from josseph.pipeline.cloner import RepositoryCloner


class FakeCommandRunner:
    def __init__(self, handler):
        self._handler = handler
        self.calls = []

    def run(self, cmd, *, cwd=None, env=None, timeout=None):
        self.calls.append(
            {
                "cmd": list(cmd),
                "cwd": cwd,
                "env": env,
                "timeout": timeout,
            }
        )
        return self._handler(cmd, cwd=cwd, env=env, timeout=timeout)


def test_repository_cloner_import_does_not_setup_trace(monkeypatch):
    import josseph.utils as utils

    calls = []
    monkeypatch.setattr(utils, "setup_trace", lambda: calls.append("called"))
    sys.modules.pop("josseph.pipeline.cloner", None)

    importlib.import_module("josseph.pipeline.cloner")

    assert calls == []


def test_repository_cloner_initializes_trace_logging(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("josseph.pipeline.cloner.setup_trace", lambda: calls.append("called"))

    module = importlib.import_module("josseph.pipeline.cloner")
    module.RepositoryCloner(
        tmp_path / "projects",
        FakeCommandRunner(lambda *args, **kwargs: ""),
    )

    assert calls == ["called"]


def test_repository_cloner_retries_and_cleans_failed_staging_dirs(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    attempts = []

    monkeypatch.setattr("josseph.pipeline.cloner.time.sleep", lambda seconds: None)

    def fake_run_command(cmd, *, cwd=None, env=None, timeout=None):
        attempts.append(Path(cmd[-1]))
        if len(attempts) < 3:
            raise RuntimeError(f"clone failed on attempt {len(attempts)}")
        staging_dir = Path(cmd[-1])
        (staging_dir / "payload.txt").write_text("fresh", encoding="utf-8")
        return "cloned"

    cloner = RepositoryCloner(projects_dir, FakeCommandRunner(fake_run_command))
    target = cloner.clone("https://github.com/example/repo.git")

    assert target == projects_dir / "example@repo"
    assert len(attempts) == 3
    assert (target / "payload.txt").read_text(encoding="utf-8") == "fresh"
    assert [path.name for path in projects_dir.iterdir()] == ["example@repo"]


def test_repository_cloner_replaces_existing_checkout(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    target = projects_dir / "example@repo"
    target.mkdir(parents=True)
    (target / "stale.txt").write_text("stale", encoding="utf-8")

    monkeypatch.setattr("josseph.pipeline.cloner.time.sleep", lambda seconds: None)

    def fake_run_command(cmd, *, cwd=None, env=None, timeout=None):
        staging_dir = Path(cmd[-1])
        (staging_dir / "fresh.txt").write_text("fresh", encoding="utf-8")
        return "cloned"

    cloner = RepositoryCloner(projects_dir, FakeCommandRunner(fake_run_command))
    cloned = cloner.clone("https://github.com/example/repo.git")

    assert cloned == target
    assert (cloned / "fresh.txt").read_text(encoding="utf-8") == "fresh"
    assert not (cloned / "stale.txt").exists()
    assert [path.name for path in projects_dir.iterdir()] == ["example@repo"]


def test_repository_cloner_annotates_final_failure(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"

    monkeypatch.setattr("josseph.pipeline.cloner.time.sleep", lambda seconds: None)

    def fake_run_command(cmd, *, cwd=None, env=None, timeout=None):
        raise RuntimeError("clone failed")

    cloner = RepositoryCloner(projects_dir, FakeCommandRunner(fake_run_command))

    with pytest.raises(RuntimeError) as excinfo:
        cloner.clone("https://github.com/example/repo.git")

    assert excinfo.value.__notes__ == [
        "Failed to clone https://github.com/example/repo.git into "
        f"{projects_dir / 'example@repo'} after 3 attempts."
    ]


def test_repository_cloner_checks_out_requested_commit_after_clone(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    runner = FakeCommandRunner(lambda *args, **kwargs: "")

    monkeypatch.setattr("josseph.pipeline.cloner.time.sleep", lambda seconds: None)

    cloner = RepositoryCloner(projects_dir, runner)
    target = cloner.clone(
        RepositorySpec.from_url(
            "https://github.com/example/repo.git",
            requested_commit_hash="deadbeef",
        ),
    )

    assert target == projects_dir / "example@repo"
    assert runner.calls[0]["cmd"][:4] == [
        "git",
        "clone",
        "--single-branch",
        "--no-tags",
    ]
    assert runner.calls[0]["cmd"][4] == "https://github.com/example/repo.git"
    staging_dir = Path(runner.calls[0]["cmd"][-1])
    assert staging_dir.parent == projects_dir
    assert staging_dir.name.startswith(".example@repo.clone-")
    assert runner.calls[1]["cmd"] == ["git", "checkout", "--detach", "deadbeef"]
    assert runner.calls[1]["cwd"] == staging_dir


def test_repository_cloner_uses_single_branch_clone_without_shallow_depth(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    runner = FakeCommandRunner(lambda *args, **kwargs: "")

    monkeypatch.setattr("josseph.pipeline.cloner.time.sleep", lambda seconds: None)

    RepositoryCloner(projects_dir, runner).clone("https://github.com/example/repo.git")

    assert runner.calls[0]["cmd"][:4] == [
        "git",
        "clone",
        "--single-branch",
        "--no-tags",
    ]
    assert "--depth" not in runner.calls[0]["cmd"]
