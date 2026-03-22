"""Repository domain models."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class RepositoryRef:
    """Canonical representation of a repository identifier."""

    raw: str
    owner: str
    name: str

    @classmethod
    def parse(cls, value: str) -> "RepositoryRef":
        raw = value.strip()
        if not raw:
            raise ValueError("Repository reference cannot be empty")

        parsed = urlparse(raw)
        path = parsed.path.strip("/") if parsed.scheme or parsed.netloc else raw.strip("/")
        if path.endswith(".git"):
            path = path[: -len(".git")]

        if "@" in path and "/" not in path:
            owner, name = path.split("@", 1)
        else:
            parts = [part for part in path.split("/") if part]
            if len(parts) < 2:
                raise ValueError(
                    f"Repository reference '{value}' must contain owner and repository name"
                )
            owner, name = parts[-2], parts[-1]

        if not owner or not name:
            raise ValueError(
                f"Repository reference '{value}' must contain owner and repository name"
            )
        return cls(raw=raw, owner=owner, name=name)

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def project_name(self) -> str:
        return f"{self.owner}@{self.name}"


@dataclass(frozen=True)
class AnalysisTarget:
    """Target passed to metric extractors."""

    repository: RepositoryRef
    checkout_path: Path | None = None
    commit_hash: str | None = None

    @property
    def project_name(self) -> str:
        return self.repository.project_name

    @property
    def repo_slug(self) -> str:
        return self.repository.slug

    def with_checkout(self, checkout_path: Path, commit_hash: str) -> "AnalysisTarget":
        return replace(self, checkout_path=checkout_path, commit_hash=commit_hash)
