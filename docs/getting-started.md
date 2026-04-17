# Getting Started

This page gets you from an empty workspace to a run you can verify.

## 1. Create the repository list

The repository file is a YAML sequence. Each entry is either a plain URL string
or a mapping with a `url` and an optional `commit` hash. Duplicates are removed
after loading.

```yaml
# configs/repositories/one-repo.yaml
- https://github.com/apache/airflow.git
- https://github.com/apache/spark.git
```

To pin a specific commit:

```yaml
- url: https://github.com/apache/airflow.git
  commit: deadbeefcafebabe
- https://github.com/apache/spark.git
```

The same repository cannot appear twice in one run with different pinned
commits. The config validator rejects that input because outputs are stored per
repository, not per revision.

## 2. Create the config

Use a small config first:

```yaml
repositories: repositories/one-repo.yaml
tools:
  - github
  - ck
workers: 2
```

Because this config lives under `configs/`, that repository path resolves to
`configs/repositories/one-repo.yaml`.

Contract:

- `repositories` is required and must point to a file
- `tools` is optional; omitted means "all registered extractors"
- pinned commits are only supported when reachable from the repository's default branch
- the same repository cannot appear twice in one run with different pinned commits
- `workers` must be a positive integer when set

## 3. Run the pipeline

JOSSeph is Docker-first. On **Linux**, SonarQube requires a kernel parameter
increase before the first run:

```bash
sudo sysctl -w vm.max_map_count=524288
```

This is not needed on macOS or Windows (Docker Desktop handles it).

Then run the pipeline:

```bash
docker compose run --rm josseph configs/config.yaml
```

You can run the module directly for development or debugging, but that is a
fallback path, not the primary operating model:

```bash
python -m josseph configs/config.yaml
```

## 4. Verify artifacts, not just console output

After a successful run, expect artifacts like:

```text
results/
  apache@airflow/
    github.parquet
    github.json
    ck.parquet
    ck.json
  apache@spark/
    github.parquet
    github.json
    ck.parquet
    ck.json
  runs/
    20260328T120000Z/
      summary.json
```

Open `results/runs/<run-id>/summary.json` first. A healthy run looks like:

```json
{
  "status": "success",
  "exit_code": 0,
  "summary": {
    "repository_count": 2,
    "affected_repository_count": 0,
    "repository_failure_count": 0,
    "extractor_failure_count": 0,
    "failed_run_count": 0,
    "skipped_run_count": 0
  }
}
```

## 5. Know what failure looks like

If `ck` fails on `apache@spark` but `github` succeeds, the run can still finish.
What changes:

- `results/apache@spark/github.parquet` may exist
- `results/apache@spark/ck.parquet` may be missing
- `summary.json` records the extractor failure
- process exit code can still be `0`
- `observation-bound` extractors still use the same file-based cache unless you pass `--force`

Example excerpt:

```json
{
  "run_id": "20260322T150000Z",
  "status": "success",
  "started_at_utc": "2026-03-22T15:00:00Z",
  "finished_at_utc": "2026-03-22T15:00:12Z",
  "duration_seconds": 12.0,
  "exit_code": 0,
  "summary": {
    "repository_count": 2,
    "affected_repository_count": 1,
    "repository_failure_count": 0,
    "extractor_failure_count": 1,
    "failed_run_count": 1,
    "skipped_run_count": 0
  },
  "extractor_failures": [
    {
      "scope": "extractor",
      "repo_url": "https://github.com/apache/spark.git",
      "project_name": "apache@spark",
      "extractor": "ck",
      "requested_commit_hash": null,
      "metric_binding": "revision-bound",
      "reason": "CK execution failed with exit code 1: java -jar ...",
      "recorded_at_utc": "2026-03-28T12:01:04Z"
    }
  ]
}
```

The example below is intentionally partial; omitted fields are unchanged from
the full schema.

## 6. Add service-backed extractors only when ready

- `github` works best with `github_token` or `GITHUB_TOKEN`
- `sonar` requires a reachable SonarQube instance
- on a fresh local SonarQube container, keep `SONAR_ADMIN_DEFAULT_PASSWORD`
  equal to the current admin password and set `SONAR_ADMIN_PASSWORD` to the
  new policy-compliant password JOSSeph should use after bootstrap
- `ck` and `cm` require their vendored JARs to exist

If those prerequisites are missing, the correct expectation is failure reporting,
not silent fallback.
