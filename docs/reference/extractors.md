# Extractors

This page lists the tools you can run.

## `github`

- reads GitHub repository metadata
- does not need a local checkout
- writes one row of repository metadata
- fails if GitHub cannot be reached or returns an error

## `ck`

- reads static code metrics
- needs a local checkout
- writes rows from CK output
- fails if the CK jar is missing or the command fails

## `cm`

- reads change metrics
- needs a local checkout
- keeps only Java source rows
- lets you set `timeout_seconds`

## `sonar`

- reads SonarQube metrics
- needs a local checkout
- also needs a reachable SonarQube server
- fails if the scanner or server setup fails

## When a tool fails

The run keeps going for other tools and repositories. Check `summary.json` to
see the failure reason.
