# Pipeline

This page documents the order of work during a run.

## Order

1. Load config
2. Build tools
3. Start the run summary
4. Process repositories
5. Save results
6. Write `summary.json`

## Parallelism

Repositories are processed in parallel. A single repository is handled one
step at a time.

## Important behavior

- cached results are reused
- non-checkout tools can run without cloning
- checkout-based tools clone the repository first
- failures for one tool do not stop the whole run
