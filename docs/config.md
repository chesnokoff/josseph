# Config

This page shows the YAML file you edit before every run.

## Minimal config

```yaml
repositories: configs/repos.txt
tools:
  - github
  - ck
clone_depth: 1
workers: 2
```

## What each field means

- `repositories`: path to the file with repository URLs
- `tools`: which metrics to collect
- `clone_depth`: how shallow the clone should be
- `workers`: how many repositories to process at the same time
- `github_token`: optional token for GitHub metadata
- `extractor_settings`: extra settings for specific tools

## Tool selection

If you want every available tool, you can omit `tools`.

```yaml
repositories: configs/repos.txt
```

If you want only a few, list them:

```yaml
tools:
  - github
  - ck
```

## Extra tool settings

Use `extractor_settings` when a tool needs a tweak:

```yaml
repositories: configs/repos.txt
tools:
  - cm
  - sonar
extractor_settings:
  cm:
    timeout_seconds: 3600
  sonar:
    host_url: http://localhost:9234
    include_frontend: false
```

## Common mistakes

- The `repositories` file does not exist
- A tool name is misspelled
- `workers` is `0` or a negative number
- `clone_depth` is `0` or a negative number
- `extractor_settings` is not a mapping

If any of those happen, JOSSeph stops before the run starts.
