# AGENT.md — Project Overview

## What Is This Project?
`hyper_web_sim` is an experimental project workspace dedicated to evaluating the graph-relational hybrid memory substrate. It houses the empirical benchmark databases and result telemetry testing progressive disclosure, multi-lens conflict resolution, teleological drift detection, and self-healing topologies.

---

## How It Works & Key Components
* **Core Logic:** Contains empirical validation suites and trial results across four foundational substrate experiments:
  * `exp1_benchmark.*`: Tests progressive disclosure via OpenGraph link previews against full relational row ingestion.
  * `exp2_benchmark.*`: Tests circular dependency pruning and schema conflict resolution using semantic lenses (`WHERE lens = 'dependency'`).
  * `exp3_benchmark.*`: Tests objective manifold deviation tracking to detect teleological agent drift at query boundaries.
  * `exp4_benchmark.*`: Tests autonomous remediation where an agent injects dynamic transformation nodes to heal failing pipelines across three lenses (`dependency`, `pipeline`, `provenance`).
* **Data & Storage:** Local SQLite database at `project.db`, supplemented by dedicated benchmark trial databases (`exp1_benchmark.db` through `exp4_benchmark.db`) with corresponding JSON result telemetry files.

---

## Operational Rules & Notes
* Benchmark artifacts and SQLite databases run in WAL mode with foreign key constraints enabled.
* Result metrics in the `exp*_benchmark_results.json` files capture trial-by-trial measurements including token counts, precision, recall, and recovery latency.
