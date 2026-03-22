"""Pipeline application entrypoint."""
from __future__ import annotations

import logging
import os

from josseph.metrics.extractors.ck import CkExtractor
from josseph.metrics.extractors.cm import CmExtractor
from josseph.metrics.extractors.github import GithubExtractor
from josseph.metrics.extractors.sonar import SonarExtractor, SonarScanner, SonarScannerSettings
from josseph.metrics.registry import ExtractorRegistry
from josseph.pipeline.analyzer import RepositoryAnalyzer
from josseph.pipeline.cloner import RepositoryCloner
from josseph.pipeline.config import build_config
from josseph.pipeline.extractor_factory import select_extractors
from josseph.pipeline.results import ResultDirectoryManager, ResultWriter
from josseph.pipeline.runner import AnalysisRunner
from josseph.process import SubprocessCommandRunner
from josseph.providers.github import GithubClient
from josseph.providers.sonar import SonarClient
from josseph.utils import PROJECTS_DIR, RESULTS_DIR, THIRD_PARTY_DIR, setup_logging


class RepositoryAnalysisPipeline:
    def __init__(self) -> None:
        self.log = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def run(self, args) -> int:
        setup_logging()

        config = build_config(args)
        self.log.info("Loaded configuration from %s", config.config_path)
        env = dict(os.environ)
        if config.github_token:
            env["GITHUB_TOKEN"] = config.github_token
        command_runner = SubprocessCommandRunner()
        registry = self._build_registry(env, command_runner)
        extractors = select_extractors(registry, config.tools)
        repos = config.repositories

        if not repos:
            self.log.info("No repositories to process.")
            return 0

        if config.workers < 1:
            raise ValueError("'workers' must be a positive integer")

        analyzer = RepositoryAnalyzer(
            cloner=RepositoryCloner(PROJECTS_DIR, command_runner),
            result_manager=ResultDirectoryManager(RESULTS_DIR),
            result_writer=ResultWriter(),
            extractors=extractors,
            command_runner=command_runner,
        )

        failures = AnalysisRunner().run(repos, analyzer, config.clone_depth, config.workers)
        if failures:
            self.log.error(
                "%s repositories failed to analyse. See logs above for details.",
                failures,
            )
            return 1
        return 0

    def _build_registry(
        self,
        env: dict[str, str],
        command_runner: SubprocessCommandRunner,
    ) -> ExtractorRegistry:
        github_client = GithubClient(token=env.get("GITHUB_TOKEN"))
        sonar_client = SonarClient(
            host_url=env.get("SONAR_HOST_URL", f"http://localhost:{env.get('SONAR_INSTANCE_PORT', '9234')}"),
            admin_user=env.get("SONAR_ADMIN_USER", "admin"),
            admin_password=env.get("SONAR_ADMIN_PASSWORD", "Son@rless123"),
            admin_default_password=env.get("SONAR_ADMIN_DEFAULT_PASSWORD", "admin"),
        )
        sonar_scanner = SonarScanner(
            command_runner=command_runner,
            settings=SonarScannerSettings.from_env(env),
        )
        cm_timeout_seconds = int(env.get("CM_TIMEOUT_SECONDS", "3600"))
        return ExtractorRegistry(
            {
                "ck": lambda: CkExtractor(
                    third_party_path=THIRD_PARTY_DIR,
                    command_runner=command_runner,
                ),
                "cm": lambda: CmExtractor(
                    third_party_path=THIRD_PARTY_DIR,
                    command_runner=command_runner,
                    timeout_seconds=cm_timeout_seconds,
                ),
                "github": lambda: GithubExtractor(client=github_client),
                "sonar": lambda: SonarExtractor(
                    client=sonar_client,
                    scanner=sonar_scanner,
                ),
            }
        )
