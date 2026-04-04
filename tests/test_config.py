from __future__ import annotations

from argparse import Namespace
import random

import pytest

from josseph.domain.repository import RepositorySpec
from josseph.pipeline.config import build_config


def test_build_config_reads_yaml_and_resolves_repositories(tmp_path, monkeypatch):
    repos_file = tmp_path / "repos.yaml"
    repos_file.write_text(
        "\n".join(
            [
                "- https://github.com/example/alpha.git",
                "- https://github.com/example/beta.git",
                "- https://github.com/example/alpha.git",
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
                "extractor_settings:",
                "  github:",
                "    token: test-token",
                "workers: '3'",
                "repositories: repos.yaml",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    config = build_config(Namespace(config_path=str(config_file)))

    assert config.config_path == config_file.resolve()
    assert config.repositories == [
        RepositorySpec.from_url("https://github.com/example/alpha.git"),
        RepositorySpec.from_url("https://github.com/example/beta.git"),
    ]
    assert config.tools == ["github", "ck"]
    assert config.extractor_settings == {"github": {"token": "test-token"}}
    assert config.workers == 3
    assert config.github_token is None


def test_build_config_reads_yaml_repository_specs_with_optional_commit(tmp_path, monkeypatch):
    repos_file = tmp_path / "repos.yaml"
    repos_file.write_text(
        "\n".join(
            [
                "- url: https://github.com/example/alpha.git",
                "  commit: deadbeefcafebabe",
                "- https://github.com/example/beta.git",
                "- https://github.com/example/gamma.git:",
                "    commit: facefeed1234",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"repositories: {repos_file.name}\n", encoding="utf-8")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    config = build_config(Namespace(config_path=str(config_file)))

    assert config.repositories == [
        RepositorySpec.from_url(
            "https://github.com/example/alpha.git",
            requested_commit_hash="deadbeefcafebabe",
        ),
        RepositorySpec.from_url("https://github.com/example/beta.git"),
        RepositorySpec.from_url(
            "https://github.com/example/gamma.git",
            requested_commit_hash="facefeed1234",
        ),
    ]


def test_build_config_rejects_conflicting_requested_commits_for_same_repository(tmp_path):
    repos_file = tmp_path / "repos.yaml"
    repos_file.write_text(
        "\n".join(
            [
                "- url: https://github.com/example/repo.git",
                "  commit: deadbeef",
                "- url: https://github.com/example/repo.git",
                "  commit: facefeed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"repositories: {repos_file.name}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="different requested commits"):
        build_config(Namespace(config_path=str(config_file)))


def test_build_config_uses_environment_github_token(tmp_path, monkeypatch):
    repos_file = tmp_path / "repos.yaml"
    repos_file.write_text("- https://github.com/example/repo.git\n", encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    config_file.write_text("repositories: repos.yaml\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")

    config = build_config(Namespace(config_path=str(config_file)))

    assert config.github_token == "env-token"


def test_build_config_rejects_invalid_workers(tmp_path):
    repos_file = tmp_path / "repos.yaml"
    repos_file.write_text("- https://github.com/example/repo.git\n", encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "repositories: repos.yaml",
                "workers: 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="'workers' must be a positive integer"):
        build_config(Namespace(config_path=str(config_file)))


def test_build_config_rejects_clone_depth(tmp_path):
    repos_file = tmp_path / "repos.yaml"
    repos_file.write_text("- https://github.com/example/repo.git\n", encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "repositories: repos.yaml",
                "clone_depth: 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="'clone_depth' is no longer supported"):
        build_config(Namespace(config_path=str(config_file)))


def test_build_config_rejects_empty_repository_list(tmp_path):
    repos_file = tmp_path / "repos.yaml"
    repos_file.write_text("[]\n", encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    config_file.write_text("repositories: repos.yaml\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Repository list .* is empty"):
        build_config(Namespace(config_path=str(config_file)))


def test_build_config_rejects_invalid_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("repositories: [unterminated\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid YAML"):
        build_config(Namespace(config_path=str(config_file)))


def test_build_config_requires_repositories_field(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("workers: 2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Configuration must define 'repositories'"):
        build_config(Namespace(config_path=str(config_file)))


def test_build_config_rejects_non_mapping_extractor_settings(tmp_path):
    repos_file = tmp_path / "repos.yaml"
    repos_file.write_text("- https://github.com/example/repo.git\n", encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "repositories: repos.yaml",
                "extractor_settings:",
                "  - invalid",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="'extractor_settings' must be a mapping"):
        build_config(Namespace(config_path=str(config_file)))


def test_build_config_deduplicates_tools_across_generated_inputs(tmp_path):
    rng = random.Random(0)
    available_tools = ["github", "ck", "cm", "sonar"]

    for index in range(20):
        repos_file = tmp_path / f"repos-{index}.yaml"
        repos_file.write_text("- https://github.com/example/repo.git\n", encoding="utf-8")

        raw_tools: list[str] = []
        for _ in range(rng.randint(1, 8)):
            tool_name = rng.choice(available_tools)
            padded = f"  {tool_name}  " if rng.random() < 0.5 else tool_name
            raw_tools.append(padded)

        config_file = tmp_path / f"config-{index}.yaml"
        config_lines = ["repositories: " + repos_file.name, "tools:"]
        config_lines.extend(f"  - {item}" for item in raw_tools)
        config_file.write_text("\n".join(config_lines) + "\n", encoding="utf-8")

        config = build_config(Namespace(config_path=str(config_file)))

        expected_tools: list[str] = []
        seen: set[str] = set()
        for tool_name in raw_tools:
            normalized = tool_name.strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            expected_tools.append(normalized)
        assert config.tools == expected_tools
