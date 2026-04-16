# Architecture

JOSSeph is a layered Python pipeline with a Docker-first execution model.

## Module map

```
josseph/
├── domain/          — value objects (RepositoryRef, AnalysisTarget)
├── providers/       — external API clients (GitHub, SonarQube)
├── metrics/
│   ├── abstract_extractor.py  — MetricExtractor ABC
│   ├── registry.py            — ExtractorRegistry (auto-discovery)
│   └── extractors/            — concrete extractor modules (ck, cm, github, sonar)
├── pipeline/
│   ├── config.py              — YAML loading and validation → AnalysisConfig
│   ├── repositories.py        — repository list parsing
│   ├── cloner.py              — git clone / cleanup (RepositoryCloner)
│   ├── analyzer.py            — per-repository orchestration (RepositoryAnalyzer)
│   ├── runner.py              — parallel execution (AnalysisRunner, ThreadPoolExecutor)
│   ├── results.py             — artifact writing (ResultWriter, ResultDirectoryManager)
│   ├── run_report.py          — run summary collection (RunReportCollector)
│   ├── extractor_factory.py   — extractor selection from registry
│   └── app.py                 — pipeline entrypoint (RepositoryAnalysisPipeline)
├── process.py       — CommandRunner protocol + SubprocessCommandRunner
├── utils.py         — path constants, logging setup, HTTP retry helpers
└── __main__.py      — CLI entrypoint (argparse)
```

## Execution flow

```
docker compose run --rm josseph configs/config.yaml
        │
        ▼
__main__.py          parse args → RepositoryAnalysisPipeline.run(args)
        │
        ▼
config.py            load YAML → AnalysisConfig
                     resolve repositories file → list[RepositorySpec]
        │
        ▼
registry.py          auto-discover extractor modules via pkgutil.iter_modules
                     build_extractor() called for each selected tool
        │
        ▼
runner.py            ThreadPoolExecutor(workers)
   for each repo ──► analyzer.py  RepositoryAnalyzer.analyze(repo_spec)
        │
        ├── checkout-free extractors (github) ──► extractor.run(target)
        │
        └── checkout-required extractors (ck, cm, sonar)
                │
                ▼
            cloner.py  git clone → project_dir (temp, cleaned up after)
                │
                ▼
            git rev-parse HEAD → commit_hash
                │
                ▼
            extractor.run(target_with_checkout)
        │
        ▼
results.py           write <tool>.parquet + <tool>.json per extractor
        │
        ▼
run_report.py        write results/runs/<run-id>/summary.json
```

## Key design decisions

### Contract-driven caching

A cached result is valid only when **both** files are present:

- `results/<owner>@<repo>/<tool>.parquet`
- `results/<owner>@<repo>/<tool>.json`

If only one exists, the extractor reruns. This prevents partial writes from
being silently treated as complete.

`observation-bound` extractors use the same cache contract; the distinction is
documented for reproducibility, not for automatic cache invalidation.

### Extractor isolation

Each extractor is a self-contained module under `josseph/metrics/extractors/`.
Failures are caught per-extractor and recorded in `summary.json`; the pipeline
continues with remaining extractors and repositories.

### Protocol-based dependency injection

`CommandRunner` is a protocol (structural subtyping). Tests inject a fake
implementation without modifying production code. This also makes it possible
to swap out subprocess execution for other backends.

### Checkout-free / checkout-required split

Extractors declare `requires_checkout: bool`. The analyzer splits them into two
groups and runs the checkout-free group before cloning. This avoids a full git
clone when only API-based extractors are needed.

Pinned repository commits are only supported when reachable from the
repository's default branch. The clone step still checks out the requested
commit after cloning.

## Adding a new extractor

The extractor API contract is intentionally small. In short:

1. Add `josseph/metrics/extractors/my_extractor.py`
2. Define `EXTRACTOR_NAME`, `build_extractor(context, settings)`, and a
   `MetricExtractor` subclass
3. Reference the name in `tools:` in your config YAML

The registry discovers the module automatically via `pkgutil.iter_modules`.
No registration step is required.

## Limitations

- Java-only: CK and CM filter for `.java` files; SonarQube default exclusions
  drop non-Java code.
- Single host: SonarQube runs on the same Docker network as the pipeline.
  There is no multi-host or cloud SonarQube support.
- Cache staleness: cached results are reused based on file presence, not
  content fingerprint. If you change configs, tool versions, or pinned commits,
  clear `results/` or use `--force`.
