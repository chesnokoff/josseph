"""Parallel pipeline execution."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from josseph.pipeline.analyzer import RepositoryAnalyzer
from josseph.pipeline.run_report import RunReportCollector


class AnalysisRunner:
    def __init__(self) -> None:
        self.log = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def run(
        self,
        repos: list[str],
        analyzer: RepositoryAnalyzer,
        clone_depth: int | None,
        workers: int,
        run_reporter: RunReportCollector | None = None,
    ) -> int:
        max_workers = min(workers, len(repos))
        failures = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyzer.analyze, repo, clone_depth): repo for repo in repos
            }
            for future in as_completed(futures):
                repo = futures[future]
                try:
                    future.result()
                except Exception as exc:  # noqa: BLE001 - preserved behavior
                    failures += 1
                    if run_reporter is not None:
                        run_reporter.record_repository_failure(
                            repo_url=repo,
                            reason=str(exc),
                        )
                    self.log.warning("Failed to analyse %s: %s", repo, exc)
        return failures
