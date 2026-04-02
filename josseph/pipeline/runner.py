"""Parallel pipeline execution."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from josseph.domain.repository import RepositorySpec
from josseph.pipeline.analyzer import RepositoryAnalysisError, RepositoryAnalyzer
from josseph.pipeline.run_report import RunReportCollector


class AnalysisRunner:
    def __init__(self) -> None:
        self.log = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def run(
        self,
        repos: list[RepositorySpec],
        analyzer: RepositoryAnalyzer,
        workers: int,
        run_reporter: RunReportCollector | None = None,
    ) -> int:
        if not repos:
            return 0
        if workers < 1:
            raise ValueError("'workers' must be a positive integer")

        max_workers = min(workers, len(repos))
        failures = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyzer.analyze, repo): repo for repo in repos
            }
            for future in as_completed(futures):
                repo = futures[future]
                try:
                    future.result()
                except RepositoryAnalysisError as exc:
                    failures += 1
                    if run_reporter is not None:
                        run_reporter.record_repository_failure(
                            repo_url=repo.repo_url,
                            requested_commit_hash=repo.requested_commit_hash,
                            reason=str(exc),
                        )
                    self.log.error("Repository analysis failed for %s: %s", repo.repo_url, exc)
                except Exception as exc:  # noqa: BLE001 - preserved behavior
                    failures += 1
                    if run_reporter is not None:
                        run_reporter.record_repository_failure(
                            repo_url=repo.repo_url,
                            requested_commit_hash=repo.requested_commit_hash,
                            reason=f"{exc.__class__.__name__}: {exc}",
                        )
                    self.log.exception("Unexpected failure analysing %s", repo.repo_url)
        return failures
