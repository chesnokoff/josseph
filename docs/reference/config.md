# Config Details

This page is for users who want the exact rules behind the config file.

## YAML rules

- the config file must be a YAML mapping at the root
- `repositories` must be a string
- `tools` may be a string or a list of strings
- `extractor_settings` must be a mapping
- `workers` and `clone_depth` must be positive integers when set

## Repository file rules

- blank lines are ignored
- `#` comments are ignored
- duplicate entries are removed after loading
- the path is resolved relative to the YAML file
- `~` is supported

## Tool rules

- empty tool names are rejected
- duplicate tool names are ignored after the first one
- unknown tool names fail before the run starts

## Supported extra settings

- `github.token`
- `cm.timeout_seconds`
- `sonar.instance_port`
- `sonar.host_url`
- `sonar.admin_user`
- `sonar.admin_password`
- `sonar.admin_default_password`
- `sonar.empty_binaries_dir`
- `sonar.exclusions`
- `sonar.include_frontend`
- `sonar.options`

Anything else fails fast when the extractor is built.
