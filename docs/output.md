# Output

This page explains what you get after a run.

## Per repository

For each repository and each tool, JOSSeph writes two files:

- `results/<owner>@<repo>/<tool>.parquet`
- `results/<owner>@<repo>/<tool>.json`

Example:

```text
results/example@project/github.parquet
results/example@project/github.json
```

## What the files mean

- the Parquet file contains the collected rows
- the JSON file contains the commit hash and the collection time

For non-checkout tools, the commit hash may be empty.

## Run summary

Every run writes:

```text
results/runs/<run-id>/summary.json
```

This file is the best place to check:

- whether the run succeeded
- which repositories were affected
- which tools were skipped or failed

## How to read the summary

The summary includes:

- `status`
- `exit_code`
- `repository_count`
- `repository_failure_count`
- `extractor_failure_count`
- `failed_runs`
- `skipped_runs`

Short version:

- `status: success` means the run finished cleanly
- `status: failed` means at least one repository had a serious problem
- extractor failures can appear even when the overall run exits `0`

## Missing files

If a tool failed, its output files may be missing for that repository.
That is normal. Check `summary.json` for the reason.
