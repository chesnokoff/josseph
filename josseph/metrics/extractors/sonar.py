from __future__ import annotations

import logging
import re
import shlex
import subprocess
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from josseph.domain.repository import AnalysisTarget
from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.metrics.registry import ExtractorFactoryContext
from josseph.process import (
    CommandExecutionError,
    CommandRunner,
    clean_command_stream,
    describe_command_failure,
)
from josseph.providers.sonar import SonarClient
from josseph.utils import AnalysisError

EXTRACTOR_NAME = "sonar"


@dataclass(frozen=True)
class SonarScannerSettings:
    host_url: str
    environment: dict[str, str]
    empty_binaries_dir: str
    exclusions: str
    include_frontend: bool
    options: str

    @classmethod
    def from_env(cls, env: dict[str, str]) -> SonarScannerSettings:
        instance_port = env.get("SONAR_INSTANCE_PORT", "9234")
        host_url = env.get("SONAR_HOST_URL", f"http://localhost:{instance_port}")
        empty_binaries_dir = env.get("SONAR_EMPTY_BINARIES_DIR", ".sonar-empty-binaries")
        exclusions = env.get("SONAR_EXCLUSIONS", SonarExtractor.DEFAULT_SONAR_EXCLUSIONS)
        include_frontend = str(env.get("SONAR_INCLUDE_FRONTEND", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        options = _normalize_sonar_options(
            raw_options=env.get("SONAR_OPTIONS", ""),
            empty_binaries_dir=empty_binaries_dir,
            exclusions=exclusions,
            include_frontend=include_frontend,
        )
        return cls(
            host_url=host_url,
            environment=dict(env),
            empty_binaries_dir=empty_binaries_dir,
            exclusions=exclusions,
            include_frontend=include_frontend,
            options=options,
        )


class SonarScanner:
    def __init__(self, *, command_runner: CommandRunner, settings: SonarScannerSettings) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._command_runner = command_runner
        self._settings = settings

    def run(self, repo_path: Path, project_key: str, token: str) -> None:
        binaries_dir = repo_path / self._settings.empty_binaries_dir
        binaries_dir.mkdir(parents=True, exist_ok=True)
        scanner_command = [
            "sonar-scanner",
            f"-Dsonar.projectKey={project_key}",
            "-Dsonar.sources=.",
            f"-Dsonar.host.url={self._settings.host_url}",
            f"-Dsonar.login={token}",
            *shlex.split(self._settings.options),
        ]
        try:
            output = self._command_runner.run(
                scanner_command,
                env=self._settings.environment,
                cwd=repo_path,
            )
        except AnalysisError:
            raise
        except (
            CommandExecutionError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as exc:
            raise AnalysisError(
                describe_command_failure("sonar-scanner", scanner_command, exc)
            ) from exc
        except Exception as exc:
            raise AnalysisError(f"sonar-scanner failed: {exc}") from exc

        if output:
            self.log.log(
                5,
                "sonar-scanner output for %s:\n%s",
                repo_path,
                clean_command_stream(output).strip(),
            )


class SonarExtractor(MetricExtractor):
    """Collect SonarQube metrics for a repository."""

    DEFAULT_SONAR_EXCLUSIONS = ",".join(
        [
            "**/*.js",
            "**/*.jsx",
            "**/*.ts",
            "**/*.tsx",
            "**/*.css",
            "**/*.scss",
            "**/*.sass",
            "**/*.less",
            "**/*.vue",
            "**/*.svelte",
            "**/node_modules/**",
            "**/dist/**",
            "**/build/**",
            "**/.next/**",
            "**/.nuxt/**",
        ]
    )

    def __init__(
        self,
        *,
        client: SonarClient,
        scanner: SonarScanner,
        concurrency_semaphore: threading.Semaphore | None = None,
    ) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.client = client
        self._scanner = scanner
        self._semaphore = concurrency_semaphore

    def run(self, target: AnalysisTarget) -> list[dict[str, object]]:
        if self._semaphore is not None:
            self._semaphore.acquire()
        try:
            return self._run_scan(target)
        finally:
            if self._semaphore is not None:
                self._semaphore.release()

    def _run_scan(self, target: AnalysisTarget) -> list[dict[str, object]]:
        repo_path = _require_checkout(target)
        sonar_project_key = _build_sonar_project_key(target)
        created_project = False

        try:
            self.client.wait_for_status("UP", timeout=180)
            self.client.ensure_admin_password()
            created_project = self.client.create_project(
                sonar_project_key,
                target.project_name,
            )
            if not created_project:
                raise AnalysisError(
                    f"Refusing to reuse pre-existing SonarQube project {sonar_project_key} "
                    f"for {target.project_name}."
                )
            token = self.client.generate_token()
            self._scanner.run(repo_path, sonar_project_key, token)
            self.client.wait_for_analysis(sonar_project_key)
            metrics = self.client.fetch_metrics(sonar_project_key)
        except Exception as exc:
            raise AnalysisError(f"Sonar scan failed for {repo_path}: {exc}") from exc
        finally:
            if created_project:
                try:
                    self.client.delete_project(sonar_project_key)
                except Exception as exc:
                    self.log.warning("Failed to cleanup project %s: %s", sonar_project_key, exc)

        return [self._convert_sonar_metrics(metrics)]

    def _convert_sonar_metrics(self, data: dict[str, object]) -> dict[str, object]:
        raw_measures = data.get("measures", [])
        if not isinstance(raw_measures, list):
            return {}

        result: dict[str, object] = {}
        for measure in raw_measures:
            if not isinstance(measure, dict):
                continue
            key = measure.get("metric")
            value = measure.get("value")
            if not isinstance(key, str) or not key:
                continue
            result[key] = "" if value is None else str(value)

        return result


def _normalize_sonar_options(
    *,
    raw_options: str,
    empty_binaries_dir: str,
    exclusions: str,
    include_frontend: bool,
) -> str:
    options = shlex.split(raw_options) if raw_options.strip() else []
    if not any("sonar.java.binaries=" in option for option in options):
        options.append(f"-Dsonar.java.binaries={empty_binaries_dir}")
    if (
        not include_frontend
        and exclusions.strip()
        and not any("sonar.exclusions=" in option for option in options)
    ):
        options.append(f"-Dsonar.exclusions={exclusions}")
    return " ".join(options)


def _require_checkout(target: AnalysisTarget) -> Path:
    if target.checkout_path is None:
        raise AnalysisError("Sonar extractor requires a local repository checkout.")
    return target.checkout_path


def _build_sonar_project_key(target: AnalysisTarget) -> str:
    base_name = re.sub(r"[^A-Za-z0-9._:-]+", "_", target.project_name.replace("@", "_"))
    commit_part = (target.commit_hash or "workspace")[:12]
    return f"{base_name}_{commit_part}_{uuid4().hex[:8]}"


def build_extractor(
    context: ExtractorFactoryContext,
    settings: dict[str, object],
) -> SonarExtractor:
    env = _build_sonar_environment(context.env, settings)
    host_url = env.get(
        "SONAR_HOST_URL",
        f"http://localhost:{env.get('SONAR_INSTANCE_PORT', '9234')}",
    )
    sonar_client = SonarClient(
        host_url=host_url,
        admin_user=env.get("SONAR_ADMIN_USER", "admin"),
        admin_password=env.get("SONAR_ADMIN_PASSWORD", "admin"),
        admin_default_password=env.get("SONAR_ADMIN_DEFAULT_PASSWORD", "admin"),
    )
    sonar_scanner = SonarScanner(
        command_runner=context.command_runner,
        settings=SonarScannerSettings.from_env(env),
    )
    concurrency_limit = _parse_concurrency(env.get("SONAR_CONCURRENCY", "1"))
    semaphore = threading.Semaphore(concurrency_limit)
    return SonarExtractor(
        client=sonar_client,
        scanner=sonar_scanner,
        concurrency_semaphore=semaphore,
    )


def _parse_concurrency(value: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 1
    return max(n, 1)


def _build_sonar_environment(
    base_env: dict[str, str] | Mapping[str, str],
    settings: dict[str, object],
) -> dict[str, str]:
    supported = {
        "instance_port": "SONAR_INSTANCE_PORT",
        "host_url": "SONAR_HOST_URL",
        "admin_user": "SONAR_ADMIN_USER",
        "admin_password": "SONAR_ADMIN_PASSWORD",
        "admin_default_password": "SONAR_ADMIN_DEFAULT_PASSWORD",
        "empty_binaries_dir": "SONAR_EMPTY_BINARIES_DIR",
        "exclusions": "SONAR_EXCLUSIONS",
        "include_frontend": "SONAR_INCLUDE_FRONTEND",
        "options": "SONAR_OPTIONS",
        "concurrency": "SONAR_CONCURRENCY",
    }
    unknown = sorted(set(settings) - set(supported))
    if unknown:
        unknown_list = ", ".join(unknown)
        raise ValueError(f"Unknown setting(s) for extractor 'sonar': {unknown_list}")

    env = dict(base_env)
    for setting_name, env_name in supported.items():
        if setting_name not in settings:
            continue
        value = settings[setting_name]
        if isinstance(value, bool):
            env[env_name] = "true" if value else "false"
        else:
            env[env_name] = str(value)
    return env
