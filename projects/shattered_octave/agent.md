# AGENT.md — Project Overview

## What Is This Project?
`shattered_octave` is a narrative world-building substrate modeling "The Shattered Octave" story bible. It uses the graph-relational substrate as an epistemic constraint boundary, enforcing character Point-of-View fog-of-war, causal conspiracy route discovery, and reactive invariant propagation for generative storytelling.

---

## How It Works & Key Components
* **Core Logic:** Python scripts in `scripts/` demonstrating narrative constraints and multi-hop discovery:
  * `fow_query.py`: Retrieves a character's bounded epistemic, spatial, and dramatic horizon, masking unobserved world facts (e.g., masking Morwen's living rebel state into Kaelen's subjective belief that she died ten years ago).
  * `conspiracy_route.py`: Executes a recursive CTE across `dramatic` and `spatial` lenses to find indirect causal transmission vectors between characters (e.g., discovering Corvo as the intermediary between Morwen and Vaelen).
* **Data & Storage:** Local SQLite database at `project.db` storing narrative entities (characters, locations, artifacts) in `substrate_nodes` and relationships in `hyper_edges` across three orthogonal planes: `spatial`, `epistemic`, and `dramatic`.

---

## Operational Rules & Notes
* Character generation prompts must strictly query the character's outbound horizon via `fow_query.py` logic to prevent context leakage and character omniscience.
* Scripts can be executed directly via Python CLI:
  * `python scripts/fow_query.py [character_coord]` (defaults to `node://character/kaelen`)
  * `python scripts/conspiracy_route.py [source_coord] [target_coord]` (defaults to `node://character/morwen` $\to$ `node://character/vaelen`)
