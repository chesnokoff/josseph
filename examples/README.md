# Examples

This directory contains reference output from the real quickstart run on the
pinned `junit-team/junit4` revision. It includes only the CK and CM extractors,
so it needs neither credentials nor SonarQube.

## Directory tree

```text
examples/sample-run/
  junit-team@junit4/
    ck.json              — CK metadata
    ck.parquet           — CK class/method metrics
    cm.json              — change-metrics metadata
    cm.parquet           — change metrics
  runs/
    20260714T212422Z/
      summary.json       — successful pipeline run summary
```

Each extractor has the complete `.parquet` + `.json` artifact pair required by
the result contract.

## How to reproduce

```bash
docker compose run --rm --build --no-deps josseph configs/quickstart.yaml
```

Results appear under `results/junit-team@junit4/`, with the run summary under
`results/runs/<run-id>/summary.json`.

## How to load parquet outputs in Python

```python
import pandas as pd

root = "examples/sample-run/junit-team@junit4"
ck = pd.read_parquet(f"{root}/ck.parquet")
cm = pd.read_parquet(f"{root}/cm.parquet")

print(ck[["file", "class", "wmc", "cbo"]].head())
print(cm[["file", "revisions", "authors"]].head())
```

## How to join metrics across extractors

```python
combined = ck.merge(
    cm[["file", "revisions", "authors"]],
    on="file",
    how="left",
)

print(combined[["file", "class", "wmc", "revisions", "authors"]].head(10))
```
