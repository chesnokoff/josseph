"""Simple registry for metric tools."""
from __future__ import annotations

from importlib import import_module
import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from pkgutil import iter_modules

from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.process import CommandRunner

ExtractorSettings = Mapping[str, object]


@dataclass(frozen=True)
class ExtractorFactoryContext:
    third_party_path: Path
    env: Mapping[str, str]
    command_runner: CommandRunner


ExtractorFactory = Callable[[ExtractorFactoryContext, ExtractorSettings], MetricExtractor]


class ExtractorRegistry:
    def __init__(
        self,
        context: ExtractorFactoryContext,
        *,
        package_name: str = "josseph.metrics.extractors",
        settings_by_name: Mapping[str, ExtractorSettings] | None = None,
    ) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._context = context
        self._settings_by_name = dict(settings_by_name or {})
        self._factories = discover_extractors(package_name)
        self._extractors: dict[str, MetricExtractor] = {}

    def get(self, name: str) -> MetricExtractor:
        if name in self._extractors:
            return self._extractors[name]

        if name not in self._factories:
            raise KeyError(f"Metric tool '{name}' is not registered")

        tool = self._factories[name](
            self._context,
            self._settings_by_name.get(name, {}),
        )
        self._extractors[name] = tool
        return tool

    def names(self) -> Iterable[str]:
        return sorted(self._factories)

    def create_all(self) -> dict[str, MetricExtractor]:
        for name in self.names():
            self.get(name)
        return dict(self._extractors)


def discover_extractors(package_name: str) -> dict[str, ExtractorFactory]:
    package = import_module(package_name)
    factories: dict[str, ExtractorFactory] = {}

    for module_info in iter_modules(package.__path__):
        if module_info.ispkg:
            continue
        module = import_module(f"{package_name}.{module_info.name}")
        extractor_name = getattr(module, "EXTRACTOR_NAME", None)
        factory = getattr(module, "build_extractor", None)
        if extractor_name is None and factory is None:
            continue
        if not isinstance(extractor_name, str) or not extractor_name.strip():
            raise ValueError(
                f"Extractor module '{module.__name__}' must define a non-empty EXTRACTOR_NAME"
            )
        if not callable(factory):
            raise ValueError(
                f"Extractor module '{module.__name__}' must define build_extractor(context, settings)"
            )
        if extractor_name in factories:
            raise ValueError(f"Duplicate extractor registration for '{extractor_name}'")
        factories[extractor_name] = factory

    return factories
