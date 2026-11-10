# AGENT.md — Project Overview

## What Is This Project?
`mark2` is a code intelligence and architecture navigation substrate modeling the Mark II application codebase. It represents modules, classes, methods, and API routers as graph nodes while separating syntactic imports, direct invocations, runtime telemetry, and test coverage into orthogonal semantic lenses.

---

## How It Works & Key Components
* **Core Logic:** Python scripts in `scripts/` supporting impact analysis, architectural navigation, and scale testing:
  * `blast_radius.py`: Executes a recursive Common Table Expression (CTE) to calculate the upstream transitive impact of a symbol change across the `call_graph` or other lenses.
  * `lens_navigator.py`: Queries and displays symbol metadata, inbound callers/dependents, and outbound relations filtered by lens (`structural`, `call_graph`, `data_flow`).
  * `codebase_scaler.py`: Synthetic microservice tree generator that seeds hundreds of modules, classes, and methods with realistic multi-lens edges to stress-test large codebases.
* **Data & Storage:** Local SQLite database at `project.db` storing code entity definitions in `substrate_nodes` and multi-lens dependencies in `hyper_edges` with indexed `(source_coordinate, lens)` and `(target_coordinate, lens)` keys.

---

## Operational Rules & Notes
* Code entity coordinates follow the `node://code/<module_path>/<symbol_name>` URI convention.
* Impact analysis queries should restrict traversal using `lens IN ('call_graph', 'test_coverage')` to avoid false-positive cycles through structural imports or telemetry streaming edges.
* Scripts can be executed directly via Python CLI:
  * `python scripts/blast_radius.py [symbol_coordinate] [lens_filter]`
  * `python scripts/lens_navigator.py [coordinate] [lens]`
  * `python scripts/codebase_scaler.py [num_modules] [classes_per_module] [methods_per_class]`
