"""Simple registry for metric tools."""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from josseph.metrics.abstract_extractor import MetricExtractor

ExtractorFactory = Callable[[], MetricExtractor]


class ExtractorRegistry:
    def __init__(self, factories: dict[str, ExtractorFactory]) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._factories = dict(factories)
        self._extractors: dict[str, MetricExtractor] = {}

    def get(self, name: str) -> MetricExtractor:
        if name in self._extractors:
            return self._extractors[name]

        if name not in self._factories:
            raise KeyError(f"Metric tool '{name}' is not registered")

        tool = self._factories[name]()
        self._extractors[name] = tool
        return tool

    def names(self) -> Iterable[str]:
        return sorted(self._factories)

    def create_all(self) -> dict[str, MetricExtractor]:
        for name in self.names():
            self.get(name)
        return dict(self._extractors)
