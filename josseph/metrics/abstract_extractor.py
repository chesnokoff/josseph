"""Common interface for metric extraction tools."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from josseph.domain.repository import AnalysisTarget

MetricBinding = Literal["revision-bound", "observation-bound"]


class MetricExtractor(ABC):
    """Base class for all metric extraction tools."""

    requires_checkout: bool = True
    metric_binding: MetricBinding = "revision-bound"

    @abstractmethod
    def run(self, target: AnalysisTarget) -> list[dict[str, object]]:
        """Collect metrics for the given analysis target."""
