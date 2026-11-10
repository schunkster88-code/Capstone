# Preliminary Capstone Architecture & Research Specification
**Working Title:** *Deterministic Relational Hypergraphs as a Bounded-Context Substrate for Autonomous Software Maintenance and State Simulation*  
**Author:** Wesley A. Schunk  
**Target Academic Milestone:** WGU B.S. Computer Science Capstone (C964) / Data Structures & Algorithms (C949/C950) Applied Research  
**Repository:** `/home/wes/projects/CapStone`  
**Contact:** Wesley A. Schunk (schunkster88@gmail.com) | ZeroSelf, LLC  
**License:** Dual-Licensed under GNU AGPLv3 / Commercial License  
**Provenance & Methodology Note:** *Phase 1 of this project was architected and empirically benchmarked through human-directed AI systems prototyping. Phase 2 focuses on formalizing the relational algebra, decomposing the Python/SQLite implementation line-by-line, and expanding the ingestion engine to demonstrate complete individual mastery of the underlying computer science primitives.*

---

## 1. Executive Problem Statement

Modern Large Language Model (LLM) coding agents and autonomous state engines suffer from a shared structural bottleneck: **unbounded context saturation**. Because standard toolchains treat source code and world states as flat natural language text, they rely on brute-force linear file scanning (`grep`) or fuzzy semantic vector embeddings (RAG) to locate dependencies.

In production software engineering, this paradigm fails across three specific fault lines:
1. **The "Forgotten Caller" in Multi-File Refactoring:** Modifying a low-level function signature requires updating every upstream caller across disparate subsystems. Dumping full files into an LLM context window consumes tens of thousands of tokens, triggers attention degradation, and frequently leaves obscure CLI or worker call-sites broken.
2. **Static Analysis Blind Spots in Dynamic Languages:** Pure Abstract Syntax Tree (AST) parsers snap at dynamic runtime boundaries—such as dictionary-based command dispatch, decorator registries, or C-extension callbacks—reporting zero upstream callers and inducing a false sense of safety during refactoring.
3. **Symptom-Chasing During Test Cascade Failures:** When a defect in a foundational utility causes dozens of tests to fail across multiple test files, naive agents ingest all failing stack traces and test suites simultaneously. Overwhelmed by context noise, agents routinely modify test assertions or patch surface-level callers rather than isolating the single shared root cause.

**Core Thesis:** Source code dependency resolution, fault localization, and deterministic world simulation are **directed multigraph traversal problems**, not natural language comprehension problems. By offloading structural navigation and state verification to a two-table relational database (`substrate_nodes`, `hyper_edges`) running in SQLite Write-Ahead Logging (WAL) mode, we execute multi-hop dependency resolution and set-theoretic bug triangulation in **sub-millisecond to single-digit-millisecond latencies** while reducing LLM token ingestion by **86% to 99.8%**.

---

## 2. Mathematical & Data-Oriented Model

Rather than maintaining heavyweight external graph databases (e.g., Neo4j) or in-memory pointer graphs that require constant serialization, the system models the workspace as a labeled directed multigraph:

$$G = (V, E, L)$$

Where:
* $V$ is the set of canonical vertex coordinates stored in `substrate_nodes`.
* $E \subseteq V \times V \times L$ is the set of directed edges stored in `hyper_edges`.
* $L$ is the discrete set of **Multiplex Lenses** (`call_graph`, `runtime_trace`, `spatial`, `containment`, `prerequisite`, `perception`, `faction`), allowing orthogonal relationship layers to coexist within a single relational schema.

### Relational Schema Definition

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE substrate_nodes (
    coordinate TEXT PRIMARY KEY, -- Canonical URI: node://code/module.py:symbol
    node_type  TEXT NOT NULL,    -- function, method, class, room, entity, item, rule
    summary    TEXT NOT NULL,    -- Compact OpenGraph signpost (< 30 tokens)
    body       TEXT NOT NULL     -- Raw source slice or JSON state payload
);

CREATE TABLE hyper_edges (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    lens   TEXT NOT NULL,        -- Multiplex discriminator
    PRIMARY KEY (source, target, lens),
    FOREIGN KEY (source) REFERENCES substrate_nodes(coordinate),
    FOREIGN KEY (target) REFERENCES substrate_nodes(coordinate)
);

CREATE INDEX idx_edges_forward ON hyper_edges(source, lens);
CREATE INDEX idx_edges_reverse ON hyper_edges(target, lens);
```

### Computational Complexity Advantage

| Operation | Naive File Scan + LLM Ingestion | Relational B-Tree CTE Traversal |
| --- | --- | --- |
| **Search / Traversal Time** | $O(N)$ linear scan across all repository lines | $O(b^d \log |E|)$ via compound B-tree indices |
| **Transformer Attention Cost** | $O(T^2)$ quadratic self-attention over full files ($T > 10^4$ tokens) | $O(T_{\text{sub}}^2)$ over isolated target nodes ($T_{\text{sub}} < 10^3$ tokens) |
| **Root-Cause Isolation** | Heuristic trial-and-error across $K$ stack traces | Deterministic set intersection: $\bigcap_{i=1}^{K} \text{Callees}(T_i)$ |

---

## 3. Core Algorithmic Mechanisms

### 3.1 Static AST Indexing (`tools/map_codebase.py`)

Walks the repository using Python’s native `ast.NodeVisitor`. Every module, class, function, and method is assigned an immutable canonical URI (`node://code/<rel_path>:<symbol>`) rather than brittle line-number offsets. Call expressions within function bodies are resolved against local import tables and emitted as `lens = 'call_graph'` edges.

### 3.2 Dynamic Runtime Trace Reconciliation (`tools/trace_runtime.py`)

