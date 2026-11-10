# Branching Fan-Out (Wide Blast Radius) Refactoring Benchmark Report
**Multi-Branch Concurrent Interface Refactoring via Relational Substrate**

*Date: November 10, 2026*  
*Environment: Linux x86_64 | SQLite 3.45+ WAL | Python 3.14*  
*Substrate Database: [`code_substrate.db`](file:///home/wes/projects/CapStone/code_substrate.db)*  
*Refactoring Tool: [`tools/blast_radius.py`](file:///home/wes/projects/CapStone/tools/blast_radius.py)*  
*Validation Harness: [`tests/test_fanout_benchmark.py`](file:///home/wes/projects/CapStone/tests/test_fanout_benchmark.py)*

---

## 1. Executive Summary & Comparative Matrix

This benchmark tests an agent's ability to locate a high fan-in utility called across multiple diverging files, calculate its upstream blast radius via reverse recursive CTEs, and patch all branching callers concurrently while ingesting strictly targeted function nodes and preserving zero test regressions.

### Comparative Benchmark Table

| Metric | Result | Baseline (Full-File Ingestion) | Delta / Status |
| :--- | :--- | :--- | :--- |
| **Target Function** | `node://code/core/project_manager.py:list_projects` | N/A | High Fan-In Target |
| **Branching Callers Identified** | 5 callers across 3 files | Variable / Unindexed | 100% Causal Recall |
| **Unrelated Code Ingested** | 0 files / lines | Full file contexts | Zero Context Drift |
| **Total Context Consumed (Tokens)** | **942.5 tokens** (142.5 summary + 800 body) | ~7,064 tokens | **86.66% reduction** |
| **Pytest Exit Code & Pass Rate** | **49 passed, 0 failed** (Exit Code 0) | N/A | 100% Regression-Free |

---

## 2. High Fan-In Candidate Discovery

Querying `code_substrate.db` identified candidate functions with high in-degree connectivity:

```sql
SELECT target, COUNT(DISTINCT source) as caller_count
FROM hyper_edges 
WHERE lens = 'call_graph'
GROUP BY target 
HAVING caller_count >= 2
ORDER BY caller_count DESC;
```

**Selected Target:** `node://code/core/project_manager.py:list_projects`
* **Fan-In Degree:** 5 direct/transitive callers.
* **Divergence:** Fans out across 3 distinct files (`api/routes/projects.py`, `core/void_engine.py`, `server.py`).

---

## 3. Reverse Recursive CTE Blast Radius Traversal

Executing `tools/blast_radius.py "node://code/core/project_manager.py:list_projects"` resolved all upstream branches across the call graph:

```text
Target: node://code/core/project_manager.py:list_projects (function)
Discovered 5 upstream dependent callers across call_graph lens:
├── [Depth 1] node://code/api/routes/projects.py:handle_list_projects (function)
├── [Depth 1] node://code/api/routes/projects.py:handle_get_active_project (function)
├── [Depth 1] node://code/api/routes/projects.py:handle_get_project (function)
├── [Depth 1] node://code/core/void_engine.py:execute_raw (function)
└── [Depth 2] node://code/server.py:run_command (function)
```

---

## 4. Surgical Fan-Out Patching

1. **Target Utility Mutation (`core/project_manager.py:list_projects`):**
   - Added `include_metadata: bool = True`.
   - When set to `False`, skips reading and parsing `project.json` files on disk, setting `"include_metadata": False` on returned dictionaries for fast directory scanning.
2. **Branch A (`api/routes/projects.py:handle_list_projects`):**
   - Added query parameter `include_metadata: bool = True`.
   - Propagates `list_projects(include_metadata=include_metadata)`.
3. **Branch B (`api/routes/projects.py:handle_get_active_project`):**
   - Added query parameter `include_metadata: bool = True`.
   - Propagates `list_projects(include_metadata=include_metadata)`.
4. **Branch C (`api/routes/projects.py:handle_get_project`):**
   - Added query parameter `include_metadata: bool = True`.
   - Propagates `list_projects(include_metadata=include_metadata)`.
5. **Branch D (`core/void_engine.py:execute_raw`):**
   - Updated the `LIST PROJECTS` console command interceptor to pass `list_projects(include_metadata=True)`.

---

## 5. Token Efficiency & Context Economy

* **Baseline Full-File Ingestion:** Ingesting `core/project_manager.py`, `api/routes/projects.py`, `core/void_engine.py`, and `server.py` requires **~7,064 tokens** ($28,256\text{ characters}$).
* **Surgical Substrate Ingestion:** Ingesting only OpenGraph summaries and targeted caller functions consumed **942.5 tokens** ($3,770\text{ characters}$) — an **86.66% token reduction** with **0 unrelated files or lines ingested**.

---

## 6. Graph Re-Mapping & Regression Verification

* **Substrate Synchronization:** Re-ran `python tools/map_codebase.py core api server.py`. All 4 branch signatures in `substrate_nodes` updated cleanly in $74.82\text{ ms}$.
* **Test Suite Verification:** Ran `.venv/bin/pytest -v`.
  - **49 passed in 0.69s** (Exit Code 0).
  - Dedicated branching tests in [`tests/test_fanout_benchmark.py`](file:///home/wes/projects/CapStone/tests/test_fanout_benchmark.py) verified `include_metadata` toggling across all three API endpoints and the console engine.
