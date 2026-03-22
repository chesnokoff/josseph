"""Simple registry for metric tools."""
from __future__ import annotations
from __future__ import annotations

import logging
from typing import Iterable, Type

from josseph.metrics.extractor import ExtractorConfig, MetricExtractor, get_registry


class ExtractorRegistry:
    def __init__(self) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        self._registry: dict[str, Type[MetricExtractor]] = get_registry()

        self._extractors: dict[str, MetricExtractor] = {}

    def get(self, name: str, cfg: ExtractorConfig) -> MetricExtractor:
        if name in self._extractors:
            return self._extractors[name]

        if name not in self._registry:
            raise KeyError(f"Metric tool '{name}' is not registered")

        tool = self._registry[name](cfg)
        self._extractors[name] = tool
        return tool

    def names(self) -> Iterable[str]:
        return sorted(self._registry)

    def create_all(self, cfg: ExtractorConfig) -> dict[str, MetricExtractor]:
        for name in self.names():
            self.get(name, cfg)
        return self._extractors