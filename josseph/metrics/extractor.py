"""Common interface for metric extraction tools."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Type

_REGISTRY: dict[str, Type[MetricExtractor]] = {}


def extractor(name: str | None = None):
    def decorator(tool_cls, tool_name: str | None = None):
        resolved_name = tool_name or tool_cls.__name__
        _REGISTRY[resolved_name] = tool_cls
        logger = logging.getLogger("josseph.metrics.extractor")
        logger.debug("Registered tool %s", resolved_name)
        return tool_cls

    if callable(name):
        return decorator(name, None)

    return lambda tool_cls: decorator(tool_cls, name)

def get_registry() -> dict[str, Type[MetricExtractor]]:
    from josseph.metrics import extractors  # noqa: F401

    return _REGISTRY


@dataclass(frozen=True)
class ExtractorConfig:
    tools_path: Path
    env: dict[str, str]

class MetricExtractor(ABC):
    """Base class for all metric extraction tools."""

    def __init__(self, cfg: ExtractorConfig) -> None:
        self.cfg = cfg

    @abstractmethod
    def run(self, repo_path: Path, project_name) -> list[dict]:
        """Collect metrics for the given repository path."""
