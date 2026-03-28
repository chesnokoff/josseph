# JOSSeph

JOSSeph turns a list of GitHub repositories into ready-to-use metrics files.
It collects repository metadata, code metrics, and SonarQube metrics, then
writes the results to predictable files you can inspect or feed into another
tool.

## Start here

If you want the shortest path to a result, go to:

1. [Getting Started](getting-started.md)
2. [Config](config.md)
3. [Examples](examples.md)
4. [Output](output.md)

## What you do

You give JOSSeph:

- a YAML config
- a text file with repository URLs
- optional access tokens if you want GitHub metadata

JOSSeph gives you:

- one Parquet file per repository and tool
- a small JSON file next to each result
- a run summary for the whole execution

## Quick start

```bash
cat > configs/repos.txt <<'EOF'
https://github.com/example/project.git
EOF

cat > configs/run.yaml <<'EOF'
repositories: configs/repos.txt
tools:
  - github
  - ck
clone_depth: 1
workers: 2
EOF

docker compose run --rm josseph configs/run.yaml
```

After the run finishes, look in:

- `results/example@project/github.parquet`
- `results/example@project/github.json`
- `results/example@project/ck.parquet`
- `results/example@project/ck.json`
- `results/runs/<run-id>/summary.json`

## Documentation site

To preview or publish this documentation:

```bash
pip install mkdocs-material
mkdocs serve
mkdocs gh-deploy --force
```
