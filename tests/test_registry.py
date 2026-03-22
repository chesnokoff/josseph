from __future__ import annotations

import pytest

from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.metrics.registry import ExtractorRegistry
from josseph.pipeline.extractor_factory import select_extractors


class DummyExtractor(MetricExtractor):
    def run(self, target):
        return []


def make_registry():
    return ExtractorRegistry(
        {
            "ck": lambda: DummyExtractor(),
            "cm": lambda: DummyExtractor(),
            "github": lambda: DummyExtractor(),
            "sonar": lambda: DummyExtractor(),
        }
    )


def test_registry_exposes_expected_extractor_names():
    registry = make_registry()

    created = registry.create_all()

    assert registry.names() == ["ck", "cm", "github", "sonar"]
    assert set(created) == {"ck", "cm", "github", "sonar"}


def test_registry_caches_created_extractors():
    registry = make_registry()

    first = registry.get("github")
    second = registry.get("github")

    assert first is second


def test_extractor_factory_rejects_unknown_tool():
    registry = make_registry()

    with pytest.raises(ValueError, match="Unknown tool\\(s\\): missing"):
        select_extractors(registry, ["github", "missing"])
