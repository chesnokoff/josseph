"""Common interface for metric extraction tools."""
from __future__ import annotations

from abc import ABC, abstractmethod

from josseph.domain.repository import AnalysisTarget


class MetricExtractor(ABC):
    """Base class for all metric extraction tools."""

    requires_checkout: bool = True

    @abstractmethod
    def run(self, target: AnalysisTarget) -> list[dict[str, object]]:
        """Collect metrics for the given analysis target."""
