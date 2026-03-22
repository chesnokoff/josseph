from __future__ import annotations

import json
from datetime import datetime, timezone

from josseph.pipeline.analyzer import RepositoryAnalyzer
from josseph.pipeline.results import ResultDirectoryManager, ResultWriter


class FakeCommandRunner:
    def run(self, cmd, *, cwd=None, env=None, timeout=None):
        assert list(cmd) == ["git", "rev-parse", "HEAD"]
        return "abc123\n"


class FakeCloner:
    def __init__(self, checkout_path):
        self.checkout_path = checkout_path
        self.cleaned = False

    def clone(self, repo_url, clone_depth):
        return self.checkout_path

    def cleanup(self, repo_path):
        self.cleaned = True


class CheckoutExtractor:
    requires_checkout = True

    def __init__(self):
        self.targets = []

    def run(self, target):
        self.targets.append(target)
        return [{"metric": 1}]


class ApiExtractor:
    requires_checkout = False

    def __init__(self):
        self.targets = []

    def run(self, target):
        self.targets.append(target)
        return [{"stars": 42}]


def test_repository_analyzer_persists_commit_hash_for_checkout_extractors(tmp_path):
    checkout_dir = tmp_path / "checkout"
    checkout_dir.mkdir()
    extractor = CheckoutExtractor()
    analyzer = RepositoryAnalyzer(
        cloner=FakeCloner(checkout_dir),
        result_manager=ResultDirectoryManager(tmp_path / "results"),
        result_writer=ResultWriter(),
        extractors={"ck": extractor},
        command_runner=FakeCommandRunner(),
    )

    analyzer.analyze("https://github.com/example/repo.git", clone_depth=1)

    metadata_path = tmp_path / "results" / "example@repo" / "ck.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["commit_hash"] == "abc123"
    assert datetime.fromisoformat(
        metadata["collected_at_utc"].replace("Z", "+00:00")
    ).tzinfo == timezone.utc
    assert extractor.targets[0].checkout_path == checkout_dir
    assert extractor.targets[0].commit_hash == "abc123"


def test_repository_analyzer_passes_domain_target_to_api_extractors(tmp_path):
    api_extractor = ApiExtractor()
    analyzer = RepositoryAnalyzer(
        cloner=FakeCloner(tmp_path / "checkout"),
        result_manager=ResultDirectoryManager(tmp_path / "results"),
        result_writer=ResultWriter(),
        extractors={"github": api_extractor},
        command_runner=FakeCommandRunner(),
    )

    analyzer.analyze("https://github.com/example/repo.git", clone_depth=None)

    target = api_extractor.targets[0]
    assert target.project_name == "example@repo"
    assert target.repo_slug == "example/repo"
    assert target.checkout_path is None
    assert target.commit_hash is None

    metadata_path = tmp_path / "results" / "example@repo" / "github.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["commit_hash"] == ""
    assert datetime.fromisoformat(
        metadata["collected_at_utc"].replace("Z", "+00:00")
    ).tzinfo == timezone.utc
