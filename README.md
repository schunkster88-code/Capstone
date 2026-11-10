# Deterministic Relational Hypergraphs for Bounded-Context Autonomous Systems

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Citation: CFF](https://img.shields.io/badge/Citation-CFF-blue.svg)](./CITATION.cff)
[![Python: 3.14](https://img.shields.io/badge/Python-3.14-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Database: SQLite WAL](https://img.shields.io/badge/Database-SQLite%20WAL-003B57.svg?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Tests: 69 passed](https://img.shields.io/badge/Tests-69%20passed-success.svg)](#)

> **WGU B.S. Computer Science Capstone (C964) / Data Structures & Algorithms Applied Research**  
> **Author:** Wesley A. Schunk  
> **Repository:** `/home/wes/projects/CapStone`  
> **Foundational Specification:** [`CAPSTONE_FOUNDATION.md`](file:///home/wes/projects/CapStone/CAPSTONE_FOUNDATION.md)

---

## 1. Project Overview

Autonomous AI coding agents and state-simulation engines routinely degrade under **unbounded context saturation**. Conventional toolchains treat code repositories and physical world states as flat natural language text, relying on linear string searches (`grep`) or approximate vector search (RAG) to resolve relationships. In complex software ecosystems or stateful environments, this induces attention degradation, dynamic analysis blind spots, and hallucination during multi-file cascades.

This project introduces an alternative architecture: **the workspace as a labeled directed multigraph** $G = (V, E, L)$ stored directly in a high-performance, zero-external-dependency SQLite database operating in Write-Ahead Logging (WAL) mode.

```
       +-----------------------------------------------------------+
       |                  Relational Substrate                     |
       |                   (SQLite 3.45+ WAL)                      |
       +-----------------------------+-----------------------------+
                                     |
               +---------------------+---------------------+
               |                                           |
               v                                           v
   +-----------------------+                   +-----------------------+
   |    substrate_nodes    |                   |      hyper_edges      |
   |-----------------------|                   |-----------------------|
   | coordinate (PK, URI)  | <---------------+ | source (FK)           |
   | node_type             |                 +-| target (FK)           |
   | summary (< 30 tokens) |                   | lens (Discriminator)  |
   | body (Raw code/state) |                   +-----------------------+
   +-----------------------+                               |
               ^                                           |
               +-------------------------------------------+
```

By querying orthogonal relationship layers (**Multiplex Lenses**: `call_graph`, `runtime_trace`, `spatial`, `containment`, `prerequisite`, `perception`, `faction`) through recursive Common Table Expressions (CTEs), multi-hop dependency analysis, dynamic dispatch resolution, and causal bug triangulation occur in **sub-millisecond to single-digit-millisecond latencies**, reducing LLM context window ingestion by **86% to 99.8%**.

---

## 2. Key Empirical Receipts

### The 5-Stage Code Intelligence Gauntlet
Empirically validated on multi-tier production subsystems containing REST APIs, background workers, and dynamic command dispatch registries:

| Stage | Engineering Challenge | Baseline (Grep / LLM Full File) | Relational Substrate Result | Realized Advantage |
| :--- | :--- | :--- | :--- | :--- |
| **1. Structural Navigation** | Trace 3-hop call path from API to disk persistence | 8.86 ms grep scan; 6,478 tokens (21 false positives) | **0.171 ms** CTE query (92.4 ms full repo index); **184.2 tokens** | **51.8x faster**; **97.2% token reduction** |
| **2. Linear Blast Radius** | Propagate parameter across 3-hop caller chain | ~6,000+ tokens (full file dumps) | **1,086 total tokens** (188 plan + 898 execute); 0 extra files read | **~82% token reduction**; 45/45 tests passed |
| **3. Divergent Fan-Out** | Refactor `list_projects` across API and CLI modules | 7,064 tokens; high risk of missing CLI handler | Caught all **5 callers across 3 files**; **942.5 tokens**; 74.8 ms re-index | **86.7% token reduction**; 49/49 tests passed |
| **4. Dynamic Multiplex Lens** | Resolve callers of dynamic dictionary dispatch handlers | **0 callers detected** via static AST (100% blind spot) | **32 invisible runtime edges** captured; full 3-hop lineage restored | **Zero blind spots**; 53/53 tests passed |
| **5. Fault Triangulation** | Isolate root cause of **24 failing tests across 7 test files** | ~14,500+ tokens (7 test files + 4 modules); 15–60s read | **7.251 ms** `INTERSECT` query; pinned Rank #1 culprit in **26.8 tokens** | **>2,000x faster**; **99.81% token reduction**; 56/56 tests passed |

### The 25-Tick Autonomous Campaign Simulation
To verify cross-domain mathematical isomorphism, the identical two-table schema was applied as a deterministic spatial world and state simulation engine:

| Metric | Substrate Multi-Agent Simulation | Traditional LLM Ingestion Baseline | Advantage |
| :--- | :--- | :--- | :--- |
| **Total Ticks Executed** | **25 consecutive ticks** | Variable / Drift-prone | **Strict state progression** |
| **Average Tick Resolution Latency** | **1.472 ms** (Max: 6.461 ms) | ~4,500 – 12,000 ms (LLM turn) | **>3,000x faster execution** |
| **Invariant Watchdog Violations** | **0 violations (100% compliance)** | Frequent state / rule drift | **Zero physical hallucinations** |
| **Epistemic Spoiler Leakage** | **0% (0 leaked coordinates)** | 20% – 45% prompt leakage | **Strict line-of-sight guarantee** |
| **Action Feasibility Verification** | **0.013 – 0.017 ms** (Sub-20µs SQL `EXCEPT`) | ~1,500 – 3,000 ms LLM evaluation | **>100,000x faster verification** |
| **Topological Mutation (Spell AoE)**| **0.151 ms** (burns doors, updates HP) | Unpredictable / Hallucinated | **Idempotent graph transition** |
| **Terminal Campaign State** | **`VICTORY_BOSS_DEFEATED`** | Indeterminate / Infinite loop | **Terminal milestone verified** |
| **Overall Repository Test Suite** | **64 / 64 passed (100%)** | N/A | **Zero regressions** |

---

## 3. Architecture & Toolchain Reference

### Code Intelligence Core Tools
* **[`tools/map_codebase.py`](file:///home/wes/projects/CapStone/tools/map_codebase.py)**: Static Abstract Syntax Tree (AST) analyzer. Scans repository Python files, assigns canonical URIs (`node://code/<rel_path>:<symbol>`), extracts function signatures/docstrings into compact summaries (< 30 tokens), and emits `call_graph`, `imports`, and `structural` edges into SQLite.
* **[`tools/trace_runtime.py`](file:///home/wes/projects/CapStone/tools/trace_runtime.py)**: Dynamic execution profiler. Hooks `sys.setprofile` during automated `pytest` suites to capture runtime call edges across dynamic dispatch registries and callbacks, recording them under `lens = 'runtime_trace'`.
* **[`tools/blast_radius.py`](file:///home/wes/projects/CapStone/tools/blast_radius.py)**: Reverse recursive CTE impact analyzer. Traverses upstream caller trees with `--multiplex` to simultaneously query static AST and dynamic profiler traces, computing the complete blast radius before code modifications.
* **[`tools/triangulate_fault.py`](file:///home/wes/projects/CapStone/tools/triangulate_fault.py)**: Set-theoretic root cause localizer. Computes the downstream execution cone of failing tests, executes SQL `INTERSECT` across all failing paths, and sorts candidates by topological depth to rank the leaf-most shared culprit at Rank #1.

### Simulation Engine & Core Subsystems
* **[`core/dnd_engine.py`](file:///home/wes/projects/CapStone/core/dnd_engine.py)**: Deterministic TTRPG spatial and state engine. Models rooms, entities, items, and rules as nodes connected via `spatial`, `containment`, `prerequisite`, `perception`, and `faction` lenses. Implements fog-of-war queries, AoE mutations, and prerequisite gating.
* **[`tools/simulate_campaign.py`](file:///home/wes/projects/CapStone/tools/simulate_campaign.py)**: Multi-agent campaign driver. Coordinates a 3-agent party (Fighter, Wizard, Rogue) across an 8-room crypt dungeon, executing actions and verifying four physical invariant watchdogs per tick.
* **[`core/void_engine.py`](file:///home/wes/projects/CapStone/core/void_engine.py)**: Dynamic command dispatch engine powering background operations and terminal command routing.
* **[`core/project_manager.py`](file:///home/wes/projects/CapStone/core/project_manager.py)**: Isolated project workspace manager supporting multi-project substrates.
* **[`core/sim_runner.py`](file:///home/wes/projects/CapStone/core/sim_runner.py)**: Headless simulation kernel executing stepping routines and state logging.
* **[`core/workbench_substrate.py`](file:///home/wes/projects/CapStone/core/workbench_substrate.py)**: Cognitive workbench with transactional SQLite savepoint branching and LRU eviction.

---

## 4. Quickstart CLI Commands

### 1. Static AST Codebase Indexing
Generate the initial relational graph from repository source code:
```bash
python3 tools/map_codebase.py --repo . --db code_substrate.db
```

### 2. Dynamic Runtime Trace Recording
Capture dynamic execution edges using `pytest` and `sys.setprofile`:
```bash
python3 tools/trace_runtime.py --db code_substrate.db --tests tests/test_void.py
```

### 3. Multiplex Upstream Blast Radius Analysis
Query all static and dynamic upstream callers of a target function:
```bash
python3 tools/blast_radius.py "node://code/core/void_engine.py:handle_create_project_cmd" --multiplex --db code_substrate.db
```

### 4. Causal Fault Triangulation
Isolate the root cause of failing tests via downstream CTE intersection:
```bash
python3 tools/triangulate_fault.py \
  "node://code/tests/test_void.py:test_void_engine_create_project" \
  "node://code/tests/test_projects.py:test_project_manager_create" \
  --culprit-only --db code_substrate.db
```

### 5. Autonomous Multi-Agent Campaign Simulation
Run the 25-tick dungeon crawl through the 8-room crypt with invariant watchdogs:
```bash
python3 tools/simulate_campaign.py --ticks 25 --verbose
```

### 6. Full Unit Test Suite Verification
Execute the full 64-test validation suite:
```bash
pytest
```

---

## 5. Documentation & Benchmark Index

* **[`CAPSTONE_FOUNDATION.md`](file:///home/wes/projects/CapStone/CAPSTONE_FOUNDATION.md)**: Formal Academic Capstone Research Specification & Complexity Analysis (WGU C964).
* **[`dynamic_lens_benchmark.md`](file:///home/wes/projects/CapStone/dynamic_lens_benchmark.md)**: Multiplex static/dynamic lens benchmark and dispatch blind spot recovery.
* **[`triangulation_benchmark.md`](file:///home/wes/projects/CapStone/triangulation_benchmark.md)**: Downstream CTE set-intersection for 24-test cascade fault triangulation.
* **[`fanout_benchmark.md`](file:///home/wes/projects/CapStone/fanout_benchmark.md)**: Multi-branch interface refactoring and upstream fan-out blast radius.
* **[`refactor_benchmark.md`](file:///home/wes/projects/CapStone/refactor_benchmark.md)**: Linear 3-hop caller chain refactoring telemetry.
* **[`dnd_substrate_benchmark.md`](file:///home/wes/projects/CapStone/dnd_substrate_benchmark.md)**: Single-tick CTE TTRPG mechanics, fog-of-war latency, and spell AoE mutations.
* **[`campaign_simulation_benchmark.md`](file:///home/wes/projects/CapStone/campaign_simulation_benchmark.md)**: 25-tick multi-agent autonomous campaign benchmark report.

---

## 6. License & Commercial Dual-Licensing

This repository and the underlying relational hypergraph substrate architecture are copyrighted by **Wesley A. Schunk (ZeroSelf, LLC)** and made available under a **Dual-License** model:

1. **Open-Source & Academic License (GNU AGPLv3):**
   This software is free for academic evaluation, research verification, and open-source projects under the **GNU Affero General Public License v3.0 (`AGPL-3.0-only`)**. Under Section 13 of the AGPLv3, any entity that modifies, embeds, or operates this software over a network (including SaaS, cloud APIs, or hosted agent workflows) **must disclose and release the complete source code of their entire derivative system under the AGPLv3**.

2. **Commercial License (Closed-Source / Enterprise):**
   If you wish to integrate this relational substrate, multiplex tracing architecture, or deterministic state engine into a proprietary, closed-source commercial product, internal enterprise toolchain, or hosted SaaS platform without the copyleft disclosure requirements of the AGPLv3, you must obtain a separate **Commercial License** from the copyright holder.

### Contact & Licensing Inquiries
* **Author:** Wesley A. Schunk (ZeroSelf, LLC)
* **Email:** [schunkster88@gmail.com](mailto:schunkster88@gmail.com)

### Academic Citation
If you utilize this relational hypergraph substrate architecture, empirical gauntlet benchmarks, or deterministic world simulation engine in your research, coursework, or systems engineering work, please cite it as:

```bibtex
@software{schunk2026deterministic,
  author       = {Wesley A. Schunk},
  title        = {Deterministic Relational Hypergraphs as a Bounded-Context Substrate for Autonomous Software Maintenance and State Simulation},
  year         = {2026},
  month        = {11},
  publisher    = {GitHub},
  version      = {1.0.0},
  url          = {https://github.com/schunkster88-code/Capstone}
}
```

