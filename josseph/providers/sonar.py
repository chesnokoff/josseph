from __future__ import annotations

import json
import logging
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode

from josseph.utils import AnalysisError
from josseph.utils import retry_http_request


class SonarClient:
    request_timeout_seconds = 30
    max_retries = 3
    initial_retry_backoff_seconds = 1.0

    def __init__(
        self,
        *,
        host_url: str,
        admin_user: str,
        admin_password: str,
        admin_default_password: str,
    ) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.host_url = host_url
        self.admin_user = admin_user
        self.admin_password = admin_password
        self.admin_default_password = admin_default_password

    def wait_for_status(self, expected: str, timeout: int) -> None:
        start_time = time.time()
        last_status = ""
        while time.time() - start_time < timeout:
            last_status = self.get_system_status()
            if last_status == expected:
                return
            time.sleep(1)
        raise AnalysisError(
            f"SonarQube did not reach status {expected} in {timeout} seconds "
            f"(last status: {last_status or 'unknown'})."
        )

    def get_system_status(self) -> str:
        response = self.request_json("GET", "/api/system/status")
        return response.get("status", "")

    def ensure_admin_password(self) -> None:
        try:
            self.request(
                "POST",
                "/api/users/change_password",
                auth=(self.admin_user, self.admin_default_password),
                data={
                    "login": self.admin_user,
                    "previousPassword": self.admin_default_password,
                    "password": self.admin_password,
                },
            )
        except AnalysisError as exc:
            if self._password_is_already_configured(exc):
                self.log.debug("SonarQube admin password is already configured.")
                return
            raise

    def create_project(self, project_key: str, project_name: str) -> bool:
        try:
            self.request(
                "POST",
                "/api/projects/create",
                auth=(self.admin_user, self.admin_password),
                params={"name": project_name, "project": project_key},
            )
            return True
        except AnalysisError as exc:
            if self._project_already_exists(exc):
                self.log.debug("SonarQube project %s already exists.", project_key)
                return False
            raise

    def generate_token(self) -> str:
        response = self.request_json(
            "POST",
            "/api/user_tokens/generate",
            auth=(self.admin_user, self.admin_password),
            params={"name": str(int(time.time() * 1_000_000))},
        )
        token = response.get("token")
        if not token:
            raise AnalysisError("Failed to generate SonarQube token.")
        return token

    def wait_for_analysis(self, project_key: str, timeout: int = 120) -> None:
        start_time = time.time()
        last_status = ""
        while time.time() - start_time < timeout:
            response = self.request_json(
                "GET",
                "/api/qualitygates/project_status",
                auth=(self.admin_user, self.admin_password),
                params={"projectKey": project_key},
            )
            last_status = response.get("projectStatus", {}).get("status", "")
            if last_status and last_status != "NONE":
                return
            time.sleep(1)
        raise AnalysisError(
            f"Timed out waiting for SonarQube analysis to finish for {project_key} "
            f"(last status: {last_status or 'unknown'})."
        )

    def fetch_metrics(self, project_key: str) -> dict[str, object]:
        metrics_payload = self.request_json(
            "GET",
            "/api/metrics/search",
            auth=(self.admin_user, self.admin_password),
        )
        metrics = [metric["key"] for metric in metrics_payload.get("metrics", []) if "key" in metric]
        if not metrics:
            raise AnalysisError("Failed to fetch metrics list from SonarQube.")

        measures: list[dict[str, object]] = []
        batch_size = 30
        for start in range(0, len(metrics), batch_size):
            batch = ",".join(metrics[start:start + batch_size])
            response = self.request_json(
                "GET",
                "/api/measures/component",
                auth=(self.admin_user, self.admin_password),
                params={"component": project_key, "metricKeys": batch},
            )
            measures.extend(response.get("component", {}).get("measures", []))
        return {"project": project_key, "measures": measures}

    def delete_project(self, project_key: str) -> None:
        self.request(
            "POST",
            "/api/projects/delete",
            auth=(self.admin_user, self.admin_password),
            params={"project": project_key},
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        auth: tuple[str, str] | None = None,
        params: dict | None = None,
        data: dict | None = None,
        timeout: int | float | None = None,
        max_retries: int | None = None,
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
        request_timeout = self.request_timeout_seconds if timeout is None else timeout
        retries = self.max_retries if max_retries is None else max_retries
        def perform_request() -> bytes:
            with urllib.request.urlopen(request, timeout=request_timeout) as response:
                return response.read()

        try:
            return retry_http_request(
                url=url,
                request_name="SonarQube request",
                logger=self.log,
                max_retries=retries,
                initial_backoff_seconds=self.initial_retry_backoff_seconds,
                request=perform_request,
                should_retry_http_error=self._should_retry_http_error,
                retry_delay=self._retry_delay,
                is_retryable_url_error=self._is_retryable_url_error,
            )
        except urllib.error.HTTPError as exc:
            raise AnalysisError(self._format_http_error(url, exc)) from exc
        except urllib.error.URLError as exc:
            raise AnalysisError(f"Failed to reach SonarQube at {url}: {exc}") from exc

    def request_json(
        self,
        method: str,
        path: str,
        *,
        auth: tuple[str, str] | None = None,
        params: dict | None = None,
        data: dict | None = None,
    ) -> dict:
        raw = self.request(method, path, auth=auth, params=params, data=data)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"Invalid JSON response from {path}: {exc}") from exc

    def _build_url(self, path: str, params: dict | None = None) -> str:
        base = self.host_url
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

    @staticmethod
    def _password_is_already_configured(exc: AnalysisError) -> bool:
        message = str(exc).lower()
        return (
            "http error 401" in message
            or "previous password" in message
            or "not authorized" in message
        )

    @staticmethod
    def _project_already_exists(exc: AnalysisError) -> bool:
        message = str(exc).lower()
        return "already exists" in message or "could not create project" in message

    @staticmethod
    def _should_retry_http_error(exc: urllib.error.HTTPError) -> bool:
        return exc.code in {429, 500, 502, 503, 504}

    @staticmethod
    def _retry_delay(exc: urllib.error.HTTPError, fallback: float) -> float:
        retry_after = exc.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return max(int(retry_after), int(fallback))
        return fallback

    @staticmethod
    def _is_retryable_url_error(exc: urllib.error.URLError) -> bool:
        reason = exc.reason
        return isinstance(reason, (TimeoutError, socket.timeout)) or getattr(
            reason,
            "__class__",
            None,
        ).__name__ in {"TimeoutError", "ConnectionResetError", "BrokenPipeError"}

    @staticmethod
    def _format_http_error(url: str, exc: urllib.error.HTTPError) -> str:
        body = exc.read().decode("utf-8", errors="ignore").strip()
        details = f": {body}" if body else ""
        return f"HTTP error {exc.code} for {url}{details}"
