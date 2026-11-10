# AGENT.md — Project Overview

## What Is This Project?
`hyper_web_sim_` is a live integration testbed linking graph-relational hypergraph traversals to the 2D visualizer runner. It maps logical graph navigation across task coordinates directly to spatial grid entity movements and step events.

---

## How It Works & Key Components
* **Core Logic:** Python scripts in `scripts/` that translate graph relations into simulation state transitions:
  * `dynamic_walker.py`: Spawns a `traverser_1` entity, steps along a hardcoded dependency adjacency path (`node://task/101` $\to$ `node://task/102` $\to$ `node://task/103`), advances the entity across the 2D grid, and emits structured `traverse_hop` events.
  * `hyper_step.py`: Generic stepping routine that advances entity state and emits `traverse_edge` telemetry events.
* **Data & Storage:** Local SQLite database at `project.db` containing `substrate_nodes`, `hyper_edges`, and `traversal_telemetry` tables alongside the standard simulation telemetry and script views.

---

## Operational Rules & Notes
* Traversal routines implement the `step(state, params, emit_step)` signature and expect grid coordinate limits (`width`, `height`) in the simulation state.
* Events emitted by the scripts include semantic lens labels (`lens: "dependency"`) and numerical edge weights to support visualizer rendering.
