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

A YAML sequence of repository URLs. Each entry is either a plain string or a
mapping with a `url` and an optional pinned `commit`.

```yaml
- https://github.com/example/project.git
```

Duplicate URLs are removed after loading. Pinned commits are only supported
when the commit is reachable from the repository's default branch.

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
repositories: repositories/one-repo.yaml
tools:
  - github
```

If you save that config under `configs/`, the repository path resolves to
`configs/repositories/one-repo.yaml`.

## What should I verify after a run?

1. exit code
2. `results/runs/<run-id>/summary.json`
3. expected `<tool>.parquet` and `<tool>.json` pairs for each repository

## How do I build a repository list?

Repository selection is out of JOSSeph's scope by design. Use a dedicated
sampling tool such as [SEART GitHub Search](https://seart-ghs.si.usi.ch)
to filter GitHub projects by language, stars, activity, and other criteria,
then convert its JSON export into a JOSSeph repository list:

```bash
jq -r '.items[].name | "- " + .' results.json > repos.yaml
```

The resulting `owner/name` entries are accepted as-is.

## How does caching work, and when should I clear results?

JOSSeph reuses a cached result whenever **both** `<tool>.parquet` and
`<tool>.json` exist for a given repository and tool. For revision-bound
extractors with a pinned commit, the `commit_hash` recorded in `<tool>.json`
must additionally match the requested commit — pinning a different commit
therefore triggers a re-run automatically. There is no content fingerprint
beyond that.

`observation-bound` extractors are cached by file presence only.

This means stale results can accumulate if you:

- change your config in ways the cache cannot see (e.g. add extractor settings)
- update a tool version (CK, CM, SonarQube, Sonar Scanner)
- repoint a repository list to different repos with the same project name

**To force a full re-run, use `--force`:**

```bash
docker compose run --rm josseph configs/config.yaml --force
```

`--force` bypasses the cache check and re-runs all extractors for all
repositories, overwriting existing artifacts.

Alternatively, delete `results/` manually before running.

## SonarQube fails to start on Linux

SonarQube uses Elasticsearch internally, which requires the kernel parameter
`vm.max_map_count` to be at least `262144`. The default on most Linux
distributions is `65530`, which causes SonarQube to crash on startup.

Run this before starting the pipeline:

```bash
sudo sysctl -w vm.max_map_count=524288
```

To make it persistent, add to `/etc/sysctl.conf`:

```
vm.max_map_count=524288
```

This is **not needed** on macOS or Windows — Docker Desktop sets this
automatically in its Linux VM.

## Why is `nodejs` installed in the Docker image?

SonarQube Scanner CLI requires Node.js at runtime for certain analysis
operations. It is not used directly by the JOSSeph Python code.
