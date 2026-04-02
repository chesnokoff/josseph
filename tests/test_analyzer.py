from __future__ import annotations

import json
from datetime import datetime, timezone

from josseph.domain.repository import RepositorySpec
from josseph.pipeline.analyzer import RepositoryAnalyzer
from josseph.pipeline.results import ResultDirectoryManager, ResultWriter
from josseph.utils import AnalysisError


class FakeCommandRunner:
    def run(self, cmd, *, cwd=None, env=None, timeout=None):
        assert list(cmd) == ["git", "rev-parse", "HEAD"]
        return "abc123\n"


class FakeCloner:
    def __init__(self, checkout_path):
        self.checkout_path = checkout_path
        self.cleaned = False

    def clone(self, repo_url):
        return self.checkout_path

    def cleanup(self, repo_path):
        self.cleaned = True


class CheckoutExtractor:
    requires_checkout = True
    metric_binding = "revision-bound"

    def __init__(self):
        self.targets = []

    def run(self, target):
        self.targets.append(target)
        return [{"metric": 1}]


class ApiExtractor:
    requires_checkout = False
    metric_binding = "observation-bound"

    def __init__(self):
        self.targets = []

    def run(self, target):
        self.targets.append(target)
        return [{"stars": 42}]


class FailingApiExtractor:
    requires_checkout = False
    metric_binding = "revision-bound"

    def run(self, target):
        raise AnalysisError("github api down")


class RecordingRunReporter:
    def __init__(self):
        self.failures = []

    def record_extractor_failure(
        self,
        *,
        repo_url,
        project_name,
        extractor_name,
        requested_commit_hash,
        metric_binding,
        reason,
    ):
        self.failures.append(
            {
                "repo_url": repo_url,
                "project_name": project_name,
                "extractor_name": extractor_name,
                "requested_commit_hash": requested_commit_hash,
                "metric_binding": metric_binding,
                "reason": reason,
            }
        )


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

    analyzer.analyze("https://github.com/example/repo.git")

    metadata_path = tmp_path / "results" / "example@repo" / "ck.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["commit_hash"] == "abc123"
    assert metadata["requested_commit_hash"] is None
    assert metadata["metric_binding"] == "revision-bound"
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

    analyzer.analyze("https://github.com/example/repo.git")

    target = api_extractor.targets[0]
    assert target.project_name == "example@repo"
    assert target.repo_slug == "example/repo"
    assert target.checkout_path is None
    assert target.commit_hash is None

    metadata_path = tmp_path / "results" / "example@repo" / "github.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["commit_hash"] == ""
    assert metadata["requested_commit_hash"] is None
    assert metadata["metric_binding"] == "observation-bound"
    assert datetime.fromisoformat(
        metadata["collected_at_utc"].replace("Z", "+00:00")
    ).tzinfo == timezone.utc


def test_repository_analyzer_records_extractor_failures_and_continues(tmp_path):
    ok_extractor = ApiExtractor()
    failing_extractor = FailingApiExtractor()
    reporter = RecordingRunReporter()
    analyzer = RepositoryAnalyzer(
        cloner=FakeCloner(tmp_path / "checkout"),
        result_manager=ResultDirectoryManager(tmp_path / "results"),
        result_writer=ResultWriter(),
        extractors={"github": ok_extractor, "sonar": failing_extractor},
        command_runner=FakeCommandRunner(),
        run_reporter=reporter,
    )

    analyzer.analyze("https://github.com/example/repo.git")

    result_dir = tmp_path / "results" / "example@repo"
    assert (result_dir / "github.parquet").is_file()
    assert (result_dir / "github.json").is_file()
    assert not (result_dir / "sonar.parquet").exists()
    assert reporter.failures == [
        {
            "repo_url": "https://github.com/example/repo.git",
            "project_name": "example@repo",
            "extractor_name": "sonar",
            "requested_commit_hash": None,
            "metric_binding": "revision-bound",
            "reason": "AnalysisError: github api down",
        }
    ]


def test_repository_analyzer_reuses_cache_only_for_matching_revision_commit(tmp_path):
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

    analyzer.analyze(
        RepositorySpec.from_url(
            "https://github.com/example/repo.git",
            requested_commit_hash="abc123",
        ),
    )
    assert len(extractor.targets) == 1

    analyzer.analyze(
        RepositorySpec.from_url(
            "https://github.com/example/repo.git",
            requested_commit_hash="abc123",
        ),
    )
    assert len(extractor.targets) == 1

    analyzer.analyze(
        RepositorySpec.from_url(
            "https://github.com/example/repo.git",
            requested_commit_hash="deadbeef",
        ),
    )
    assert len(extractor.targets) == 2
