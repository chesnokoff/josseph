# Examples

Use these examples as a starting point.

## Example 1: GitHub and CK only

Config:

```yaml
repositories: configs/repos.txt
tools:
  - github
  - ck
clone_depth: 1
workers: 2
github_token: ghp_example
```

Run:

```bash
docker compose run --rm josseph configs/run.yaml
```

Result files:

```text
results/example@project/github.parquet
results/example@project/github.json
results/example@project/ck.parquet
results/example@project/ck.json
results/runs/20260322T150000Z/summary.json
```

## Example 2: Add Sonar

Config:

```yaml
repositories: configs/repos.txt
tools:
  - github
  - ck
  - cm
  - sonar
clone_depth: 1
workers: 2
github_token: ghp_example
extractor_settings:
  cm:
    timeout_seconds: 1800
  sonar:
    host_url: http://localhost:9234
```

Run:

```bash
docker compose up -d sonarqube
docker compose run --rm josseph configs/run.yaml
```

## Example output

The exact columns depend on the tool, but the files always follow the same
pattern:

```text
results/example@project/github.parquet
results/example@project/github.json
results/runs/20260322T150000Z/summary.json
```

The JSON metadata next to each Parquet file looks like:

```json
{
  "commit_hash": "abc123",
  "collected_at_utc": "2026-03-22T12:34:56Z"
}
```

And the run summary includes counts and failure lists:

```json
{
  "status": "success",
  "exit_code": 0,
  "summary": {
    "repository_count": 1,
    "affected_repository_count": 0,
    "repository_failure_count": 0,
    "extractor_failure_count": 0,
    "failed_run_count": 0,
    "skipped_run_count": 0
  }
}
```
