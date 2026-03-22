from __future__ import annotations

from argparse import Namespace

import pytest

from josseph.pipeline.config import build_config


def test_build_config_reads_yaml_and_resolves_repositories(tmp_path, monkeypatch):
    repos_file = tmp_path / "repos.txt"
    repos_file.write_text(
        "\n".join(
            [
                "https://github.com/example/alpha.git",
                "",
                "# comment",
                "https://github.com/example/beta.git",
                "https://github.com/example/alpha.git",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "tools:",
                "  - github",
                "  - ck",
                "clone_depth: 5",
                "workers: '3'",
                "repositories: repos.txt",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    config = build_config(Namespace(config_path=str(config_file)))

    assert config.config_path == config_file.resolve()
    assert config.repositories == [
        "https://github.com/example/alpha.git",
        "https://github.com/example/beta.git",
    ]
    assert config.tools == ["github", "ck"]
    assert config.clone_depth == 5
    assert config.workers == 3
    assert config.github_token is None


def test_build_config_uses_environment_github_token(tmp_path, monkeypatch):
    repos_file = tmp_path / "repos.txt"
    repos_file.write_text("https://github.com/example/repo.git\n", encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    config_file.write_text("repositories: repos.txt\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")

    config = build_config(Namespace(config_path=str(config_file)))

    assert config.github_token == "env-token"


def test_build_config_rejects_invalid_workers(tmp_path):
    repos_file = tmp_path / "repos.txt"
    repos_file.write_text("https://github.com/example/repo.git\n", encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "repositories: repos.txt",
                "workers: 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="'workers' must be a positive integer"):
        build_config(Namespace(config_path=str(config_file)))
