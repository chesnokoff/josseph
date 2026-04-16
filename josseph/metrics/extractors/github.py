import logging
from typing import Any

from josseph.domain.repository import AnalysisTarget
from josseph.metrics.abstract_extractor import MetricExtractor
from josseph.metrics.registry import ExtractorFactoryContext
from josseph.providers.github import GithubClient
from josseph.utils import AnalysisError

EXTRACTOR_NAME = "github"


class GithubExtractor(MetricExtractor):
    """Collect GitHub metadata without a local checkout."""

    requires_checkout = False
    metric_binding = "observation-bound"

    def __init__(self, *, client: GithubClient) -> None:
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.client = client

    def run(self, target: AnalysisTarget) -> list[dict[str, object]]:
        slug = target.repo_slug

        try:
            repo_data = self.client.get_repo(slug)
        except AnalysisError as exc:
            self.log.warning("Failed to fetch repository metadata for %s: %s", slug, exc)
            raise AnalysisError(f"Failed to fetch repository metadata for {slug}: {exc}") from exc
        except Exception as exc:
            self.log.warning("Failed to fetch repository metadata for %s: %s", slug, exc)
            raise AnalysisError(f"Failed to fetch repository metadata for {slug}: {exc}") from exc

        metrics = self._format_repo_metrics(repo_data, slug)

        topics = repo_data.get("topics") or []
        value = ",".join(topics) if topics else ""
        metrics["topics"] = value

        return [metrics]

    def _format_repo_metrics(self, repo_data: dict[str, Any], slug: str) -> dict[str, object]:
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


def build_extractor(
    context: ExtractorFactoryContext,
    settings: dict[str, object],
) -> GithubExtractor:
    allowed = {"token"}
    unknown = sorted(set(settings) - allowed)
    if unknown:
        unknown_list = ", ".join(unknown)
        raise ValueError(f"Unknown setting(s) for extractor 'github': {unknown_list}")

    token = settings.get("token", context.env.get("GITHUB_TOKEN"))
    if token is not None and not isinstance(token, str):
        raise ValueError("Extractor setting 'github.token' must be a string")

    return GithubExtractor(client=GithubClient(token=token))
