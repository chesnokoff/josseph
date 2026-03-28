# Config

This page defines the run configuration contract.

## Minimal valid config

```yaml
repositories: configs/repos.txt
tools:
  - github
  - ck
clone_depth: 1
workers: 2
```

## Field contract

| Field | Required | Type | Validation | Runtime effect |
| --- | --- | --- | --- | --- |
| `repositories` | yes | string | must point to an existing file; file must yield at least one repository URL after removing blanks and comments | defines the repository set for the run |
| `tools` | no | string or list of strings | empty names rejected; duplicates removed while preserving first occurrence | selects extractors; omitted means all registered extractors |
| `clone_depth` | no | positive integer or numeric string | values below `1` are rejected | passed to `git clone --depth` |
| `workers` | no | positive integer or numeric string | values below `1` are rejected | upper bound for parallel repository processing |
| `github_token` | no | string | empty string becomes unset | exported as `GITHUB_TOKEN` for runtime |
| `extractor_settings` | no | mapping | each extractor key must be non-empty; each value must be a mapping or `null` | passed to extractor factory |

## Strict rules that matter in production

- Paths in `repositories` are resolved relative to the YAML file.
- `~` is expanded before resolution.
- A repository file containing only comments and blank lines is invalid.
- `workers` defaults to `os.cpu_count()` when omitted.
- non-empty `github_token` values are redacted to `***redacted***` in the run summary.

## Repository file example

Input file:

```text
# configs/repos.txt
https://github.com/example/alpha.git

https://github.com/example/beta.git
https://github.com/example/alpha.git
```

Effective repository list in the run summary:

```json
[
  "https://github.com/example/alpha.git",
  "https://github.com/example/beta.git"
]
```

## Extractor settings example

```yaml
repositories: configs/repos.txt
tools:
  - github
  - cm
  - sonar
extractor_settings:
  github:
    token: ghp_example
  cm:
    timeout_seconds: 1800
  sonar:
    host_url: http://localhost:9234
    include_frontend: false
    options: -Dsonar.sources=.
```

This is a contract, not a suggestion:

- unknown extractor setting names fail before execution
- invalid setting types fail before execution
- unknown tool names fail before execution

## Invalid config examples

Broken YAML:

```yaml
repositories: [unterminated
```

Invalid worker count:

```yaml
repositories: configs/repos.txt
workers: 0
```

Invalid extractor settings:

```yaml
repositories: configs/repos.txt
extractor_settings:
  - invalid
```

## Exit behavior

- config load failure returns exit code `2`
- if config fails before `RunReportCollector` is created, no `summary.json` is written
- if config loads but runtime preparation fails later, `summary.json` is still written with `exit_code: 2`
