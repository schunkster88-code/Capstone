# AGENT.md — Project Overview

## What Is This Project?
The `default` project is the base simulation and spatial memory workspace for the system. It serves as a testing environment for 2D grid-based multi-agent ecosystems, active inference foraging, predator-prey dynamics, and physical wave propagation models.

---

## How It Works & Key Components
* **Core Logic:** A collection of Python simulation scripts in `scripts/` driven by the simulation runner:
  * `baseline_forage.py`: Active exploratory foraging routine using random-walk steps across grid boundaries.
  * `epistemic_chase.py`: Active inference loop where a forager minimizes expected free energy while navigating around a hunting stalker.
  * `evasive_tension_chase.py` & `multi_agent_chase.py`: Multi-entity ecosystems with stamina consumption, adrenaline dashes, resource harvesting, and raycast occlusion.
  * `harmonic_sandbox.py` & `wave_reservoir.py`: Discretized 2D scalar wave equations modeling wave velocity, acoustic damping, and reflective boundaries.
  * `patrol_and_recover.py`: State-based behavioral routines for scavenger rebooting, drone perimeter sweeps, and agent stamina regeneration.
* **Data & Storage:** Local SQLite database at `project.db` operated in WAL mode. Contains `sim_telemetry` and `sim_scripts` tables, alongside database views (`v_sim_telemetry`, `v_sim_entities`, `v_sim_cells`, `v_sim_scripts`) consumed by the web viewer.

---

## Operational Rules & Notes
* Scripts are executed either via the `step(state, params, emit_step)` interface or as inline execution loops iterating over `steps_to_run`.
* Execution routines avoid complex scoping constructs (such as nested list comprehensions inside sandboxed execution) to prevent variable leakage.
* Script IDs and default parameters are declared in YAML-style docstring headers at the top of each Python file in `scripts/`.
