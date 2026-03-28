"""Pipeline application entrypoint."""
from __future__ import annotations

import logging
import os

from josseph.metrics.registry import ExtractorFactoryContext, ExtractorRegistry
from josseph.pipeline.analyzer import RepositoryAnalyzer
from josseph.pipeline.cloner import RepositoryCloner
from josseph.pipeline.config import build_config
from josseph.pipeline.extractor_factory import select_extractors
from josseph.pipeline.run_report import RunReportCollector
from josseph.pipeline.results import ResultDirectoryManager, ResultWriter
from josseph.pipeline.runner import AnalysisRunner
from josseph.process import SubprocessCommandRunner
from josseph.utils import PROJECTS_DIR, RESULTS_DIR, THIRD_PARTY_DIR, setup_logging


class RepositoryAnalysisPipeline:
    def __init__(self) -> None:
        self.log = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def run(self, args) -> int:
        setup_logging()
        try:
            config = build_config(args)
        except (FileNotFoundError, ValueError):
            self.log.exception("Failed to load pipeline configuration")
            return 2

        self.log.info("Loaded configuration from %s", config.config_path)
        run_reporter = RunReportCollector(config=config, results_dir=RESULTS_DIR)
        exit_code = 1
        try:
            repos = config.repositories
            if not repos:
                self.log.info("No repositories to process.")
                exit_code = 0
                return 0

            if config.workers < 1:
                raise ValueError("'workers' must be a positive integer")

            env = dict(os.environ)
            if config.github_token:
                env["GITHUB_TOKEN"] = config.github_token
            command_runner = SubprocessCommandRunner()
            try:
                registry = self._build_registry(
                    env,
                    command_runner,
                    extractor_settings=config.extractor_settings,
                )
                extractors = select_extractors(registry, config.tools)
            except (FileNotFoundError, ValueError):
                self.log.exception("Failed to prepare pipeline runtime")
                exit_code = 2
                return 2

            analyzer = RepositoryAnalyzer(
                cloner=RepositoryCloner(PROJECTS_DIR, command_runner),
                result_manager=ResultDirectoryManager(RESULTS_DIR),
                result_writer=ResultWriter(),
                extractors=extractors,
                command_runner=command_runner,
                run_reporter=run_reporter,
            )
            failures = AnalysisRunner().run(
                repos,
                analyzer,
                config.clone_depth,
                config.workers,
                run_reporter=run_reporter,
            )
            if failures:
                self.log.error(
                    "%s repositories failed to analyse. See logs above for details.",
                    failures,
                )
                exit_code = 1
            else:
                exit_code = 0
            return exit_code
        finally:
            summary_path = run_reporter.write_summary(exit_code=exit_code)
            self.log.info("Wrote pipeline run summary to %s", summary_path)

    def _build_registry(
        self,
        env: dict[str, str],
        command_runner: SubprocessCommandRunner,
        *,
        extractor_settings: dict[str, dict[str, object]],
    ) -> ExtractorRegistry:
        return ExtractorRegistry(
            ExtractorFactoryContext(
                third_party_path=THIRD_PARTY_DIR,
                env=env,
                command_runner=command_runner,
            ),
            settings_by_name=extractor_settings,
        )
