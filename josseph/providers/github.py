from __future__ import annotations

import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from josseph.domain.repository import RepositoryRef
from josseph.utils import create_ssl_context


class GithubClient:
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
        max_retries: int = 3,
    ) -> dict:
        query = f"?{urlencode(params)}" if params else ""
        url = f"https://api.github.com{path}{query}"
        headers = {"User-Agent": "oss-metrics-pipeline"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        backoff = 2.0
        ssl_context = create_ssl_context()
        for attempt in range(1, max_retries + 1):
            request = Request(url, headers=headers)
            try:
                with urlopen(request, context=ssl_context) as response:  # noqa: S310
                    payload = response.read().decode("utf-8")
                    return json.loads(payload)
            except HTTPError as exc:
                if exc.code == 403 and attempt < max_retries:
                    reset = exc.headers.get("X-RateLimit-Reset")
                    if reset and reset.isdigit():
                        wait_seconds = max(int(reset) - int(time.time()), int(backoff))
                    else:
                        wait_seconds = backoff
                    self.log.debug(
                        "GitHub API rate limit encountered on %s (attempt %s/%s), sleeping for %ss",
                        url,
                        attempt,
                        max_retries,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    backoff *= 2
                    continue
                raise
            except URLError as exc:
                if getattr(exc.reason, "__class__", None).__name__ == "SSLCertVerificationError":
                    raise RuntimeError(
                        "GitHub API request failed due to SSL certificate verification. "
                        "Install the 'certifi' package or configure your system trust store."
                    ) from exc
                raise
        raise RuntimeError(f"Unable to fetch {url} from GitHub API after {max_retries} attempts")
