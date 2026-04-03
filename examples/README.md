# Examples

This directory contains reference outputs from a real JOSSeph run on one small
repository (`https://github.com/GregorStocks/mage-bench`) using the
`configs/one-repo.yaml` config with `tools: [github, ck]`.

## Directory tree

```
examples/sample-run/
  GregorStocks@mage-bench/
    github.json          — metadata for github extractor
    github.parquet       — github metrics table (not committed; binary)
    ck.json              — metadata for ck extractor
    ck.parquet           — CK class/method metrics table (not committed; binary)
  runs/
    20260328T120000Z/
      summary.json       — pipeline-level run summary
```

Parquet files are not committed to the repository (binary, potentially large).
The `.json` sidecar files are committed as reference artifacts for format
verification.

## How to reproduce

```bash
cp .env.example .env
# edit .env and set GITHUB_TOKEN and SONAR_ADMIN_PASSWORD

docker compose build josseph
docker compose up -d sonarqube
docker compose run --rm josseph /app/configs/one-repo.yaml
```

Results appear under `results/GregorStocks@mage-bench/`.

## How to load parquet outputs in Python

```python
import pandas as pd

# Load CK class-level metrics
ck = pd.read_parquet("results/GregorStocks@mage-bench/ck.parquet")
print(ck.columns.tolist())
print(ck.head())

# Load GitHub metadata
gh = pd.read_parquet("results/GregorStocks@mage-bench/github.parquet")
print(gh)
```

## How to join metrics across extractors

```python
import pandas as pd

ck = pd.read_parquet("results/GregorStocks@mage-bench/ck.parquet")
gh = pd.read_parquet("results/GregorStocks@mage-bench/github.parquet")

# Add repository-level context to all class rows
gh_row = gh.iloc[0]
ck["repo_stars"] = gh_row["stargazers_count"]
ck["repo_forks"] = gh_row["forks_count"]

print(ck[["file", "class", "wmc", "cbo", "repo_stars"]].head(10))
```
