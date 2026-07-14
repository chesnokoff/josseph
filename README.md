# JOSSeph

[![Tests](https://github.com/chesnokoff/josseph/actions/workflows/test.yml/badge.svg)](https://github.com/chesnokoff/josseph/actions/workflows/test.yml)
[![Integration](https://github.com/chesnokoff/josseph/actions/workflows/integration.yml/badge.svg)](https://github.com/chesnokoff/josseph/actions/workflows/integration.yml)
[![Docs](https://github.com/chesnokoff/josseph/actions/workflows/deploy-docs.yml/badge.svg)](https://chesnokoff.github.io/josseph/)
[![DOI](https://zenodo.org/badge/1209711267.svg)](https://doi.org/10.5281/zenodo.19559305)

Container-first pipeline for collecting repository metrics with:
- CK (static code metrics)
- CM (change metrics)
- GitHub API metadata
- SonarQube metrics (`sonar` extractor)

## Project Layout
- `configs/` — YAML configuration files for runs
- `configs/repositories/` — small example repository lists for e2e runs
- `results/` — output directory (mounted from host)
- `josseph/` — Python package and pipeline code
- `docker-compose.yml` — `sonarqube` + `josseph` services
- `Dockerfile` — runtime image for `josseph`

## Prerequisites
- Docker Desktop / Docker Engine with Compose
- A GitHub token is needed only when using the `github` extractor:

```bash
export GITHUB_TOKEN=your_token_here
```

- **Linux only:** SonarQube requires a kernel parameter increase for Elasticsearch:

```bash
sudo sysctl -w vm.max_map_count=524288
```

To make it persistent across reboots, add `vm.max_map_count=524288` to `/etc/sysctl.conf`. This is not required on macOS or Windows (Docker Desktop handles it automatically).

## Quick Start
The checked-in quick-start config runs CK and CM on a pinned revision of
`junit-team/junit4`. It does not need a GitHub token or SonarQube:

```bash
docker compose run --rm --build --no-deps josseph configs/quickstart.yaml
```

The config is intentionally small and explicit:

```yaml
tools:
  - ck
  - cm
workers: 1
repositories: repositories/quickstart.yaml
```

On success, `results/junit-team@junit4/` contains paired `.parquet` and `.json`
artifacts for both tools, and `results/runs/<run-id>/summary.json` reports
`"status": "success"`. See the checked-in [sample run](examples/sample-run/).

### Full run

The default config runs all four extractors. Copy the environment template,
set `GITHUB_TOKEN`, and run it; Compose builds the image and starts SonarQube:

```bash
cp .env.example .env
# Edit GITHUB_TOKEN in .env, then:
docker compose run --rm --build josseph configs/config.yaml
```

For a fresh local SonarQube container, `docker-compose.yml` uses a two-step
bootstrap:
- `SONAR_ADMIN_DEFAULT_PASSWORD=admin` is the upstream factory default for a
  new local container
- `SONAR_ADMIN_PASSWORD=Admin#Password12345` is the policy-compliant password
  JOSSeph sets on first run

Override these values in `.env` only for your local container lifecycle. Keep
`SONAR_ADMIN_DEFAULT_PASSWORD` aligned with the current admin password of that
local SonarQube instance, and ensure `SONAR_ADMIN_PASSWORD` satisfies the
current SonarQube password policy.

The checked-in full config is `configs/config.yaml`:

```yaml
tools:
  - ck
  - cm
  - github
  - sonar
workers: 1
repositories: repositories/one-repo.yaml
```

## Configuration Format
The container reads `/app/configs/config.yaml` by default.

Supported keys:
- `tools`: optional list of extractors (`ck`, `cm`, `github`, `sonar`); omitted means all
- `extractor_settings`: optional mapping of extractor name to extractor-specific settings
- `workers`: optional positive integer; omitted means CPU count
- `github_token`: optional token value; if omitted, `GITHUB_TOKEN` from the environment is used
- `repositories`: path to a YAML file whose root is a sequence of repository entries; entries may include an optional `commit`

Path in `repositories` is resolved relative to the YAML file.
Pinned commits are only supported when they are reachable from the repository's
default branch.

## Outputs
Results are written to:
- `results/<owner>@<repo>/ck.parquet`
- `results/<owner>@<repo>/cm.parquet`
- `results/<owner>@<repo>/github.parquet`
- `results/<owner>@<repo>/sonar.parquet`
- `results/<owner>@<repo>/*.json` (metadata with `commit_hash`, `requested_commit_hash`, `metric_binding`, and `collected_at_utc`)
- `results/runs/<run-id>/summary.json` (pipeline-level run metadata)

Results are stored per repository, not per repository revision. A later run for
the same repository can overwrite earlier artifacts; the requested commit is
captured in per-tool metadata and in the run summary.

A metric is considered complete only when both files exist:
- `results/<owner>@<repo>/<tool>.parquet`
- `results/<owner>@<repo>/<tool>.json`

## Common Commands
- Rebuild image after code changes:

```bash
docker compose build josseph
```

- Stop SonarQube:

```bash
docker compose stop sonarqube
```

- Remove SonarQube container/network:

```bash
docker compose down
```

## Notes
- This setup is container-first for reproducibility.
- Cloned repositories live in `workspace/projects/` by default and are mounted into the container from `./workspace`.
- Analysis helpers and operational scripts may live outside the repo in a sibling tools directory.
- `GITHUB_TOKEN` is passed from host environment into `josseph` via `docker-compose.yml`.
- `sonar` analysis may be slower on large repositories.
- Sonar Scanner is downloaded from the official SonarSource CDN at Docker build time, pinned to version `7.0.2.4839` (see `third_party/sonar-scanner/README.md`).

## Reproducibility Contract
- Runtime dependencies are pinned in `requirements.txt`.
- Unknown tool names fail fast (`tools:` validates against the registered extractors).
- The process exit code is strict:
  - `0`: all repositories processed without top-level failures
  - `1`: one or more repositories failed during analysis
  - `2`: invalid user input/configuration (for example, unknown tool)
- Cached results are reused only when both `<tool>.parquet` and `<tool>.json` are present;
  for revision-bound extractors with a pinned commit, the `commit_hash` recorded in
  `<tool>.json` must also match the requested commit.
- `observation-bound` extractors are still cacheable by file presence; use
  `--force` to recollect them.

## Third-Party Licenses

JOSSeph relies on the following third-party tools (CK and CM are vendored;
Sonar Scanner is downloaded at image build time; SonarQube runs as a Docker
service). All licenses are compatible with the project's MIT license.

| Tool | Version | License | Source |
|------|---------|---------|--------|
| CK | 0.7.1 | Apache 2.0 | [github.com/mauricioaniche/ck](https://github.com/mauricioaniche/ck) |
| CM | — | Apache 2.0 | [github.com/mauricioaniche/change-metrics](https://github.com/mauricioaniche/change-metrics) |
| Sonar Scanner | 7.0.2.4839 | LGPL 3.0 | [github.com/SonarSource/sonar-scanner-cli](https://github.com/SonarSource/sonar-scanner-cli) |
| SonarQube (Docker) | 25.5.0.107428-community | LGPL 3.0 | [github.com/SonarSource/sonarqube](https://github.com/SonarSource/sonarqube) |

## Extensibility API
To add a new metrics source:
1. Add a new module under `josseph/metrics/extractors/`, for example `my_extractor.py`.
2. In that module:
   - define `EXTRACTOR_NAME = "my_extractor"`
   - implement `build_extractor(context, settings)`
   - implement an extractor class that subclasses `MetricExtractor`
3. List the extractor name under `tools:` in the YAML config.
4. Set `metric_binding` on the extractor class:
   - default is `revision-bound`
   - use `observation-bound` for time-dependent extractors
5. Pass extractor-specific parameters under `extractor_settings:` when needed.

Example:

```yaml
tools:
  - github
  - my_extractor

extractor_settings:
  my_extractor:
    threshold: 10
```

Minimal extractor module:

```python
from josseph.metrics.abstract_extractor import MetricExtractor

EXTRACTOR_NAME = "my_extractor"


class MyExtractor(MetricExtractor):
    requires_checkout = False
    metric_binding = "revision-bound"

    def __init__(self, threshold: int) -> None:
        self.threshold = threshold

    def run(self, target):
        return [{"threshold": self.threshold, "repo": target.project_name}]


def build_extractor(context, settings):
    threshold = int(settings.get("threshold", 10))
    return MyExtractor(threshold=threshold)
```
