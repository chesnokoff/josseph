from __future__ import annotations

import csv
import subprocess
import traceback
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

from josseph.domain.repository import AnalysisTarget, RepositoryRef
from josseph.metrics.extractors.ck import CkExtractor
from josseph.metrics.extractors.cm import CmExtractor
from josseph.metrics.extractors.github import GithubExtractor
from josseph.metrics.extractors.sonar import (
    DEFAULT_SONAR_ADMIN_DEFAULT_PASSWORD,
    DEFAULT_SONAR_ADMIN_PASSWORD,
    SonarExtractor,
    SonarScanner,
    SonarScannerSettings,
    _build_sonar_project_key,
    build_extractor,
)
from josseph.metrics.registry import ExtractorFactoryContext
from josseph.process import CommandExecutionError
from josseph.providers.github import GithubClient
from josseph.providers.sonar import SonarClient
from josseph.utils import AnalysisError, setup_trace

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


def test_github_extractor_raises_analysis_error_on_http_error(tmp_path, monkeypatch):
    extractor = GithubExtractor(client=GithubClient(token=None))

    def fake_get_repo(slug):
        raise HTTPError(
            "https://api.github.com/repos/example/repo",
            403,
            "rate limited",
            {},
            BytesIO(b""),
        )

    monkeypatch.setattr(extractor.client, "get_repo", fake_get_repo)

    with pytest.raises(
        AnalysisError,
        match="Failed to fetch repository metadata for example/repo: HTTP Error 403: rate limited",
    ):
        extractor.run(make_target())


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


def test_ck_extractor_surfaces_standard_command_failure_contract(tmp_path):
    def fake_run_command(cmd, cwd=None, env=None, timeout=None):
        raise subprocess.CalledProcessError(
            returncode=2,
            cmd=cmd,
            output=b"ck stdout",
            stderr=b"ck stderr",
        )

    extractor = CkExtractor(
        third_party_path=make_third_party(tmp_path),
        command_runner=FakeCommandRunner(fake_run_command),
    )

    with pytest.raises(
        AnalysisError,
        match=r"CK execution failed with exit code 2",
    ) as excinfo:
        extractor.run(make_target(checkout_path=tmp_path))

    assert "stdout:\nck stdout" in str(excinfo.value)
    assert "stderr:\nck stderr" in str(excinfo.value)


def test_cm_extractor_requires_checkout(tmp_path):
    extractor = CmExtractor(
        third_party_path=make_third_party(tmp_path),
        command_runner=FakeCommandRunner(lambda *args, **kwargs: ""),
        timeout_seconds=7,
    )

    with pytest.raises(AnalysisError, match="CM extractor requires a local repository checkout"):
        extractor.run(make_target())


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


def test_cm_extractor_surfaces_standard_timeout_contract(tmp_path):
    def fake_run_command(cmd, cwd=None, env=None, timeout=None):
        raise subprocess.TimeoutExpired(
            cmd=cmd,
            timeout=timeout,
            output="cm stdout",
            stderr="cm stderr",
        )

    extractor = CmExtractor(
        third_party_path=make_third_party(tmp_path),
        command_runner=FakeCommandRunner(fake_run_command),
        timeout_seconds=7,
    )

    with pytest.raises(
        AnalysisError,
        match=r"CM execution timed out after 7 seconds: java -jar .*results\.csv single",
    ) as excinfo:
        extractor.run(make_target(checkout_path=tmp_path))

    message = str(excinfo.value)
    assert "stdout:\ncm stdout" in message
    assert "stderr:\ncm stderr" in message


def test_sonar_scanner_surfaces_command_output_on_failure(tmp_path):
    def fake_run_command(cmd, cwd=None, env=None, timeout=None):
        raise subprocess.CalledProcessError(
            returncode=7,
            cmd=cmd,
            output="scanner stdout",
            stderr="scanner stderr",
        )

    scanner = SonarScanner(
        command_runner=FakeCommandRunner(fake_run_command),
        settings=SonarScannerSettings.from_env({"SONAR_OPTIONS": ""}),
    )

    with pytest.raises(AnalysisError) as excinfo:
        scanner.run(tmp_path, "example_repo", "token-123")

    message = str(excinfo.value)
    assert "sonar-scanner execution failed with exit code 7" in message
    assert "stdout:\nscanner stdout" in message
    assert "stderr:\nscanner stderr" in message


