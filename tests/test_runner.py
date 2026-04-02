from __future__ import annotations

from threading import Lock

from josseph.domain.repository import RepositorySpec
from josseph.pipeline.runner import AnalysisRunner


class RecordingAnalyzer:
    def __init__(self, failing_repo: str):
        self.failing_repo = failing_repo
        self.calls = []
        self._lock = Lock()

    def analyze(self, repo):
        with self._lock:
            self.calls.append(repo)
        if repo.repo_url == self.failing_repo:
            raise RuntimeError("boom")


class RecordingRunReporter:
    def __init__(self):
        self.failures = []

    def record_repository_failure(self, *, repo_url, requested_commit_hash, reason):
        self.failures.append(
            {
                "repo_url": repo_url,
                "requested_commit_hash": requested_commit_hash,
                "reason": reason,
            }
        )


def test_analysis_runner_records_repository_failures(tmp_path):
    analyzer = RecordingAnalyzer("https://github.com/example/bad.git")
    run_reporter = RecordingRunReporter()

    failures = AnalysisRunner().run(
        [
            RepositorySpec.from_url("https://github.com/example/good.git"),
            RepositorySpec.from_url("https://github.com/example/bad.git"),
        ],
        analyzer,
        workers=1,
        run_reporter=run_reporter,
    )

    assert failures == 1
    assert analyzer.calls == [
        RepositorySpec.from_url("https://github.com/example/good.git"),
        RepositorySpec.from_url("https://github.com/example/bad.git"),
    ]
    assert run_reporter.failures == [
        {
            "repo_url": "https://github.com/example/bad.git",
            "requested_commit_hash": None,
            "reason": "RuntimeError: boom",
        }
    ]


def test_analysis_runner_supports_multiple_workers_without_order_assumptions():
    analyzer = RecordingAnalyzer("https://github.com/example/bad.git")
    run_reporter = RecordingRunReporter()
    repos = [
        RepositorySpec.from_url("https://github.com/example/good-a.git"),
        RepositorySpec.from_url("https://github.com/example/bad.git"),
        RepositorySpec.from_url("https://github.com/example/good-b.git"),
    ]

    failures = AnalysisRunner().run(
        repos,
        analyzer,
        workers=3,
        run_reporter=run_reporter,
    )

    assert failures == 1
    assert set(analyzer.calls) == {
        RepositorySpec.from_url("https://github.com/example/good-a.git"),
        RepositorySpec.from_url("https://github.com/example/bad.git"),
        RepositorySpec.from_url("https://github.com/example/good-b.git"),
    }
    assert run_reporter.failures == [
        {
            "repo_url": "https://github.com/example/bad.git",
            "requested_commit_hash": None,
            "reason": "RuntimeError: boom",
        }
    ]
