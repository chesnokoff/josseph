from __future__ import annotations

from threading import Lock

from josseph.pipeline.runner import AnalysisRunner


class RecordingAnalyzer:
    def __init__(self, failing_repo: str):
        self.failing_repo = failing_repo
        self.calls = []
        self._lock = Lock()

    def analyze(self, repo, clone_depth):
        with self._lock:
            self.calls.append((repo, clone_depth))
        if repo == self.failing_repo:
            raise RuntimeError("boom")


class RecordingRunReporter:
    def __init__(self):
        self.failures = []

    def record_repository_failure(self, *, repo_url, reason):
        self.failures.append({"repo_url": repo_url, "reason": reason})


def test_analysis_runner_records_repository_failures(tmp_path):
    analyzer = RecordingAnalyzer("https://github.com/example/bad.git")
    run_reporter = RecordingRunReporter()

    failures = AnalysisRunner().run(
        [
            "https://github.com/example/good.git",
            "https://github.com/example/bad.git",
        ],
        analyzer,
        clone_depth=7,
        workers=1,
        run_reporter=run_reporter,
    )

    assert failures == 1
    assert analyzer.calls == [
        ("https://github.com/example/good.git", 7),
        ("https://github.com/example/bad.git", 7),
    ]
    assert run_reporter.failures == [
        {
            "repo_url": "https://github.com/example/bad.git",
            "reason": "RuntimeError: boom",
        }
    ]


def test_analysis_runner_supports_multiple_workers_without_order_assumptions():
    analyzer = RecordingAnalyzer("https://github.com/example/bad.git")
    run_reporter = RecordingRunReporter()
    repos = [
        "https://github.com/example/good-a.git",
        "https://github.com/example/bad.git",
        "https://github.com/example/good-b.git",
    ]

    failures = AnalysisRunner().run(
        repos,
        analyzer,
        clone_depth=3,
        workers=3,
        run_reporter=run_reporter,
    )

    assert failures == 1
    assert set(analyzer.calls) == {
        ("https://github.com/example/good-a.git", 3),
        ("https://github.com/example/bad.git", 3),
        ("https://github.com/example/good-b.git", 3),
    }
    assert run_reporter.failures == [
        {
            "repo_url": "https://github.com/example/bad.git",
            "reason": "RuntimeError: boom",
        }
    ]
