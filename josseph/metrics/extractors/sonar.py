from __future__ import annotations

import json
import logging
import os
import shlex
import tempfile
import time
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from pathlib import Path

from josseph.metrics.extractor import ExtractorConfig, MetricExtractor, extractor
from josseph.utils import AnalysisError, run_command


@extractor("sonar")
class SonarExtractor(MetricExtractor):
    """Collect SonarQube metrics for a repository."""

    def __init__(self, cfg: ExtractorConfig) -> None:
        super().__init__(cfg)

        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        env = self.cfg.env or os.environ
        self.sonar_instance_port = env.get("SONAR_INSTANCE_PORT", "9234")
        self.sonar_host_url = env.get("SONAR_HOST_URL", f"http://localhost:{self.sonar_instance_port}")
        self.sonar_admin_user = env.get("SONAR_ADMIN_USER", "admin")
        self.sonar_admin_password = env.get("SONAR_ADMIN_PASSWORD", "Son@rless123")
        self.sonar_admin_default_password = env.get("SONAR_ADMIN_DEFAULT_PASSWORD", "admin")
        self.sonar_empty_binaries_dir = env.get("SONAR_EMPTY_BINARIES_DIR", ".sonar-empty-binaries")
        self.sonar_options = self._normalize_sonar_options(env.get("SONAR_OPTIONS", ""))

    def run(self, repo_path: Path, project_name: str) -> list[dict[str, str]]:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)

            env = dict(self.cfg.env or os.environ)
            safe_project_name = str(project_name).replace("@", "_")
            sonar_project_key = safe_project_name
            sonar_metrics_path = temp_dir / "sonar-metrics.json"

            try:
                self._wait_for_status("UP", timeout=180)
                self._ensure_admin_password()
                self._create_project(sonar_project_key, safe_project_name)
                token = self._generate_token()
                self._run_scanner(env, repo_path, sonar_project_key, token)
                self._wait_for_analysis(sonar_project_key)
                metrics = self._fetch_metrics(sonar_project_key)
                sonar_metrics_path.write_text(json.dumps(metrics, ensure_ascii=False), encoding="utf-8")
            except Exception as exc:
                raise AnalysisError(f"Sonar scan failed for {repo_path}: {exc}") from exc
            finally:
                try:
                    self._delete_project(sonar_project_key)
                except Exception as exc:
                    self.log.warning("Failed to cleanup project %s: %s", sonar_project_key, exc)

            if not sonar_metrics_path.exists():
                raise AnalysisError(f"Metrics file not found: {sonar_metrics_path}")

            return [self._convert_sonar_json(sonar_metrics_path)]

    def _normalize_sonar_options(self, sonar_options: str) -> str:
        default_option = f"-Dsonar.java.binaries={self.sonar_empty_binaries_dir}"
        if not sonar_options.strip():
            return default_option
        if "sonar.java.binaries=" in sonar_options:
            return sonar_options
        return f"{sonar_options} {default_option}"

    def _wait_for_status(self, expected: str, timeout: int) -> None:
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self._get_system_status()
            if status == expected:
                return
            time.sleep(1)
        raise AnalysisError(f"SonarQube did not reach status {expected} in {timeout} seconds.")

    def _get_system_status(self) -> str:
        response = self._request_json("GET", "/api/system/status")
        return response.get("status", "")

    def _ensure_admin_password(self) -> None:
        try:
            self._request(
                "POST",
                "/api/users/change_password",
                auth=(self.sonar_admin_user, self.sonar_admin_default_password),
                data={
                    "login": self.sonar_admin_user,
                    "previousPassword": self.sonar_admin_default_password,
                    "password": self.sonar_admin_password,
                },
            )
        except AnalysisError:
            return

    def _create_project(self, project_key: str, project_name: str) -> None:
        try:
            self._request(
                "POST",
                "/api/projects/create",
                auth=(self.sonar_admin_user, self.sonar_admin_password),
                params={"name": project_name, "project": project_key},
            )
        except AnalysisError:
            return

    def _generate_token(self) -> str:
        response = self._request_json(
            "POST",
            "/api/user_tokens/generate",
            auth=(self.sonar_admin_user, self.sonar_admin_password),
            params={"name": str(int(time.time() * 1_000_000))},
        )
        token = response.get("token")
        if not token:
            raise AnalysisError("Failed to generate SonarQube token.")
        return token

    def _run_scanner(self, env: dict[str, str], repo_path: Path, project_key: str, token: str) -> None:
        binaries_dir = repo_path / self.sonar_empty_binaries_dir
        binaries_dir.mkdir(parents=True, exist_ok=True)
        scanner_command = [
            "sonar-scanner",
            f"-Dsonar.projectKey={project_key}",
            "-Dsonar.sources=.",
            f"-Dsonar.host.url={self.sonar_host_url}",
            f"-Dsonar.login={token}",
            *shlex.split(self.sonar_options),
        ]
        try:
            run_command(scanner_command, env=env, cwd=repo_path)
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

    def _wait_for_analysis(self, project_key: str, timeout: int = 120) -> None:
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self._request_json(
                "GET",
                "/api/qualitygates/project_status",
                auth=(self.sonar_admin_user, self.sonar_admin_password),
                params={"projectKey": project_key},
            )
            status = response.get("projectStatus", {}).get("status")
            if status and status != "NONE":
                return
            time.sleep(1)
        raise AnalysisError("Timed out waiting for SonarQube analysis to finish.")

    def _fetch_metrics(self, project_key: str) -> dict[str, object]:
        metrics_payload = self._request_json(
            "GET",
            "/api/metrics/search",
            auth=(self.sonar_admin_user, self.sonar_admin_password),
        )
        metrics = [metric["key"] for metric in metrics_payload.get("metrics", []) if "key" in metric]
        if not metrics:
            raise AnalysisError("Failed to fetch metrics list from SonarQube.")
        measures = []
        batch_size = 30
        for start in range(0, len(metrics), batch_size):
            batch = ",".join(metrics[start:start + batch_size])
            response = self._request_json(
                "GET",
                "/api/measures/component",
                auth=(self.sonar_admin_user, self.sonar_admin_password),
                params={"component": project_key, "metricKeys": batch},
            )
            measures.extend(response.get("component", {}).get("measures", []))
        return {"project": project_key, "measures": measures}

    def _delete_project(self, project_key: str) -> None:
        self._request(
            "POST",
            "/api/projects/delete",
            auth=(self.sonar_admin_user, self.sonar_admin_password),
            params={"project": project_key},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        auth: tuple[str, str] | None = None,
        params: dict | None = None,
        data: dict | None = None,
    ) -> bytes:
        url = self._build_url(path, params)
        headers: dict[str, str] = {}
        if auth is not None:
            headers.update(self._auth_headers(auth))
        payload = None
        if data is not None:
            payload = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(url, method=method, headers=headers, data=payload)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise AnalysisError(f"HTTP error {exc.code} for {url}: {exc.read().decode('utf-8', errors='ignore')}") from exc
        except urllib.error.URLError as exc:
            raise AnalysisError(f"Failed to reach SonarQube at {url}: {exc}") from exc

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        auth: tuple[str, str] | None = None,
        params: dict | None = None,
        data: dict | None = None,
    ) -> dict:
        raw = self._request(method, path, auth=auth, params=params, data=data)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"Invalid JSON response from {path}: {exc}") from exc

    def _build_url(self, path: str, params: dict | None = None) -> str:
        base = self.sonar_host_url
        if not base.endswith("/"):
            base = f"{base}/"
        url = urllib.parse.urljoin(base, path.lstrip("/"))
        if params:
            query = urllib.parse.urlencode(params)
            return f"{url}?{query}"
        return url

    def _auth_headers(self, auth: tuple[str, str]) -> dict[str, str]:
        user, password = auth
        token = b64encode(f"{user}:{password}".encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {token}"}

    def _convert_sonar_json(self, metrics_path: Path) -> dict[str, str]:
        metrics_path = metrics_path.resolve()

        if not metrics_path.exists():
            raise AnalysisError(f"Metrics file not found: {metrics_path}")

        try:
            data = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"Invalid JSON in {metrics_path}: {exc}") from exc

        measures = data.get("measures", [])

        result = {}
        for measure in measures:
            key = measure.get("metric")
            value = measure.get("value")
            if not key:
                continue
            result[key] = value

        return result
