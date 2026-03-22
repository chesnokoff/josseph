from __future__ import annotations

import logging
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from josseph.domain.repository import AnalysisTarget
from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.process import CommandRunner
from josseph.providers.sonar import SonarClient
from josseph.utils import AnalysisError


@dataclass(frozen=True)
class SonarScannerSettings:
    host_url: str
    environment: dict[str, str]
    empty_binaries_dir: str
    exclusions: str
    include_frontend: bool
    options: str

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "SonarScannerSettings":
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
            self._command_runner.run(
                scanner_command,
                env=self._settings.environment,
                cwd=repo_path,
            )
        except subprocess.CalledProcessError as exc:
            stdout = (exc.stdout or "").strip()
            stderr = (exc.stderr or "").strip()
            details = "\n".join(part for part in (stdout, stderr) if part)
            if details:
                raise AnalysisError(
                    f"sonar-scanner failed with exit code {exc.returncode}:\n{details}"
                ) from exc
            raise AnalysisError(
                f"sonar-scanner failed with exit code {exc.returncode} and no output"
            ) from exc


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

    def __init__(self, *, client: SonarClient, scanner: SonarScanner) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.client = client
        self._scanner = scanner

    def run(self, target: AnalysisTarget) -> list[dict[str, str]]:
        repo_path = _require_checkout(target)
        sonar_project_key = target.project_name.replace("@", "_")

        try:
            self.client.wait_for_status("UP", timeout=180)
            self.client.ensure_admin_password()
            self.client.create_project(sonar_project_key, sonar_project_key)
            token = self.client.generate_token()
            self._scanner.run(repo_path, sonar_project_key, token)
            self.client.wait_for_analysis(sonar_project_key)
            metrics = self.client.fetch_metrics(sonar_project_key)
        except Exception as exc:
            raise AnalysisError(f"Sonar scan failed for {repo_path}: {exc}") from exc
        finally:
            try:
                self.client.delete_project(sonar_project_key)
            except Exception as exc:
                self.log.warning("Failed to cleanup project %s: %s", sonar_project_key, exc)

        return [self._convert_sonar_metrics(metrics)]

    def _convert_sonar_metrics(self, data: dict[str, object]) -> dict[str, str]:
        measures = data.get("measures", [])

        result = {}
        for measure in measures:
            key = measure.get("metric")
            value = measure.get("value")
            if not key:
                continue
            result[key] = value

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
