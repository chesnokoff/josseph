import logging
from urllib.error import HTTPError, URLError

from josseph.domain.repository import AnalysisTarget
from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.providers.github import GithubClient


class GithubExtractor(MetricExtractor):
    """Collect GitHub metadata without a local checkout."""

    requires_checkout = False

    def __init__(self, *, client: GithubClient) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.client = client

    def run(self, target: AnalysisTarget) -> list[dict[str, object]]:
        slug = target.repo_slug

        try:
            repo_data = self.client.get_repo(slug)
        except (HTTPError, RuntimeError, URLError) as exc:
            self.log.warning(f"Failed to fetch repository metadata for {slug}: {exc}")
            return []

        metrics = self._format_repo_metrics(repo_data, slug)

        topics = repo_data.get("topics") or []
        value = ",".join(topics) if topics else ""
        metrics["topics"] = value

        return [metrics]

    def _format_repo_metrics(self, repo_data: dict, slug: str) -> dict[str, object]:
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
