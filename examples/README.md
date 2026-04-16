# Examples

This directory contains reference outputs from real JOSSeph runs:
- `GregorStocks@mage-bench`: a minimal example with committed `github.json` and `ck.json`
- `doocs@advanced-java`: a fuller multi-extractor example with committed `github`, `ck`, `cm`, and `sonar` outputs in both `.json` and `.parquet` formats

## Directory tree

```
examples/sample-run/
  GregorStocks@mage-bench/
    github.json          — metadata for github extractor
    ck.json              — metadata for ck extractor
  doocs@advanced-java/
    github.json          — metadata for github extractor
    github.parquet       — github metrics table
    ck.json              — metadata for ck extractor
    ck.parquet           — CK class/method metrics table
    cm.json              — metadata for change metrics extractor
    cm.parquet           — change metrics table
    sonar.json           — metadata for SonarQube extractor
    sonar.parquet        — SonarQube metrics table
  runs/
    20260328T120000Z/
      summary.json       — pipeline-level run summary
```

Some examples include only `.json` sidecars, while others intentionally include
small `.parquet` files as loadable reference artifacts.

## How to reproduce

```bash
cp .env.example .env
# edit .env and set GITHUB_TOKEN and SONAR_ADMIN_PASSWORD

docker compose build josseph
docker compose up -d sonarqube
docker compose run --rm josseph configs/one-repo.yaml
```

Results appear under `results/<owner>@<repo>/`.

## How to load parquet outputs in Python

```python
import pandas as pd

# Load CK class-level metrics
ck = pd.read_parquet("examples/sample-run/doocs@advanced-java/ck.parquet")
print(ck.columns.tolist())
print(ck.head())

# Load GitHub metadata
gh = pd.read_parquet("examples/sample-run/doocs@advanced-java/github.parquet")
print(gh)
```

## How to join metrics across extractors

```python
import pandas as pd

ck = pd.read_parquet("examples/sample-run/doocs@advanced-java/ck.parquet")
gh = pd.read_parquet("examples/sample-run/doocs@advanced-java/github.parquet")

# Add repository-level context to all class rows
gh_row = gh.iloc[0]
ck["repo_stars"] = gh_row["stargazers_count"]
ck["repo_forks"] = gh_row["forks_count"]

print(ck[["file", "class", "wmc", "cbo", "repo_stars"]].head(10))
```