def test_sonar_scanner_redacts_token_through_the_cause_chain(tmp_path: Path) -> None:
    token = "squ_0123456789abcdef"

    def fake_run_command(
        cmd: tuple[str, ...],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> str:
        # mimic SubprocessCommandRunner: CommandExecutionError is raised
        # from the original CalledProcessError, so the raw token survives
        # one level deeper in __cause__
        try:
            raise subprocess.CalledProcessError(
                returncode=3,
                cmd=cmd,
                output=f"launching: sonar-scanner -Dsonar.login={token}",
                stderr=f"scan aborted, bare token {token} echoed by the JVM",
            )
        except subprocess.CalledProcessError as exc:
            raise CommandExecutionError(
                exc.returncode,
                exc.cmd,
                output=exc.output,
                stderr=exc.stderr,
            ) from exc

    scanner = SonarScanner(
        command_runner=FakeCommandRunner(fake_run_command),
        settings=SonarScannerSettings.from_env({"SONAR_OPTIONS": ""}),
    )

    with pytest.raises(AnalysisError) as excinfo:
        scanner.run(tmp_path, "example_repo", token)

    message = str(excinfo.value)
    assert token not in message
    assert "-Dsonar.login=***" in message
    assert "scan aborted" in message

    # the fully rendered traceback walks __cause__/__context__; the token
    # must not appear anywhere in the chain
    rendered = "".join(traceback.format_exception(excinfo.value))
    assert token not in rendered


def test_sonar_extractor_uses_client_and_converts_measures(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "josseph.metrics.extractors.sonar._build_sonar_project_key",
        lambda target: "example_repo_deadbeef1234_abcd1234",
    )

    class FakeClient:
        def wait_for_status(self, expected, timeout):
            calls.append(("wait_for_status", expected, timeout))

        def ensure_admin_password(self):
            calls.append(("ensure_admin_password",))

        def ensure_project(self, project_key, project_name):
            calls.append(("ensure_project", project_key, project_name))

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
    assert (
        "ensure_project",
        "example_repo_deadbeef1234_abcd1234",
        "example@repo",
    ) in calls
    assert ("wait_for_analysis", "example_repo_deadbeef1234_abcd1234") in calls
    assert ("delete_project", "example_repo_deadbeef1234_abcd1234") in calls
    assert (tmp_path / ".sonar-empty-binaries").is_dir()


def test_sonar_extractor_deletes_project_on_scanner_failure(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "josseph.metrics.extractors.sonar._build_sonar_project_key",
        lambda target: "example_repo_deadbeef1234_abcd1234",
    )

    class FakeClient:
        def wait_for_status(self, expected, timeout):
            calls.append(("wait_for_status", expected, timeout))

        def ensure_admin_password(self):
            calls.append(("ensure_admin_password",))

        def ensure_project(self, project_key, project_name):
            calls.append(("ensure_project", project_key, project_name))

        def generate_token(self):
            calls.append(("generate_token",))
            return "token-123"

        def wait_for_analysis(self, project_key):
            calls.append(("wait_for_analysis", project_key))

        def fetch_metrics(self, project_key):
            calls.append(("fetch_metrics", project_key))
            return {"project": project_key, "measures": []}

        def delete_project(self, project_key):
            calls.append(("delete_project", project_key))

    class FailingScanner:
        def run(self, repo_path, project_key, token):
            raise AnalysisError("scanner exploded")

    extractor = SonarExtractor(client=FakeClient(), scanner=FailingScanner())

    with pytest.raises(AnalysisError, match="Sonar scan failed"):
        extractor.run(make_target(checkout_path=tmp_path))

    assert ("delete_project", "example_repo_deadbeef1234_abcd1234") in calls


def make_sonar_client_failing_with(message: str) -> SonarClient:
    client = SonarClient(
        host_url="http://localhost:9000",
        admin_user="admin",
        admin_password="secret",
        admin_default_password="admin",
    )

    def failing_request(*args: object, **kwargs: object) -> bytes:
        raise AnalysisError(message)

    client.request = failing_request  # type: ignore[method-assign]
    return client


def test_sonar_client_ensure_project_treats_retried_already_exists_as_success() -> None:
    client = make_sonar_client_failing_with(
        'HTTP error 400 for http://localhost:9000/api/projects/create: '
        '{"errors":[{"msg":"Could not create Project, key already exists: k"}]}'
    )
    client.ensure_project("key_deadbeef_abcd1234", "example")


def test_sonar_client_ensure_project_does_not_claim_unrelated_create_failures() -> None:
    client = make_sonar_client_failing_with(
        'HTTP error 400 for http://localhost:9000/api/projects/create: '
        '{"errors":[{"msg":"Could not create Project: quota exceeded"}]}'
    )
    with pytest.raises(AnalysisError, match="quota exceeded"):
        client.ensure_project("key_deadbeef_abcd1234", "example")


def test_sonar_client_ensure_project_propagates_other_errors() -> None:
    client = make_sonar_client_failing_with(
        "HTTP error 403 for http://localhost:9000/api/projects/create"
    )
    with pytest.raises(AnalysisError, match="403"):
        client.ensure_project("key_deadbeef_abcd1234", "example")


def test_sonar_extractor_owns_and_cleans_up_project_after_retried_create(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        "josseph.metrics.extractors.sonar._build_sonar_project_key",
        lambda target: "example_repo_deadbeef1234_abcd1234",
    )

    class FakeClient:
        def wait_for_status(self, expected: str, timeout: int) -> None:
            calls.append(("wait_for_status", expected, timeout))

        def ensure_admin_password(self) -> None:
            calls.append(("ensure_admin_password",))

        def ensure_project(self, project_key: str, project_name: str) -> None:
            # provider contract: returns for fresh creates and for
            # "already exists" reported after a retried POST
            calls.append(("ensure_project", project_key, project_name))

        def generate_token(self) -> str:
            calls.append(("generate_token",))
            return "token-123"

        def wait_for_analysis(self, project_key: str) -> None:
            calls.append(("wait_for_analysis", project_key))

        def fetch_metrics(self, project_key: str) -> dict[str, object]:
            calls.append(("fetch_metrics", project_key))
            return {"project": project_key, "measures": []}

        def delete_project(self, project_key: str) -> None:
            calls.append(("delete_project", project_key))

    extractor = SonarExtractor(
        client=FakeClient(),
        scanner=SonarScanner(
            command_runner=FakeCommandRunner(lambda *args, **kwargs: ""),
            settings=SonarScannerSettings.from_env({"SONAR_OPTIONS": ""}),
        ),
    )

    rows = extractor.run(make_target(checkout_path=tmp_path))

    assert rows == [{}]
    assert ("generate_token",) in calls
    assert ("delete_project", "example_repo_deadbeef1234_abcd1234") in calls


def test_build_sonar_project_key_uses_project_and_commit_hash():
    key = _build_sonar_project_key(
        make_target(
            repo="https://github.com/example/repo.git",
            checkout_path=Path("/tmp/repo"),
            commit_hash="deadbeefcafebabe1234",
        )
    )

    assert key.startswith("example_repo_deadbeefcafe_")


def test_build_sonar_extractor_uses_bootstrap_sonar_admin_password_defaults(tmp_path):
    extractor = build_extractor(
        ExtractorFactoryContext(
            third_party_path=tmp_path / "third_party",
            env={},
            command_runner=FakeCommandRunner(lambda *args, **kwargs: ""),
        ),
        settings={},
    )

    assert isinstance(extractor, SonarExtractor)
    assert isinstance(extractor.client, SonarClient)
    assert extractor.client.admin_default_password == DEFAULT_SONAR_ADMIN_DEFAULT_PASSWORD
    assert extractor.client.admin_password == DEFAULT_SONAR_ADMIN_PASSWORD
