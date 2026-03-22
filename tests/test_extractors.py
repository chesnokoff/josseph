from __future__ import annotations

import csv
from pathlib import Path

from josseph.domain.repository import AnalysisTarget, RepositoryRef
from josseph.metrics.extractors.ck import CkExtractor
from josseph.metrics.extractors.cm import CmExtractor
from josseph.metrics.extractors.github import GithubExtractor
from josseph.metrics.extractors.sonar import SonarExtractor, SonarScanner, SonarScannerSettings
from josseph.providers.github import GithubClient
from josseph.providers.sonar import SonarClient
from josseph.utils import setup_trace


setup_trace()


class FakeCommandRunner:
    def __init__(self, handler):
        self._handler = handler

    def run(self, cmd, *, cwd=None, env=None, timeout=None):
        return self._handler(cmd, cwd=cwd, env=env, timeout=timeout)


def make_third_party(tmp_path):
    third_party = tmp_path / "third_party"
    (third_party / "ck").mkdir(parents=True)
    (third_party / "cm").mkdir(parents=True)
    (third_party / "ck" / "ck.jar").write_text("", encoding="utf-8")
    (third_party / "cm" / "cm.jar").write_text("", encoding="utf-8")
    return third_party


def make_target(repo="https://github.com/example/repo.git", checkout_path=None, commit_hash=None):
    return AnalysisTarget(
        repository=RepositoryRef.parse(repo),
        checkout_path=checkout_path,
        commit_hash=commit_hash,
    )


def test_github_extractor_returns_formatted_metrics(tmp_path, monkeypatch):
    extractor = GithubExtractor(client=GithubClient(token=None))
    payload = {
        "full_name": "example/repo",
        "description": "Demo",
        "default_branch": "main",
        "language": "Java",
        "license": {"spdx_id": "Apache-2.0"},
        "homepage": "https://example.com",
        "stargazers_count": 10,
        "watchers_count": 11,
        "subscribers_count": 12,
        "forks_count": 13,
        "network_count": 14,
        "open_issues_count": 15,
        "has_issues": True,
        "has_wiki": False,
        "has_pages": False,
        "fork": False,
        "archived": False,
        "disabled": False,
        "size": 16,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "pushed_at": "2024-01-03T00:00:00Z",
        "topics": ["quality", "java"],
    }
    monkeypatch.setattr(extractor.client, "get_repo", lambda slug: payload)

    rows = extractor.run(make_target())

    assert rows == [
        {
            "full_name": "example/repo",
            "description": "Demo",
            "default_branch": "main",
            "language": "Java",
            "license": "Apache-2.0",
            "homepage": "https://example.com",
            "stargazers_count": 10,
            "watchers_count": 11,
            "subscribers_count": 12,
            "forks_count": 13,
            "network_count": 14,
            "open_issues_total": 15,
            "has_issues": True,
            "has_wiki": False,
            "has_pages": False,
            "is_fork": False,
            "archived": False,
            "disabled": False,
            "size_kb": 16,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "pushed_at": "2024-01-03T00:00:00Z",
            "topics": "quality,java",
        }
    ]


def test_ck_extractor_reads_generated_csv(tmp_path, monkeypatch):
    def fake_run_command(cmd, cwd=None, env=None, timeout=None):
        out_dir = Path(cmd[-1].rstrip("/"))
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = out_dir / "class.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["class", "wmc"])
            writer.writeheader()
            writer.writerow({"class": "Example", "wmc": "3"})
        return ""

    extractor = CkExtractor(
        third_party_path=make_third_party(tmp_path),
        command_runner=FakeCommandRunner(fake_run_command),
    )

    rows = extractor.run(make_target(checkout_path=tmp_path))

    assert rows == [{"class": "Example", "wmc": "3"}]


def test_cm_extractor_filters_non_java_rows(tmp_path, monkeypatch):
    def fake_run_command(cmd, cwd=None, env=None, timeout=None):
        assert timeout == 7
        csv_path = Path(cmd[4])
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["file", "commits"])
            writer.writeheader()
            writer.writerow({"file": "src/Main.java", "commits": "2"})
            writer.writerow({"file": "README.md", "commits": "1"})
        return ""

    extractor = CmExtractor(
        third_party_path=make_third_party(tmp_path),
        command_runner=FakeCommandRunner(fake_run_command),
        timeout_seconds=7,
    )

    rows = extractor.run(make_target(checkout_path=tmp_path))

    assert rows == [{"file": "src/Main.java", "commits": "2"}]


def test_sonar_extractor_uses_client_and_converts_measures(tmp_path, monkeypatch):
    calls = []

    class FakeClient:
        def wait_for_status(self, expected, timeout):
            calls.append(("wait_for_status", expected, timeout))

        def ensure_admin_password(self):
            calls.append(("ensure_admin_password",))

        def create_project(self, project_key, project_name):
            calls.append(("create_project", project_key, project_name))

        def generate_token(self):
            calls.append(("generate_token",))
            return "token-123"

        def wait_for_analysis(self, project_key):
            calls.append(("wait_for_analysis", project_key))

        def fetch_metrics(self, project_key):
            calls.append(("fetch_metrics", project_key))
            return {
                "project": project_key,
                "measures": [
                    {"metric": "bugs", "value": "1"},
                    {"metric": "coverage", "value": "80.5"},
                ],
            }

        def delete_project(self, project_key):
            calls.append(("delete_project", project_key))

    def fake_run_command(cmd, cwd=None, env=None, timeout=None):
        calls.append(("run_command", cmd, cwd))
        return ""

    settings = SonarScannerSettings.from_env({"SONAR_OPTIONS": ""})
    extractor = SonarExtractor(
        client=FakeClient(),
        scanner=SonarScanner(
            command_runner=FakeCommandRunner(fake_run_command),
            settings=settings,
        ),
    )

    rows = extractor.run(make_target(checkout_path=tmp_path))

    assert rows == [{"bugs": "1", "coverage": "80.5"}]
    assert ("create_project", "example_repo", "example_repo") in calls
    assert ("wait_for_analysis", "example_repo") in calls
    assert ("delete_project", "example_repo") in calls
    assert (tmp_path / ".sonar-empty-binaries").is_dir()
