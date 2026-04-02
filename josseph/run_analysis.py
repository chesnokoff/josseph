"""Backward-compatible exports for pipeline orchestration.

Deprecated: import directly from the pipeline submodules instead.
This shim exists for external code written against earlier versions of the
package and will be removed in a future release.
"""
from __future__ import annotations

from josseph.pipeline.analyzer import RepositoryAnalyzer
from josseph.pipeline.app import RepositoryAnalysisPipeline
from josseph.pipeline.cloner import RepositoryCloner, cloned_repository
from josseph.pipeline.config import AnalysisConfig, build_config
from josseph.pipeline.extractor_factory import select_extractors
from josseph.pipeline.repositories import sanitize_repo_name
from josseph.pipeline.results import ResultDirectoryManager, ResultWriter
from josseph.pipeline.runner import AnalysisRunner

__all__ = [
    "AnalysisConfig",
    "AnalysisRunner",
    "RepositoryAnalysisPipeline",
    "RepositoryAnalyzer",
    "RepositoryCloner",
    "ResultDirectoryManager",
    "ResultWriter",
    "build_config",
    "cloned_repository",
    "sanitize_repo_name",
    "select_extractors",
]
