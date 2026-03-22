"""Repository list and naming helpers."""
from __future__ import annotations

from pathlib import Path

from josseph.domain.repository import RepositoryRef


def sanitize_repo_name(repo_url: str) -> str:
    """Convert a repository URL to <owner>@<repo>."""
    return RepositoryRef.parse(repo_url).project_name


def read_repositories(path: Path) -> list[str]:
    """Load repository URLs from a file, skipping comments and blanks."""
    if not path.exists():
        raise FileNotFoundError(f"Repository list {path} not found")

    repos: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        repos.append(line)
    return repos
