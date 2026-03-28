# Output

This page defines the artifact contract under `results/`.

## Directory layout

Per repository and per extractor:

```text
results/<owner>@<repo>/<tool>.parquet
results/<owner>@<repo>/<tool>.json
```

Per run:

```text
results/runs/<run-id>/summary.json
```

`<run-id>` is UTC time in `YYYYMMDDTHHMMSSZ` format.

## Per-tool artifact contract

An extractor result is considered present only when both files exist:

- `<tool>.parquet`
- `<tool>.json`

This matters for cache reuse. If only one file exists, JOSSeph treats the
result as missing and reruns the extractor.

## Metadata JSON contract

Every successful extractor writes:

```json
{
  "commit_hash": "abc123",
  "collected_at_utc": "2026-03-22T12:34:56Z"
}
```

Rules:

- `commit_hash` is the resolved `HEAD` for checkout-based extractors
- `commit_hash` is `""` for checkout-free runs such as `github`
- `collected_at_utc` is UTC and truncated to whole seconds

## Run summary contract

Example:

```json
{
  "run_id": "20260322T150000Z",
  "status": "failed",
  "started_at_utc": "2026-03-22T15:00:00Z",
  "finished_at_utc": "2026-03-22T15:00:12Z",
  "duration_seconds": 12.0,
  "exit_code": 1,
  "config": {
    "config_path": "/workspace/configs/run.yaml",
    "repositories": [
      "https://github.com/example/repo.git"
    ],
    "clone_depth": 1,
    "tools": [
      "github",
      "sonar"
    ],
    "extractor_settings": {
      "sonar": {
        "host_url": "http://localhost:9234"
      }
    },
    "github_token": "***redacted***",
    "workers": 2
  },
  "summary": {
    "repository_count": 1,
    "affected_repository_count": 1,
    "repository_failure_count": 1,
    "extractor_failure_count": 1,
    "failed_run_count": 2,
    "skipped_run_count": 0
  },
  "repository_failures": [
    {
      "scope": "repository",
      "repo_url": "https://github.com/example/repo.git",
      "project_name": "example@repo",
      "reason": "clone failed",
      "recorded_at_utc": "2026-03-22T15:00:01Z"
    }
  ],
  "extractor_failures": [
    {
      "scope": "extractor",
      "repo_url": "https://github.com/example/repo.git",
      "project_name": "example@repo",
      "extractor": "github",
      "reason": "api failed",
      "recorded_at_utc": "2026-03-22T15:00:02Z"
    }
  ],
  "failed_runs": [
    {
      "scope": "repository",
      "repo_url": "https://github.com/example/repo.git",
      "project_name": "example@repo",
      "reason": "clone failed",
      "recorded_at_utc": "2026-03-22T15:00:01Z"
    },
    {
      "scope": "extractor",
      "repo_url": "https://github.com/example/repo.git",
      "project_name": "example@repo",
      "extractor": "github",
      "reason": "api failed",
      "recorded_at_utc": "2026-03-22T15:00:02Z"
    }
  ],
  "skipped_runs": []
}
```

## How to interpret `summary`

| Field | Meaning |
| --- | --- |
| `repository_count` | number of unique repositories in the loaded config |
| `affected_repository_count` | number of repositories with at least one skip or failure event |
| `repository_failure_count` | count of repository-level failures |
| `extractor_failure_count` | count of extractor-level failures |
| `failed_run_count` | total length of `failed_runs` |
| `skipped_run_count` | total length of `skipped_runs` |

## Missing file rules

Missing output files are meaningful:

- missing `<tool>.parquet` and `<tool>.json` usually means the extractor failed or was not selected
- missing only one of the pair means the result is incomplete and is not treated as cached
- missing `results/runs/<run-id>/summary.json` usually means config loading failed before reporting started

## Consumer guidance

If you build downstream jobs on top of `results/`, do not assume the directory
tree is complete. Use `summary.json` as the run manifest and fail your consumer
when expected extractor outputs are absent or listed in `failed_runs`.
