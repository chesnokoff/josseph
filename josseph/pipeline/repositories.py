"""Repository list and naming helpers."""
from __future__ import annotations

from pathlib import Path

import yaml

from josseph.domain.repository import RepositorySpec


def sanitize_repo_name(repo_url: str | RepositorySpec) -> str:
    """Convert a repository URL to <owner>@<repo>."""
    return RepositorySpec.coerce(repo_url).project_name


def read_repositories(path: Path) -> list[RepositorySpec]:
    """Load repository specs from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Repository list {path} not found")

    repositories = _read_yaml_repositories(path)
    return _deduplicate_repositories(repositories, path)


def _read_yaml_repositories(path: Path) -> list[RepositorySpec]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in repository list {path}: {exc}") from exc

    if loaded is None:
        return []
    if not isinstance(loaded, list):
        raise ValueError(f"Repository list {path} must contain a YAML sequence")

    repositories: list[RepositorySpec] = []
    for index, item in enumerate(loaded, start=1):
        repositories.append(_parse_yaml_repository_item(item, path=path, index=index))
    return repositories


def _parse_yaml_repository_item(item: object, *, path: Path, index: int) -> RepositorySpec:
    item_label = f"repository list {path} item #{index}"
    if isinstance(item, str):
        return RepositorySpec.from_url(item)

    if not isinstance(item, dict):
        raise ValueError(
            f"{item_label} must be either a repository string or a mapping with url/commit"
        )

    if "url" in item:
        unknown = sorted(set(item) - {"url", "commit"})
        if unknown:
            unknown_list = ", ".join(unknown)
            raise ValueError(f"{item_label} has unknown field(s): {unknown_list}")
        repo_url = _parse_required_string(item.get("url"), f"{item_label}.url")
        commit_hash = _parse_optional_string(item.get("commit"), f"{item_label}.commit")
        return RepositorySpec.from_url(repo_url, requested_commit_hash=commit_hash)

    if len(item) != 1:
        raise ValueError(
            f"{item_label} must use either {{url, commit}} or a single-entry mapping"
        )

    repo_url, raw_value = next(iter(item.items()))
    repo_url = _parse_required_string(repo_url, f"{item_label}.repo")
    if raw_value is None:
        return RepositorySpec.from_url(repo_url)
    if isinstance(raw_value, str):
        return RepositorySpec.from_url(repo_url, requested_commit_hash=raw_value)
    if not isinstance(raw_value, dict):
        raise ValueError(f"{item_label} mapping value must be a string, mapping, or null")

    unknown = sorted(set(raw_value) - {"commit"})
    if unknown:
        unknown_list = ", ".join(unknown)
        raise ValueError(f"{item_label} has unknown nested field(s): {unknown_list}")
    commit_hash = _parse_optional_string(raw_value.get("commit"), f"{item_label}.commit")
    return RepositorySpec.from_url(repo_url, requested_commit_hash=commit_hash)


def _deduplicate_repositories(
    repositories: list[RepositorySpec],
    path: Path,
) -> list[RepositorySpec]:
    deduplicated: list[RepositorySpec] = []
    seen: set[tuple[str, str | None]] = set()
    commits_by_project: dict[str, str | None] = {}

    for repository in repositories:
        commit_for_project = commits_by_project.get(repository.project_name)
        has_seen_project = repository.project_name in commits_by_project
        if has_seen_project and commit_for_project != repository.requested_commit_hash:
            raise ValueError(
                f"Repository list {path} contains multiple entries for "
                f"{repository.project_name} with different requested commits"
            )

        commits_by_project[repository.project_name] = repository.requested_commit_hash
        key = (repository.project_name, repository.requested_commit_hash)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(repository)
    return deduplicated


def _parse_required_string(value: object, field_name: str) -> str:
    parsed = _parse_optional_string(value, field_name)
    if parsed is None:
        raise ValueError(f"'{field_name}' cannot be empty")
    return parsed


def _parse_optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"'{field_name}' must be a string")
    stripped = value.strip()
    return stripped or None