To resolve dynamic dispatch blind spots without altering the two-table schema, `trace_runtime.py` hooks `sys.setprofile` and `threading.setprofile` during automated `pytest` execution. Whenever a call event crosses module/function boundaries within the target repository, the profiler resolves the caller and callee stack frames (`f_back`, `f_code`) to their canonical `node://code/...` coordinates and inserts the edge under `lens = 'runtime_trace'`.

### 3.3 Multiplex Upstream Blast Radius (`tools/blast_radius.py`)

Before modifying a function signature, the agent queries the reverse transitive closure across both static and dynamic lenses simultaneously:

```sql
WITH RECURSIVE upstream(source, target, lens, depth, path) AS (
    SELECT source, target, lens, 1, source || ' -[' || lens || ']-> ' || target
    FROM hyper_edges
    WHERE target = :target_coord
      AND lens IN ('call_graph', 'runtime_trace')
    UNION ALL
    SELECT e.source, e.target, e.lens, u.depth + 1,
           e.source || ' -[' || e.lens || ']-> ' || u.path
    FROM hyper_edges e
    JOIN upstream u ON e.target = u.source
    WHERE u.depth < :max_depth
      AND e.lens IN ('call_graph', 'runtime_trace')
)
SELECT DISTINCT source, depth, path FROM upstream ORDER BY depth ASC;
```

### 3.4 Causal Fault Triangulation (`tools/triangulate_fault.py`)

When a defect triggers failures across $n$ distinct test functions $\{T_1, T_2, \dots, T_n\}$, the root cause resides within the intersection of their downstream execution cones:

$$\text{Suspects} = \bigcap_{i=1}^{n} \left\{ v \in V \;\middle|\; T_i \xrightarrow{\text{call\_graph} \cup \text{runtime\_trace}}^{*} v \right\}$$

By executing a forward recursive CTE for each failing test coordinate, computing their SQL `INTERSECT`, and ordering candidates by topological depth (`max_depth DESC, min_depth DESC`), the query pins the leaf-most shared dependency at **Rank #1**.

---

## 4. Empirical Benchmark Telemetry (The 5-Stage Gauntlet)

| Benchmark Stage | Engineering Challenge | Baseline (Grep / Raw LLM Context) | Relational Substrate Result | Realized Gain |
| --- | --- | --- | --- | --- |
| **1. Structural Navigation** | Trace a 3-hop execution path from API route to disk utility | **8.86 ms** grep scan; **6,478 tokens** (21 false positives) | **0.171 ms** CTE query (**92.4 ms** full repo index); **184.2 tokens** | **51.8x faster**; **97.2% token reduction** |
| **2. Linear Blast Radius** | Propagate new parameter across 3-hop caller chain | **~6,000+ tokens** (full module ingestion) | **1,086 total tokens** (188 planning + 898 execution); 0 extra files read | **~82% token reduction**; 45/45 tests passed |
| **3. Divergent Fan-Out** | Refactor `list_projects` across REST API and CLI subsystems | **7,064 tokens**; high risk of missing CLI handler | Caught all **5 callers across 3 files**; **942.5 tokens**; **74.8 ms** re-index | **86.7% token reduction**; 49/49 tests passed |
| **4. Dynamic Multiplex Lens** | Resolve callers of dynamically dispatched command handlers | **0 callers detected** via static AST (100% blind spot) | **32 invisible runtime edges** captured; full 3-hop lineage restored | Eliminated dynamic dispatch blind spot; 53/53 tests passed |
| **5. Fault Triangulation** | Isolate root cause of **24 failing tests across 7 test files** | **~14,500+ tokens** (7 test files + 4 modules); 15–60s LLM read | **7.251 ms** `INTERSECT` query; pinned Rank #1 culprit using **26.8 tokens** | **>2,000x faster**; **99.81% token reduction**; 56/56 tests passed |

---

## 5. Topological Isomorphism: Deterministic World & State Simulation

To verify domain generalizability, the identical two-table schema was instantiated as a deterministic Tabletop RPG simulation engine (`core/dnd_engine.py`, `tools/simulate_campaign.py`) across an 8-room dungeon topology using five domain lenses (`spatial`, `containment`, `prerequisite`, `perception`, `faction`):

* **Epistemic Information Barrier (Fog-of-War):** `get_visible_state()` resolved visible nodes in **0.039 ms** (203 tokens/turn), guaranteeing **0% spoiler leakage**.
* **Topological Mutation:** `resolve_aoe_spell()` resolved saving throws, deducted HP, and incinerated flammable wooden door edges in **0.151 ms**.
* **Sub-20µs Prerequisite Gates:** `verify_action_feasibility()` enforced a dual-key lock (`bone_key` + `iron_key`) via SQL `EXCEPT` in **0.013–0.017 ms**.
* **Multi-Agent Campaign Simulation:** A 3-agent autonomous party completed a **25-tick campaign** to `VICTORY_BOSS_DEFEATED` at **1.472 ms/tick** with **0 invariant watchdog violations** across all 64 repository unit tests.

---

## 6. Personal Mastery & Capstone Hardening Roadmap

1. **White-Box Code Audit & Manual Reconstruction:** Annotate every AST visitor method, stack frame pointer inspection (`f_back`, `f_code`), and SQLite query plan (`EXPLAIN QUERY PLAN`).
2. **Formal Tie-In with WGU Coursework (C949 / C950 / C960):** Document B-tree adjacency indexing, cycle-safe recursive CTE traversal, and discrete set algebra (`INTERSECT` / `EXCEPT`).
3. **External Repository Stress Testing:** Benchmark against unmodified open-source repositories (`httpx`, `click`, `fastapi`).
4. **Edge-Case Hardening:** Enforce cycle-prevention guards (`INSTR(path, e.source) = 0`) and implement a `symbol_heuristic` fallback lens.
