"""Pipeline configuration objects."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from josseph.domain.repository import RepositorySpec
from josseph.pipeline.repositories import read_repositories


@dataclass(frozen=True)
class AnalysisConfig:
    config_path: Path
    repositories: list[RepositorySpec]
    tools: list[str] | None
    extractor_settings: dict[str, dict[str, object]]
    github_token: str | None
    workers: int

    def to_report_dict(self) -> dict[str, object]:
        return {
            "config_path": str(self.config_path),
            "repositories": [repository.to_report_dict() for repository in self.repositories],
            "tools": list(self.tools) if self.tools is not None else None,
            "extractor_settings": dict(self.extractor_settings),
            "github_token": "***redacted***" if self.github_token else None,
            "workers": self.workers,
        }


def build_config(args) -> AnalysisConfig:
    config_path = Path(args.config_path).expanduser().resolve()
    raw = _read_yaml(config_path)
    _reject_unsupported_fields(raw)
    repositories = _parse_repositories(raw, config_path)
    tools = _parse_tools(raw.get("tools"))
    extractor_settings = _parse_extractor_settings(raw.get("extractor_settings"))
    github_token = _parse_optional_string(raw.get("github_token"), "github_token")
    if github_token is None:
        github_token = os.environ.get("GITHUB_TOKEN")

    return AnalysisConfig(
        config_path=config_path,
        repositories=repositories,
        tools=tools,
        extractor_settings=extractor_settings,
        github_token=github_token,
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


def _parse_repositories(raw: dict, config_path: Path) -> list[RepositorySpec]:
    repositories_value = raw.get("repositories")
    if repositories_value is None:
        raise ValueError("Configuration must define 'repositories' as a path to a file")

    if not isinstance(repositories_value, str):
        raise ValueError("'repositories' must be a path to a file with repository URLs")

    repositories_path_value = _parse_optional_string(repositories_value, "repositories")
    if repositories_path_value is None:
        raise ValueError("'repositories' cannot be empty")

    repositories_path = (
        config_path.parent / Path(repositories_path_value).expanduser()
    ).resolve()
    repositories = read_repositories(repositories_path)
    if not repositories:
        raise ValueError(f"Repository list {repositories_path} is empty")
    return list(dict.fromkeys(repositories))


def _parse_tools(value: object) -> list[str] | None:
    if value is None:
        return None

    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        raise ValueError("'tools' must be a string or a list of strings")

    parsed: list[str] = []
    seen: set[str] = set()
    for item in items:
        tool_name = _parse_optional_string(item, "tools")
        if tool_name is None:
            raise ValueError("'tools' cannot contain empty tool names")
        if tool_name in seen:
            continue
        seen.add(tool_name)
        parsed.append(tool_name)
    return parsed or None


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


def _parse_optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"'{field_name}' must be a string")
    stripped = value.strip()
    return stripped or None


def _reject_unsupported_fields(raw: dict[str, object]) -> None:
    if "clone_depth" in raw:
        raise ValueError("'clone_depth' is no longer supported")
