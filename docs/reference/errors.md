# Errors

This page explains what users will see when something goes wrong.

## Invalid config

Examples:

- config file missing
- YAML is broken
- `repositories` is missing
- `workers` is invalid
- a tool name is unknown

Result:

- the run stops before analysis starts
- the process exits with code `2`

## Tool problems

Examples:

- GitHub rate limits
- CK or CM command failure
- SonarQube is unreachable
- a tool times out

Result:

- the failing tool is recorded in `summary.json`
- the rest of the run can continue

## Repository problems

Examples:

- clone fails after retries
- the repository cannot be checked out
- the repository hash cannot be resolved

Result:

- the repository is marked as failed
- the process exits non-zero
- the failure appears in `summary.json`

## Where to look first

1. `results/runs/<run-id>/summary.json`
2. the log output
3. the repository-specific result directory under `results/`
