from __future__ import annotations

import importlib


def test_projects_dir_defaults_to_repo_local_workspace(monkeypatch):
    monkeypatch.delenv("JOSSEPH_WORKSPACE", raising=False)

    import josseph.utils as utils

    module = importlib.reload(utils)

    assert module.PROJECTS_DIR == module.ROOT / "workspace" / "projects"


def test_projects_dir_uses_workspace_override(monkeypatch):
    monkeypatch.setenv("JOSSEPH_WORKSPACE", "/tmp/custom-workspace")

    import josseph.utils as utils

    module = importlib.reload(utils)

    assert module.Path("/tmp/custom-workspace") / "projects" == module.PROJECTS_DIR
