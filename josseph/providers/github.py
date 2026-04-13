from __future__ import annotations

import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from josseph.domain.repository import RepositoryRef
from josseph.utils import AnalysisError
from josseph.utils import create_ssl_context
from josseph.utils import retry_http_request


class GithubClient:
    request_timeout_seconds = 30
    max_retries = 3

    def __init__(self, token: str | None = None) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._token = token

    def get_repo(self, slug: str) -> dict:
        return self._request_json(f"/repos/{slug}")

    @staticmethod
    def extract_repo_slug(repo: str) -> str:
        """Return the <owner>/<repo> slug for a GitHub repository reference."""
        return RepositoryRef.parse(repo).slug

    def _request_json(
        self,
        path: str,
        params: dict[str, str] | None = None,
        *,
        max_retries: int | None = None,
    ) -> dict:
        query = f"?{urlencode(params)}" if params else ""
        url = f"https://api.github.com{path}{query}"
        headers = {"User-Agent": "josseph-pipeline"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        retries = self.max_retries if max_retries is None else max_retries
        ssl_context = create_ssl_context()
        request_name = "GitHub API request"

        def perform_request() -> dict:
            request = Request(url, headers=headers)
            with urlopen(  # noqa: S310
                request,
                context=ssl_context,
                timeout=self.request_timeout_seconds,
            ) as response:
                payload = response.read().decode("utf-8")
                try:
                    return json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise AnalysisError(
                        f"Invalid JSON response from GitHub API at {url}: {exc}"
                    ) from exc

        try:
            return retry_http_request(
                url=url,
                request_name=request_name,
                logger=self.log,
                max_retries=retries,
                initial_backoff_seconds=2.0,
                request=perform_request,
                should_retry_http_error=self._should_retry_http_error,
                retry_delay=self._retry_delay,
                is_retryable_url_error=self._is_retryable_url_error,
            )
        except HTTPError as exc:
            raise AnalysisError(self._format_http_error(url, exc)) from exc
        except URLError as exc:
            if getattr(exc.reason, "__class__", None).__name__ == "SSLCertVerificationError":
                raise AnalysisError(
                    "GitHub API request failed due to SSL certificate verification. "
                    "Install the 'certifi' package or configure your system trust store."
                ) from exc
            raise AnalysisError(f"Failed to reach GitHub API at {url}: {exc}") from exc

    @staticmethod
    def _should_retry_http_error(exc: HTTPError) -> bool:
        if exc.code in {429, 500, 502, 503, 504}:
            return True
        if exc.code != 403:
            return False
        return exc.headers.get("X-RateLimit-Remaining") == "0" or bool(
            exc.headers.get("X-RateLimit-Reset")
        )

    @staticmethod
    def _retry_delay(exc: HTTPError, fallback: float) -> float:
        reset = exc.headers.get("X-RateLimit-Reset")
        if reset and reset.isdigit():
            return max(int(reset) - int(time.time()), int(fallback))
        retry_after = exc.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return max(int(retry_after), int(fallback))
        return fallback

    @staticmethod
    def _is_retryable_url_error(exc: URLError) -> bool:
        reason_name = getattr(exc.reason, "__class__", None).__name__
        return reason_name in {"TimeoutError", "Timeout", "OSError"}

    @staticmethod
    def _format_http_error(url: str, exc: HTTPError) -> str:
        body = exc.read().decode("utf-8", errors="ignore").strip()
        details = f": {body}" if body else ""
        return f"GitHub API request to {url} failed with HTTP {exc.code}{details}"
