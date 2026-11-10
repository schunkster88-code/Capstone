# AGENT.md — Project Overview

## What Is This Project?
`eco_colony` is a dedicated simulation project designed to model an ant colony ecosystem. It provides the scaffold for simulating pheromone gradient deposition, trail evaporation, and periodic worker ant generation.

---

## How It Works & Key Components
* **Core Logic:** Python simulation handlers located in `scripts/`:
  * `ant_trail.py`: Defines the `ant_trail` routine with a default pheromone decay parameter (`decay: 0.05`) for ant movement and gradient following.
  * `queen_logic.py`: Defines the `queen_logic` routine with a configurable spawn interval (`spawn_interval: 10`) to generate new worker entities into the simulation state.
* **Data & Storage:** Local SQLite database at `project.db` initialized with simulation tables (`sim_telemetry`, `sim_scripts`) and telemetry views (`v_sim_telemetry`, `v_sim_entities`, `v_sim_cells`, `v_sim_scripts`). Project metadata is defined in `project.json`.

---

## Operational Rules & Notes
* Handlers adhere to the standard `step(state, params, emit_step)` signature expected by the simulation engine runner.
* The script routines are registered in the `sim_scripts` table and synchronized to local `.py` files using the project synchronization utilities.
