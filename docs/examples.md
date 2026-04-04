# Examples

These examples show real artifact shapes and failure handling.

## Example 1: Metadata-only run

Config excerpt, save under `configs/`:

```yaml
repositories: repositories/one-repo.yaml
tools:
  - github
workers: 2
github_token: ghp_example
```

Run:

```bash
docker compose run --rm josseph configs/config.yaml
```

Expected repository artifact set:

```text
results/example@project/github.parquet
results/example@project/github.json
results/runs/20260322T150000Z/summary.json
```

Example `github.json`:

```json
{
  "commit_hash": "",
  "requested_commit_hash": null,
  "metric_binding": "observation-bound",
  "collected_at_utc": "2026-03-22T12:34:56Z"
}
```

Example row inside `github.parquet`:

```json
{
  "full_name": "example/project",
  "description": "Metrics demo repository",
  "default_branch": "main",
  "language": "Java",
  "license": "Apache-2.0",
  "homepage": "",
  "stargazers_count": 42,
  "watchers_count": 42,
  "subscribers_count": 7,
  "forks_count": 5,
  "network_count": 5,
  "open_issues_total": 3,
  "has_issues": true,
  "has_wiki": false,
  "has_pages": false,
  "is_fork": false,
  "archived": false,
  "disabled": false,
  "size_kb": 2048,
  "created_at": "2025-01-01T10:00:00Z",
  "updated_at": "2026-03-20T11:00:00Z",
  "pushed_at": "2026-03-22T12:00:00Z",
  "topics": "metrics,java"
}
```

## Example 2: Pinned commit run

Hypothetical pinned-config excerpt (save under `configs/`):

```yaml
repositories: repositories/pinned-projects.yaml  # hypothetical
tools:
  - github
  - ck
workers: 1
```

Hypothetical repository list excerpt:

```yaml
- url: https://github.com/example/project.git
  commit: deadbeefcafebabe
```

Relevant per-tool metadata:

```json
{
  "github.json": {
    "commit_hash": "",
    "requested_commit_hash": "deadbeefcafebabe",
    "metric_binding": "observation-bound",
    "collected_at_utc": "2026-03-22T12:34:56Z"
  },
  "ck.json": {
    "commit_hash": "deadbeefcafebabe",
    "requested_commit_hash": "deadbeefcafebabe",
    "metric_binding": "revision-bound",
    "collected_at_utc": "2026-03-22T12:35:10Z"
  }
}
```

Relevant `summary.json` fragment:

```json
{
  "config": {
    "repositories": [
      {
        "repo_url": "https://github.com/example/project.git",
        "requested_commit_hash": "deadbeefcafebabe"
      }
    ]
  },
  "summary": {
    "repository_count": 1,
    "failed_run_count": 0,
    "skipped_run_count": 0
  }
}
```

## Example 3: Mixed checkout-free and checkout-based extractors

Config excerpt, matching `configs/20-small.yaml`:

```yaml
repositories: repositories/20-small-repos.yaml
tools:
  - github
  - ck
  - cm
workers: 2
extractor_settings:
  cm:
    timeout_seconds: 1800
```

Execution model for each repository:

1. Run `github` without checkout.
2. Clone repository with up to 3 attempts.
3. Resolve `git rev-parse HEAD`.
4. Run `ck`.
5. Run `cm`.
6. Persist `<tool>.parquet` and `<tool>.json` for each successful extractor.

## Example 4: Partial extractor failure with successful run

Suppose `github` succeeds and `sonar` fails because SonarQube is unavailable.

Example `summary.json`:

Excerpt, omitting unchanged fields:

```json
{
  "run_id": "20260322T150000Z",
  "status": "success",
  "started_at_utc": "2026-03-22T15:00:00Z",
  "finished_at_utc": "2026-03-22T15:00:12Z",
  "duration_seconds": 12.0,
  "exit_code": 0,
  "summary": {
    "repository_count": 1,
    "affected_repository_count": 1,
    "repository_failure_count": 0,
    "extractor_failure_count": 1,
    "failed_run_count": 1,
    "skipped_run_count": 0
  },
  "extractor_failures": [
    {
      "scope": "extractor",
      "repo_url": "https://github.com/example/repo.git",
      "project_name": "example@repo",
      "extractor": "sonar",
      "requested_commit_hash": null,
      "metric_binding": "revision-bound",
      "reason": "AnalysisError: scanner unavailable",
      "recorded_at_utc": "2026-03-22T15:00:04Z"
    }
  ],
  "failed_runs": [
    {
      "scope": "extractor",
      "repo_url": "https://github.com/example/repo.git",
      "project_name": "example@repo",
      "extractor": "sonar",
      "requested_commit_hash": null,
      "metric_binding": "revision-bound",
      "reason": "AnalysisError: scanner unavailable",
      "recorded_at_utc": "2026-03-22T15:00:04Z"
    }
  ]
}
```

Operational meaning:

- the process completed
- at least one extractor failed
- successful artifacts from other extractors remain valid
- downstream consumers must consult `summary.json` before assuming completeness
- the artifacts are stored under one repository directory, so a later run for
  the same repository can overwrite an earlier revision's outputs

## Example 5: Repository failure with non-zero exit

If clone or checkout resolution fails for a repository, the run ends with exit
code `1`.

Example excerpt:

Excerpt, omitting unchanged fields:

```json
{
  "status": "failed",
  "exit_code": 1,
  "summary": {
    "repository_count": 1,
    "affected_repository_count": 1,
    "repository_failure_count": 1,
    "extractor_failure_count": 0,
    "failed_run_count": 1,
    "skipped_run_count": 0
  },
  "repository_failures": [
    {
      "scope": "repository",
      "repo_url": "https://github.com/example/repo.git",
      "project_name": "example@repo",
      "requested_commit_hash": null,
      "reason": "clone failed",
      "recorded_at_utc": "2026-03-22T15:00:01Z"
    }
  ]
}
```
