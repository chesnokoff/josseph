# oss-metrics

Container-first pipeline for collecting repository metrics with:
- CK (static code metrics)
- CM (change metrics)
- GitHub API metadata
- SonarQube metrics (`sonar` extractor)

## Project Layout
- `josseph/` — Python package and pipeline code
- `repos.txt` — default list of repositories (one URL per line)
- `results/` — output directory (mounted from host)
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

3. Run the pipeline:

```bash
docker compose run --rm josseph python -m josseph --workers 1
```

## Repositories Input
By default, `repos.txt` is mounted into the container as `/app/repos.txt`.

- Default file:
  - `./repos.txt`
- Custom file for one run:

```bash
JOSSEPH_REPOS_FILE_HOST=./my-repos.txt docker compose run --rm josseph python -m josseph --workers 1
```

## Outputs
Results are written to:
- `results/<owner>@<repo>/ck.parquet`
- `results/<owner>@<repo>/cm.parquet`
- `results/<owner>@<repo>/github.parquet`
- `results/<owner>@<repo>/sonar.parquet`
- `results/<owner>@<repo>/*.json` (metadata)

## Run Specific Extractors
Run only one or more tools:

```bash
docker compose run --rm josseph python -m josseph --tool ck --tool cm
docker compose run --rm josseph python -m josseph --tool github
docker compose run --rm josseph python -m josseph --tool sonar
```

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
