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
    def parse(cls, value: str) -> RepositoryRef:
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
class RepositorySpec:
    """Runtime repository input including an optional pinned revision."""

    repository: RepositoryRef
    requested_commit_hash: str | None = None

    @classmethod
    def from_url(
        cls,
        value: str,
        *,
        requested_commit_hash: str | None = None,
    ) -> RepositorySpec:
        return cls(
            repository=RepositoryRef.parse(value),
            requested_commit_hash=_normalize_commit_hash(requested_commit_hash),
        )

    @classmethod
    def coerce(cls, value: str | RepositorySpec) -> RepositorySpec:
        if isinstance(value, RepositorySpec):
            return value
        return cls.from_url(value)

    @property
    def repo_url(self) -> str:
        return self.repository.raw

    @property
    def project_name(self) -> str:
        return self.repository.project_name

    def to_report_dict(self) -> dict[str, object]:
        return {
            "repo_url": self.repo_url,
            "requested_commit_hash": self.requested_commit_hash,
        }

    def matches_resolved_commit(self, resolved_commit_hash: str) -> bool:
        if self.requested_commit_hash is None:
            return True
        return (
            resolved_commit_hash == self.requested_commit_hash
            or resolved_commit_hash.startswith(self.requested_commit_hash)
        )


@dataclass(frozen=True)
class AnalysisTarget:
    """Target passed to metric extractors."""

    repository: RepositoryRef
    requested_commit_hash: str | None = None
    checkout_path: Path | None = None
    commit_hash: str | None = None

    @property
    def project_name(self) -> str:
        return self.repository.project_name

    @property
    def repo_slug(self) -> str:
        return self.repository.slug

    def with_checkout(self, checkout_path: Path, commit_hash: str) -> AnalysisTarget:
        return replace(self, checkout_path=checkout_path, commit_hash=commit_hash)


def _normalize_commit_hash(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
