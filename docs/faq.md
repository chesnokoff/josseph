# FAQ

## Do I need Docker?

For normal use, yes. JOSSeph is Docker-first, and the documented execution path
is:

```bash
docker compose run --rm josseph configs/config.yaml
```

Direct module execution exists for development and debugging:

```bash
python -m josseph configs/config.yaml
```

## What exactly goes into `repositories`?

A text file with one repository URL per line, or a YAML sequence when you need
to pin a commit.

```text
https://github.com/example/project.git
```

Blank lines and `#` comments are ignored. Duplicate URLs are removed after
loading.

YAML input is also supported for pinned commits, but only for revisions that
are reachable from the repository's default branch.

You cannot list the same repository twice in one run with different pinned
commits. The config validator rejects that because outputs are stored per
repository, not per revision.

## Why is a result missing for one tool?

Check the strict cases first:

- the tool was not selected
- the extractor failed and therefore wrote no artifacts
- only one of `<tool>.parquet` or `<tool>.json` exists, so the result is incomplete
- the result was already cached and skipped

The source of truth is `results/runs/<run-id>/summary.json`.

## Why did the process exit `0` even though one extractor failed?

Because extractor failures are non-fatal by design. Exit code `1` is reserved
for repository-level failures. Use `summary.extractor_failure_count` and
`failed_runs` to detect incomplete runs.

## Why is there no `summary.json` at all?

The most likely cause is config loading failure before the run reporter was
created. Typical examples are missing config file, invalid YAML, or missing
`repositories`.

## Can I run only one tool?

Yes.

```yaml
repositories: repositories/one-repo.txt
tools:
  - github
```

If you save that config under `configs/`, the repository path resolves to
`configs/repositories/one-repo.txt`.

## What should I verify after a run?

1. exit code
2. `results/runs/<run-id>/summary.json`
3. expected `<tool>.parquet` and `<tool>.json` pairs for each repository

## How does caching work, and when should I clear results?

JOSSeph reuses a cached result whenever **both** `<tool>.parquet` and
`<tool>.json` exist for a given repository and tool. There is no content
fingerprint — the cache check is presence-only.

`observation-bound` extractors follow the same cache rule.

This means stale results can accumulate if you:

- change your config (e.g. change requested commits, add tools)
- update a tool version (CK, CM, SonarQube, Sonar Scanner)
- repoint a repository list to different repos with the same project name
- pin a different commit for the same repository, because artifacts are stored
  per repository directory rather than per revision

**To force a full re-run, use `--force`:**

```bash
docker compose run --rm josseph configs/config.yaml --force
```

`--force` bypasses the cache check and re-runs all extractors for all
repositories, overwriting existing artifacts.

Alternatively, delete `results/` manually before running.

## Why is `nodejs` installed in the Docker image?

SonarQube Scanner CLI requires Node.js at runtime for certain analysis
operations. It is not used directly by the JOSSeph Python code.
