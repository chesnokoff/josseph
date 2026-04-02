# Metrics Reference

JOSSeph currently ships four extractors. Each is a self-contained module under
`josseph/metrics/extractors/`.

---

## ck — Static object-oriented metrics

**Tool:** [CK](https://github.com/mauricioaniche/ck) by Maurício Aniche et al.

**Requires checkout:** yes

**What it measures:**

CK computes class- and method-level static metrics for Java source code.
The most commonly used metrics include:

| Metric | Description |
|--------|-------------|
| CBO | Coupling Between Objects — number of classes a class depends on |
| WMC | Weighted Methods per Class — sum of cyclomatic complexities |
| DIT | Depth of Inheritance Tree |
| NOC | Number of Children (direct subclasses) |
| RFC | Response For a Class — number of methods that can be invoked |
| LCOM | Lack of Cohesion of Methods |
| LOC | Lines of code (class and method level) |
| NOM | Number of Methods |
| NOSI | Number of Static Invocations |

CK emits one row per class and one row per method. Both are written as separate
parquet files (see output docs for schema).

**Citation:** Aniche, M. (2021). *mauricioaniche/ck*. GitHub.

---

## cm — Change metrics

**Tool:** [CM](https://github.com/mauricioaniche/code-changes-miner) — process
metrics derived from git history.

**Requires checkout:** yes

**What it measures:**

CM processes the git commit log to produce change-based (process) metrics at
the file and class level:

| Metric | Description |
|--------|-------------|
| revisions | Number of commits that touched this file |
| bugFixes | Commits with keywords indicating a bug fix |
| authors | Number of distinct authors |
| LOC added | Total lines added across all commits |
| LOC removed | Total lines removed across all commits |
| codeCHurn | LOC added + LOC removed |
| firstCommit | Timestamp of earliest commit touching the file |
| lastCommit | Timestamp of most recent commit touching the file |

Process metrics capture how actively and riskily a file has been changed, which
correlates with defect density in empirical software engineering research.

**Scope:** CM filters for `.java` files only.

---

## github — GitHub repository metadata

**Tool:** GitHub REST API (v3)

**Requires checkout:** no

**What it measures:**

The `github` extractor calls the GitHub API to collect project-level metadata:

| Field | Description |
|-------|-------------|
| stars | Repository stargazer count |
| forks | Fork count |
| watchers | Watcher count |
| open_issues | Open issue count |
| created_at | Repository creation timestamp |
| pushed_at | Last push timestamp |
| size | Repository size in KB |
| language | Primary language reported by GitHub |
| license | SPDX license identifier |
| topics | Repository topic tags |
| has_wiki | Whether the wiki is enabled |
| archived | Whether the repository is archived |

**Authentication:** A `GITHUB_TOKEN` environment variable is strongly
recommended to avoid rate limiting (5000 req/hour authenticated vs. 60
unauthenticated).

---

## sonar — SonarQube maintainability and reliability metrics

**Tool:** [SonarQube Community Edition](https://www.sonarsource.com/products/sonarqube/)
with [Sonar Scanner CLI](https://docs.sonarsource.com/sonarqube-server/latest/analyzing-source-code/scanners/sonarscanner/)

**Requires checkout:** yes

**What it measures:**

SonarQube performs a static analysis scan and exposes aggregated project-level
measures:

| Metric | Description |
|--------|-------------|
| bugs | Number of detected bugs |
| vulnerabilities | Security vulnerability count |
| code_smells | Maintainability issue count |
| coverage | Line coverage percentage (if test data present) |
| duplicated_lines_density | Percentage of duplicated lines |
| ncloc | Non-comment lines of code |
| sqale_index | Technical debt in minutes |
| reliability_rating | A–E rating for reliability |
| security_rating | A–E rating for security |
| sqale_rating | A–E rating for maintainability |
| cognitive_complexity | Cognitive complexity score |

**Note:** Coverage metrics require test execution data (JaCoCo or similar).
Without test data, `coverage` will be `0.0`.

**Infrastructure:** SonarQube runs as a local Docker container started via
`docker compose up -d sonarqube`. JOSSeph creates a temporary project per
repository, scans it, reads the measures, then deletes the project. Each run
is isolated.
