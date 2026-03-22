import json
import logging
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from josseph.metrics.extractor import ExtractorConfig, MetricExtractor, extractor
from josseph.utils import create_ssl_context


@extractor("github")
class GithubMetrics(MetricExtractor):
    """Base class for all metric extraction tools."""

    def __init__(self, cfg: ExtractorConfig) -> None:
        super().__init__(cfg)

        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        self.token = cfg.env.get("GITHUB_TOKEN")

    def run(self, repo, project_name: str):
        """Collect metrics for the given repository path."""
        slug = self.__extract_github_slug(str(repo))

        try:
            repo_data = self.__github_api_request(f"/repos/{slug}")
        except (HTTPError, RuntimeError, URLError) as exc:
            self.log.warning(f"Failed to fetch repository metadata for {slug}: {exc}")
            return []

        metrics = self._format_repo_metrics(repo_data, slug)

        topics = repo_data.get("topics") or []
        value = ",".join(topics) if topics else ""
        metrics["topics"] = value

        return [metrics]

    def _format_repo_metrics(self, repo_data: dict, slug: str) -> dict[str, str]:
        mapping = {
            "full_name": repo_data.get("full_name", slug),
            "description": repo_data.get("description", ""),
            "default_branch": repo_data.get("default_branch", ""),
            "language": repo_data.get("language", ""),
            "license": (repo_data.get("license") or {}).get("spdx_id", ""),
            "homepage": repo_data.get("homepage", ""),
            "stargazers_count": repo_data.get("stargazers_count", 0),
            "watchers_count": repo_data.get("watchers_count", 0),
            "subscribers_count": repo_data.get("subscribers_count", 0),
            "forks_count": repo_data.get("forks_count", 0),
            "network_count": repo_data.get("network_count", 0),
            "open_issues_total": repo_data.get("open_issues_count", 0),
            "has_issues": repo_data.get("has_issues", False),
            "has_wiki": repo_data.get("has_wiki", False),
            "has_pages": repo_data.get("has_pages", False),
            "is_fork": repo_data.get("fork", False),
            "archived": repo_data.get("archived", False),
            "disabled": repo_data.get("disabled", False),
            "size_kb": repo_data.get("size", 0),
            "created_at": repo_data.get("created_at", ""),
            "updated_at": repo_data.get("updated_at", ""),
            "pushed_at": repo_data.get("pushed_at", ""),
        }
        return mapping

    def __github_api_request(self, path: str, params: dict[str, str] | None = None, max_retries: int = 3):
        query = f"?{urlencode(params)}" if params else ""
        url = f"https://api.github.com{path}{query}"
        headers = {"User-Agent": "oss-metrics-pipeline"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

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
                    self.log.debug(f"GitHub API rate limit encountered on {url} (attempt {attempt}/{max_retries}), sleeping for {wait_seconds}s",
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

    def __extract_github_slug(self, repo: str) -> str:
        """Return the <owner>/<repo> slug for a GitHub repository URL."""
        return os.path.basename(urlparse(repo).path.rstrip("/")).replace("@", "/", 1)
