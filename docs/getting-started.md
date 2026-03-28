# Getting Started

This page gets you from an empty workspace to a run you can verify.

## 1. Create the repository list

The repository file is a plain text input artifact. JOSSeph reads one URL per
line, ignores blank lines, ignores lines starting with `#`, and removes
duplicates after loading.

```text
# configs/repos.txt
https://github.com/apache/airflow.git
https://github.com/apache/spark.git
https://github.com/apache/airflow.git
```

The effective repository set for this file is:

```json
[
  "https://github.com/apache/airflow.git",
  "https://github.com/apache/spark.git"
]
```

## 2. Create the config

Use a small config first:

```yaml
repositories: configs/repos.txt
tools:
  - github
  - ck
clone_depth: 1
workers: 2
```

Contract:

- `repositories` is required and must point to a file
- `tools` is optional; omitted means "all registered extractors"
- `clone_depth` must be a positive integer when set
- `workers` must be a positive integer when set

## 3. Run the pipeline

JOSSeph is Docker-first. The standard way to run it is:

```bash
docker compose run --rm josseph configs/run.yaml
```

You can run the module directly for development or debugging, but that is a
fallback path, not the primary operating model:

```bash
python -m josseph configs/run.yaml
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

Example:

```json
{
  "status": "success",
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
      "reason": "CK execution failed with exit code 1: java -jar ...",
      "recorded_at_utc": "2026-03-28T12:01:04Z"
    }
  ]
}
```

## 6. Add service-backed extractors only when ready

- `github` works best with `github_token` or `GITHUB_TOKEN`
- `sonar` requires a reachable SonarQube instance
- `ck` and `cm` require their vendored JARs to exist

If those prerequisites are missing, the correct expectation is failure reporting,
not silent fallback.
