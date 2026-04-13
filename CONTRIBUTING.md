# Contributing

## Development setup

```bash
git clone https://github.com/chesnokoff/josseph.git
cd josseph

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install the package with dev dependencies
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v
```

Tests are deterministic and require no network access, Docker, or external
services. All external dependencies (subprocess, GitHub API, SonarQube) are
replaced with fakes or stubs.

## Adding a new extractor

1. Create `josseph/metrics/extractors/my_extractor.py`.
2. Define the required module-level symbols:
   ```python
   EXTRACTOR_NAME = "my_extractor"

   def build_extractor(context, settings):
       ...

   class MyExtractor(MetricExtractor):
       requires_checkout = False  # or True

       def run(self, target):
           return [{"field": value, ...}]
   ```
3. The registry discovers the module automatically via `pkgutil.iter_modules`.
   No registration step is required.
4. Add tests under `tests/test_extractors.py` or a new test module.
5. Document the new extractor in `docs/metrics.md`.

See `josseph/metrics/abstract_extractor.py` for the full `MetricExtractor`
contract.

## Module structure

| Module | Responsibility |
|--------|----------------|
| `josseph/domain/` | Value objects: `RepositoryRef`, `AnalysisTarget` |
| `josseph/providers/` | External API clients (GitHub, SonarQube) |
| `josseph/metrics/` | Extractor ABC, registry, concrete extractors |
| `josseph/pipeline/` | Config loading, cloning, analysis, result writing |
| `josseph/process.py` | `CommandRunner` protocol + subprocess implementation |
| `josseph/utils.py` | Path constants, logging setup, HTTP retry helpers |

## Code style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting. Run before
submitting:

```bash
ruff check josseph/ tests/
```

Type hints are required for all new code. Run mypy to verify:

```bash
mypy josseph/
```

## Cache invalidation

If you change extractor output schemas or tool versions in a development run,
clear `results/` or pass `--force` to avoid stale cached results:

```bash
docker compose run --rm josseph /app/configs/config.yaml --force
```

## Submitting changes

1. Fork the repository.
2. Create a feature branch.
3. Ensure `pytest tests/ -v` passes.
4. Open a pull request with a description of what changes and why.
