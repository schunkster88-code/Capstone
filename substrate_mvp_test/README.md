# Substrate MVP Test Suite & A/B Benchmark

> **WGU B.S. Computer Science Capstone (C964) MVP Prototype**  
> **Author:** Wesley A. Schunk (ZeroSelf, LLC)  
> **Contact:** [schunkster88@gmail.com](mailto:schunkster88@gmail.com)  
> **License:** GNU AGPLv3 (`AGPL-3.0-only`) / Commercial Dual-License  

---

## 1. Overview
This directory contains a self-contained, standalone MVP prototype of the **Relational Hypergraph Substrate**. It demonstrates:
1. **Sample 5-File Fixture:** Interconnected Python modules with real multi-hop execution flow (`main.py` -> `core/router.py` -> `core/engine.py` -> `storage/db.py`) along with decoy comments and strings to stress-test naive grep scanning.
2. **SQLite WAL Database:** Two-table normalized relational schema (`substrate_nodes`, `hyper_edges`) configured with Write-Ahead Logging (WAL) and compound forward/reverse B-tree indexes.
3. **AST Parser:** Native `ast.NodeVisitor` engine indexing source code functions into canonical URIs (`node://code/...`) and constructing `call_graph` multiplex edges.
4. **Recursive CTE Upstream Tracer:** Dynamic SQL Common Table Expression (CTE) discovering multi-hop callers up to 3 hops away in sub-millisecond query time.
5. **Automated A/B Benchmark:** Rigorous comparison between the Recursive CTE Substrate and a recursive text-scanning grep baseline across execution latency, token payload size, and false positives.

---

## 2. Directory Structure

```
substrate_mvp_test/
├── fixture/                     # 5-file interconnected sample project
│   ├── main.py                  # Entrypoint (CLI dispatch) -> Hop 3
│   ├── core/
│   │   ├── router.py            # Route handler -> Hop 2
│   │   ├── engine.py            # Workflow processor -> Hop 1
│   │   └── validator.py         # Schema validation & audit -> Hop 1
│   └── storage/
│       └── db.py                # Target leaf persistence layer
├── schema.sql                   # SQLite WAL DDL and B-tree compound indexes
├── init_db.py                   # Database initializer script
├── parser.py                    # AST visitor & graph ingestion script
├── tracer.py                    # Recursive CTE 3-hop upstream tracer
├── benchmark.py                 # Automated A/B benchmark runner (100 trials)
├── benchmark_report.md          # Generated empirical benchmark markdown report
├── test_mvp.py                  # Pytest validation test harness (5 tests)
└── README.md                    # Systems engineering overview
```

---

## 3. Quickstart CLI Commands

### Run the Sample Fixture Directly
```bash
python3 fixture/main.py
```

### Initialize the Substrate Database
```bash
python3 init_db.py
```

### Ingest the Codebase via AST Parser
```bash
python3 parser.py
```

### Execute 3-Hop Upstream Dependency Trace
```bash
python3 tracer.py
```

### Run Automated A/B Benchmark (100 Trials)
```bash
python3 benchmark.py
```

### Run the Full Pytest Suite
```bash
pytest test_mvp.py -v
```

---

## 4. Empirical Benchmark Telemetry

| Evaluation Metric | Condition A: Naive File Scan / Grep Baseline | Condition B: Relational Substrate (CTE) | Delta / Realized Gain |
| :--- | :--- | :--- | :--- |
| **Execution Latency (Mean)** | **0.444 ms** (Iterative regex file I/O) | **0.252 ms** (B-tree indexed CTE) | **1.8x Faster** |
| **Planning Context Overhead** | **1,301 tokens** (Full matched files) | **131 tokens** (OpenGraph signposts) | **89.9% Token Reduction** |
| **Surgical Body Ingestion** | **1,301 tokens** (Entire module contexts) | **415 tokens** (Targeted AST slices) | **68.1% Token Reduction** |
| **False Positive Noise** | **19 false matches** (comments, strings, defs) | **0 false positives** (AST call graph) | **100% Precision / Zero Noise** |
| **Upstream Lineage Recall** | Fragile regex / heuristic hopping | Complete multi-hop directed path | **100% Causal Recall (4/4 Callers)** |
