# Architecture

This page is technical reference material.

## Main parts

- CLI entrypoint
- config loader
- pipeline runner
- repository analyzer
- cloning helper
- result writer
- run summary collector
- extractor registry
- external providers

## Why it is split this way

The split keeps one job simple:

- users edit config and read results
- internal components handle retries, cleanup, and reporting

## External dependencies

- GitHub API
- SonarQube
- vendored CK and CM jars
