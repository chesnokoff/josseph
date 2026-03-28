# FAQ

## Do I need Docker?

No. Docker is the default path, but you can also run:

```bash
python -m josseph configs/run.yaml
```

## What should I put in `repositories`?

A text file with one repository URL per line.

```text
https://github.com/example/project.git
```

## Why is a result missing?

Usually one of these:

- the tool was not selected in `tools:`
- the tool failed for that repository
- the result was already cached and reused

Check `results/runs/<run-id>/summary.json` for details.

## Can I run only one tool?

Yes.

```yaml
repositories: configs/repos.txt
tools:
  - github
```

## What if I use Sonar?

Start SonarQube first, then run JOSSeph.

```bash
docker compose up -d sonarqube
docker compose run --rm josseph configs/run.yaml
```

## How do I know the run finished?

Look for the run summary:

```text
results/runs/<run-id>/summary.json
```

If it exists, the run reached the reporting step.
