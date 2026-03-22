"""Pipeline configuration objects."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from josseph.pipeline.repositories import read_repositories


@dataclass(frozen=True)
class AnalysisConfig:
    config_path: Path
    repositories: list[str]
    clone_depth: int | None
    tools: list[str] | None
    extractor_settings: dict[str, dict[str, object]]
    github_token: str | None
    workers: int


def build_config(args) -> AnalysisConfig:
    config_path = Path(args.config_path).expanduser().resolve()
    raw = _read_yaml(config_path)

    return AnalysisConfig(
        config_path=config_path,
        repositories=_parse_repositories(raw, config_path),
        clone_depth=_parse_clone_depth(raw.get("clone_depth")),
        tools=_parse_tools(raw.get("tools")),
        extractor_settings=_parse_extractor_settings(raw.get("extractor_settings")),
        github_token=_parse_optional_string(raw.get("github_token"), "github_token")
        or os.environ.get("GITHUB_TOKEN"),
        workers=_parse_workers(raw.get("workers")),
    )


def _read_yaml(config_path: Path) -> dict:
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file {config_path} not found")

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {config_path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(
            f"Configuration file {config_path} must contain a YAML mapping at the root"
        )
    return loaded


def _parse_repositories(raw: dict, config_path: Path) -> list[str]:
    repositories_value = raw.get("repositories")
    if repositories_value is None:
        raise ValueError("Configuration must define 'repositories' as a path to a file")

    if not isinstance(repositories_value, str):
        raise ValueError("'repositories' must be a path to a file with repository URLs")

    repositories_path_value = _parse_optional_string(repositories_value, "repositories")
    if repositories_path_value is None:
        raise ValueError("'repositories' cannot be empty")

    repositories_path = (config_path.parent / repositories_path_value).resolve()
    repositories = read_repositories(repositories_path)
    if not repositories:
        raise ValueError(f"Repository list {repositories_path} is empty")
    return list(dict.fromkeys(repositories))


def _parse_clone_depth(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("'clone_depth' must be a positive integer")
    if isinstance(value, int):
        if value < 1:
            raise ValueError("'clone_depth' must be a positive integer")
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if not stripped.isdigit() or int(stripped) < 1:
            raise ValueError("'clone_depth' must be a positive integer")
        return int(stripped)
    raise ValueError("'clone_depth' must be a positive integer")


def _parse_tools(value: object) -> list[str] | None:
    tools = _parse_string_list(value, "tools") if value is not None else None
    return tools or None


def _parse_workers(value: object) -> int:
    default_workers = os.cpu_count() or 1
    if value is None:
        return default_workers
    if isinstance(value, bool):
        raise ValueError("'workers' must be a positive integer")
    if isinstance(value, int):
        if value < 1:
            raise ValueError("'workers' must be a positive integer")
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        if parsed < 1:
            raise ValueError("'workers' must be a positive integer")
        return parsed
    raise ValueError("'workers' must be a positive integer")


def _parse_extractor_settings(value: object) -> dict[str, dict[str, object]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("'extractor_settings' must be a mapping of extractor names to settings")

    parsed: dict[str, dict[str, object]] = {}
    for raw_name, raw_settings in value.items():
        name = _parse_optional_string(raw_name, "extractor_settings key")
        if name is None:
            raise ValueError("'extractor_settings' cannot contain empty extractor names")
        if raw_settings is None:
            parsed[name] = {}
            continue
        if not isinstance(raw_settings, dict):
            raise ValueError(
                f"'extractor_settings.{name}' must be a mapping of setting names to values"
            )
        parsed[name] = dict(raw_settings)
    return parsed


def _parse_string_list(
    value: object,
    field_name: str,
    *,
    skip_comments: bool = False,
) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        raise ValueError(f"'{field_name}' must be a string or a list of strings")

    parsed: list[str] = []
    for item in items:
        string_value = _parse_optional_string(item, field_name)
        if string_value is None:
            continue
        if skip_comments and string_value.startswith("#"):
            continue
        parsed.append(string_value)
    return parsed


def _parse_optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"'{field_name}' must be a string")
    stripped = value.strip()
    return stripped or None
