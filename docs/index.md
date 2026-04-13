# JOSSeph

**JOSSeph** (**J**ava **O**SS metrics **S**oftware) is a Docker-first
reproducible pipeline for extracting metrics from GitHub Java repositories.

One run does this:

1. Load and validate config.
2. Build extractor runtime.
3. Process repositories in parallel.
4. Write per-tool artifacts.
5. Write one run summary.

The useful part is not "metrics in general". The useful part is a strict,
reproducible contract:

- input is one YAML file plus one repository list
- the primary execution target is `docker compose run --rm josseph <config>`
- the Docker runtime makes execution platform-independent
- output is a predictable directory tree under `results/`
- every partial failure is supposed to end up in `summary.json`
- a cached result is reused only when both `<tool>.parquet` and `<tool>.json` exist

## What a run produces

For repository `https://github.com/example/project.git` and tools `github` and
`ck`, the steady-state output is:

```text
results/
  example@project/
    github.parquet
    github.json
    ck.parquet
    ck.json
  runs/
    20260328T120000Z/
      summary.json
```

`github.json` has this excerpted shape:

```json
{
  "commit_hash": "",
  "requested_commit_hash": null,
  "metric_binding": "observation-bound",
  "collected_at_utc": "2026-03-22T12:34:56Z"
}
```

`summary.json` is the run-level source of truth. Excerpt:

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
    "affected_repository_count": 0,
    "repository_failure_count": 0,
    "extractor_failure_count": 0,
    "failed_run_count": 0,
    "skipped_run_count": 0
  },
  "repository_failures": [],
  "extractor_failures": [],
  "failed_runs": [],
  "skipped_runs": []
}
```

If you only read one file after a run, read `results/runs/<run-id>/summary.json`.
It tells you which repository failed, which extractor failed, which results were
skipped as cached, and whether the process exited `0`, `1`, or `2`.

## Start here

1. [Getting Started](getting-started.md) for the fastest real run.
2. [Config](config.md) for the exact YAML contract.
3. [Output](output.md) for artifact schemas and failure cases.
4. [Examples](examples.md) for concrete success and partial-failure runs.
