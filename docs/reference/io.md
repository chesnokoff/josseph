# IO Details

This page keeps the file-level contract in one place.

## Inputs

JOSSeph reads:

- one YAML config file
- one repository list file
- optional external services when you use GitHub or Sonar

## Outputs

For each repository and tool:

- Parquet data under `results/<owner>@<repo>/<tool>.parquet`
- metadata JSON under `results/<owner>@<repo>/<tool>.json`

For each run:

- `results/runs/<run-id>/summary.json`

## Summary file

The summary file includes:

- run timestamps
- exit code
- config snapshot with secrets redacted
- repository counts
- failure lists
- skipped result lists

## Guarantees

- result paths are predictable
- metadata JSON is written next to the Parquet file
- summary output is written once per run when the pipeline reaches reporting

## Not guaranteed

- every repository will have every tool result
- failed tools do not produce result files
- config errors before startup do not produce a summary file
