# Getting Started

This page walks through the shortest useful path from "no setup" to "I have
results".

## 1. Prepare a repository list

Create a text file with one repository per line:

```text
https://github.com/example/project.git
https://github.com/example/another-project.git
```

Blank lines and `#` comments are okay.

## 2. Create a config file

Start with this:

```yaml
repositories: configs/repos.txt
tools:
  - github
  - ck
clone_depth: 1
workers: 2
```

Save it as something like `configs/run.yaml`.

## 3. Run JOSSeph

Use the config path as the last argument:

```bash
docker compose run --rm josseph configs/run.yaml
```

If you want to run it locally instead of through Docker:

```bash
python -m josseph configs/run.yaml
```

## 4. Find the results

After a successful run, look under `results/`:

```text
results/
  example@project/
    github.parquet
    github.json
    ck.parquet
    ck.json
  runs/
    <run-id>/
      summary.json
```

## 5. If you use GitHub or Sonar

Some tools need extra setup:

- `github` works best with a token in `github_token` or `GITHUB_TOKEN`
- `sonar` needs a reachable SonarQube server

If you do not need those tools, leave them out of `tools:`.
