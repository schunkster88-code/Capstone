# Empirical Benchmark Results: Codebase Indexing & Traversal Substrate
**Zero-LLM Codebase Indexing & Graph-Relational Traversal Evaluation**

*Target Environment: Linux x86_64 | SQLite 3.45+ WAL | Python 3.14*  
*Evaluated Path (3 hops deep):*  
`api/routes/projects.py:handle_create_project -> core/project_manager.py:create_project -> core/project_manager.py:sync_db_scripts_to_disk -> core/project_manager.py:export_script_to_disk`

---

## 1. Summary Comparison Table

| Metric | Grep / Text Search | Relational Substrate | Delta / Improvement |
| :--- | :--- | :--- | :--- |
| **Search / Traversal Latency** | 9.669 ms | 0.131 ms | 73.8x faster |
| **Payload Size (Tokens)** | 9479.8 tokens | 199.0 tokens | -97.9% reduction |
| **False Positive Noise** | 4 files (36 raw matches) | 0 (exact path) | 100% precision |
| **Total Indexing Time** | N/A | 53.69 ms | One-time cost |

---

## 2. Execution Path & OpenGraph Node Previews

The relational substrate retrieved only the minimal, high-signal node summary cards along the exact causal path without ingesting any unrelated code files:

1. **`node://code/api/routes/projects.py:handle_create_project`** (`function`)
   > def handle_create_project(req: ProjectCreateRequest) -> Dict[str, Any]: Create a new self-contained project folder with isolated database and scripts.

2. **`node://code/core/project_manager.py:create_project`** (`function`)
   > def create_project(name: str, description: str='', template: str='sim', compress: bool=False) -> Dict[str, Any]: Create a new self-contained project folder with its own SQLite database and scripts directory.

3. **`node://code/core/project_manager.py:sync_db_scripts_to_disk`** (`function`)
   > def sync_db_scripts_to_disk(db_path: Optional[Path]=None, compress: bool=False) -> int: Export all scripts from the database to individual .py files in the project's scripts folder.

4. **`node://code/core/project_manager.py:export_script_to_disk`** (`function`)
   > def export_script_to_disk(script_id: str, name: str, description: str, script_body: str, default_params: Optional[Dict[str, Any]]=None, db_path: Optional[Path]=None, compress: bool=False) -> Path: Export a simulation script to an isolated .py file bundled...

---

## 3. Key Empirical Findings

1. **Token Efficiency:** The relational substrate consumed only **199.0 tokens** compared to **9479.8 tokens** for grep context windows—an empirical **97.9% reduction**.
2. **Speed:** SQLite indexed recursive CTE query resolved the multi-hop call chain in **0.131 ms**, achieving a **73.81x speedup** over disk-based text searches.
3. **Precision:** Grep returned 6 files with 4 false-positive files (core/sim_runner.py, core/void_engine.py, tests/test_benchmark_traversal.py, tests/test_refactor_blast_radius.py), whereas the substrate isolated the exact execution chain with **100% precision**.
4. **One-Time Cost:** Building the relational substrate (`code_substrate.db`) across all project files required a one-time indexing cost of **53.69 ms**.
