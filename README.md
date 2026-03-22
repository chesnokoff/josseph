# oss-metrics

Container-first pipeline for collecting repository metrics with:
- CK (static code metrics)
- CM (change metrics)
- GitHub API metadata
- SonarQube metrics (`sonar` extractor)

## Project Layout
- `configs/` — YAML configuration files for runs
- `data/` — repository lists and workspace data
- `results/` — output directory (mounted from host)
- `josseph/` — Python package and pipeline code
- `docker-compose.yml` — `sonarqube` + `josseph` services
- `Dockerfile` — runtime image for `josseph`

## Prerequisites
- Docker Desktop / Docker Engine with Compose
- A GitHub token in shell environment (recommended):

```bash
export GITHUB_TOKEN=your_token_here
```

## Quick Start
1. Build the app image:

```bash
docker compose build josseph
```

2. Start SonarQube:

```bash
docker compose up -d sonarqube
```

3. Configure the run in `configs/config.yaml`.

Example:

```yaml
tools:
  - ck
  - cm
  - github
  - sonar
clone_depth: 1
workers: 1
repositories: ../data/repos.txt
```

4. Run the pipeline:

```bash
docker compose run --rm josseph
```

## Configuration Format
The container reads `/app/configs/config.yaml` by default.

Supported keys:
- `tools`: optional list of extractors (`ck`, `cm`, `github`, `sonar`); omitted means all
- `extractor_settings`: optional mapping of extractor name to extractor-specific settings
- `clone_depth`: optional positive integer for shallow clone depth
- `workers`: optional positive integer; omitted means CPU count
- `github_token`: optional token value; if omitted, `GITHUB_TOKEN` from the environment is used
- `repositories`: path to a text file with one repository URL per line

Path in `repositories` is resolved relative to the YAML file.

## Outputs
Results are written to:
- `results/<owner>@<repo>/ck.parquet`
- `results/<owner>@<repo>/cm.parquet`
- `results/<owner>@<repo>/github.parquet`
- `results/<owner>@<repo>/sonar.parquet`
- `results/<owner>@<repo>/*.json` (metadata)

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
- `GITHUB_TOKEN` is passed from host environment into `josseph` via `docker-compose.yml`.
- `sonar` analysis may be slower on large repositories.
- Sonar Scanner is vendored in `third_party/sonar-scanner` at a fixed version (`7.0.2.4839`).

## Reproducibility Contract
- Runtime dependencies are pinned in `requirements.txt`.
- Unknown tool names fail fast (`tools:` validates against the registered extractors).
- The process exit code is strict:
  - `0`: all repositories processed without top-level failures
  - `1`: one or more repositories failed during analysis
  - `2`: invalid user input/configuration (for example, unknown tool)
- Cached results are reused only when both `<tool>.parquet` and `<tool>.json` are present.

## Extensibility API
To add a new metrics source:
1. Add a new module under `josseph/metrics/extractors/`, for example `my_extractor.py`.
2. In that module:
   - define `EXTRACTOR_NAME = "my_extractor"`
   - implement `build_extractor(context, settings)`
   - implement an extractor class that subclasses `MetricExtractor`
3. List the extractor name under `tools:` in the YAML config.
4. Pass extractor-specific parameters under `extractor_settings:` when needed.

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

    def __init__(self, threshold: int) -> None:
        self.threshold = threshold

    def run(self, target):
        return [{"threshold": self.threshold, "repo": target.project_name}]


def build_extractor(context, settings):
    threshold = int(settings.get("threshold", 10))
    return MyExtractor(threshold=threshold)
```
