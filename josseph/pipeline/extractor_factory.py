"""Factory helpers for creating configured metric extractors."""
from __future__ import annotations

from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.metrics.registry import ExtractorRegistry


def select_extractors(
    registry: ExtractorRegistry,
    tools: list[str] | None,
) -> dict[str, MetricExtractor]:
    if not tools:
        return registry.create_all()

    available = set(registry.names())
    unknown = sorted({name for name in tools if name not in available})
    if unknown:
        available_list = ", ".join(sorted(available))
        unknown_list = ", ".join(unknown)
        raise ValueError(
            f"Unknown tool(s): {unknown_list}. Available tools: {available_list}"
        )

    selected: dict[str, MetricExtractor] = {}
    for name in tools:
        if name not in selected:
            selected[name] = registry.get(name)
    return selected
