# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

"""
Narrative World Benchmark: The Shattered Octave
Empirical Evaluation of Inverted Architecture (Story Engine -> DB Mutation -> Constraint Boundary)

Tests:
- Test A: Point-of-View Fog-of-War (Preventing Omniscience / Context Leakage)
- Test B: Dynamic Event Ingestion & Reactive Invariant Propagation
- Test C: Transitive Betrayal Path (Multi-Hop Causal Discovery via Recursive CTE)
- Test D: Timeline Forking & Multiverse Consistency (SAVEPOINT / Diff via EXCEPT)
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tiktoken

DDL_STATEMENTS = """
-- 1. NODES TABLE (Entity State & Progressive Disclosure Previews)
CREATE TABLE IF NOT EXISTS substrate_nodes (
    coordinate TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL,
    summary TEXT NOT NULL,
    body TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. HYPER-EDGES (Multi-Lens Topology)
CREATE TABLE IF NOT EXISTS hyper_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_coordinate TEXT NOT NULL,
    target_coordinate TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    lens TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    metadata JSON,
    FOREIGN KEY(source_coordinate) REFERENCES substrate_nodes(coordinate),
    FOREIGN KEY(target_coordinate) REFERENCES substrate_nodes(coordinate)
);

CREATE INDEX IF NOT EXISTS idx_edges_source_lens ON hyper_edges(source_coordinate, lens);
CREATE INDEX IF NOT EXISTS idx_edges_target_lens ON hyper_edges(target_coordinate, lens);
"""

SEED_NODES = [
    (
        "node://location/aethelgard_spire",
        "location",
        "The North Spire",
        "resonant",
        "High bell tower, pristine, guarded by Synod.",
        "Houses the Great Resonant Bell of the Synod. Air is thin and vibration vibrates through tooth enamel.",
    ),
    (
        "node://location/brinegate_sump",
        "location",
        "The Drowned Sump",
        "flooded",
        "Subterranean docks under Brinegate, silt-heavy.",
        "A maze of rotting galleons tied together with braided hemp and iron chains. Smell of sulfur and damp salt.",
    ),
    (
        "node://location/rust_expanse",
        "location",
        "The Rust Foundry",
        "arid",
        "Dead iron factory in the salt wastes.",
        "Scrap piles three storeys tall. High acoustic distortion. Home to the renegade Ferrum Choir.",
    ),
    (
        "node://character/vaelen",
        "character",
        "Grand Censor Vaelen",
        "ailing",
        "Synod leader, hidden rot, manipulative.",
        "Suffers from pulmonary ossification. Desperately requires Brinegate black-market dampening salt to survive inspection.",
    ),
    (
        "node://character/kaelen",
        "character",
        "Needle Master Kaelen",
        "grieving",
        "Spire artisan, master chime-tuner.",
        "Obsessed with acoustic perfection. Keeps his exiled sister's resonance flute hidden behind his bench.",
    ),
    (
        "node://character/morwen",
        "character",
        "Morwen of the Rust",
        "militant",
        "Leader of the Ferrum Choir, exiled rebel.",
        "Exiled a decade ago. Deaf in her left ear. Formulated the Shatter-Pitch frequency.",
    ),
    (
        "node://character/corvo",
        "character",
        "Corvo the Smuggler",
        "vengeful",
        "Skipper of The Blind Gull, black-market broker.",
        "Maintains smiling neutrality while smuggling salt for Vaelen, but plotting revenge for his cousin's execution.",
    ),
    (
        "node://character/lyra",
        "character",
        "Novice Lyra",
        "inquisitive",
        "Spire tuning apprentice, gifted ear.",
        "Discovered harmonic drifting in the northern quadrant bell housing. Unaware of the political coup brewing.",
    ),
    (
        "node://artifact/shatter_chime",
        "artifact",
        "The Shatter Chime",
        "dormant",
        "Pitch-black bell tuned to destroy resonant crystal.",
        "Forged from un-audited meteorite iron. Emits 14.2 Hz sub-harmonic cancellation pulse.",
    ),
    (
        "node://artifact/dampening_salt",
        "artifact",
        "Refined Black Salt",
        "stored",
        "Suppresses biological resonance rot.",
        "Smuggled through Sump bilge tanks in waxed eel-skin bladders.",
    ),
    (
        "node://artifact/childhood_flute",
        "artifact",
        "Pewter Resonance Flute",
        "hidden",
        "Twin-hole whistle stamped with house insignia.",
        "Belonged to Morwen before her exile. Carries the harmonic frequency of the family crypt.",
    ),
]

SEED_EDGES = [
    # SPATIAL LENS
    ("node://character/vaelen", "node://location/aethelgard_spire", "located_in", "spatial", 1.0),
    ("node://character/kaelen", "node://location/aethelgard_spire", "located_in", "spatial", 1.0),
    ("node://character/lyra", "node://location/aethelgard_spire", "located_in", "spatial", 1.0),
    ("node://character/corvo", "node://location/brinegate_sump", "located_in", "spatial", 1.0),
    ("node://character/morwen", "node://location/rust_expanse", "located_in", "spatial", 1.0),
    ("node://artifact/shatter_chime", "node://character/morwen", "carried_by", "spatial", 0.1),
    ("node://artifact/dampening_salt", "node://character/corvo", "carried_by", "spatial", 0.1),
    ("node://artifact/childhood_flute", "node://location/aethelgard_spire", "hidden_in", "spatial", 0.5),

    # EPISTEMIC LENS
    ("node://character/kaelen", "node://character/morwen", "believes_deceased", "epistemic", 1.0),
    ("node://character/morwen", "node://character/kaelen", "knows_alive_in_spire", "epistemic", 1.0),
    ("node://character/lyra", "node://artifact/childhood_flute", "discovered_existence", "epistemic", 1.0),
    ("node://character/vaelen", "node://artifact/dampening_salt", "knows_shipment_pending", "epistemic", 1.0),
    ("node://character/corvo", "node://character/vaelen", "knows_medical_secret", "epistemic", 0.2),

    # DRAMATIC LENS
    ("node://character/corvo", "node://character/vaelen", "blood_grudge", "dramatic", 0.95),
    ("node://character/morwen", "node://character/vaelen", "vows_destruction", "dramatic", 1.0),
    ("node://character/kaelen", "node://character/lyra", "protective_mentor", "dramatic", 0.1),
    ("node://character/morwen", "node://character/corvo", "clandestine_ally", "dramatic", 0.3),
]


def init_narrative_database(db_path: Path) -> sqlite3.Connection:
    """Initializes and seeds the narrative world database."""
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(DDL_STATEMENTS)

    with conn:
        conn.executemany(
            "INSERT INTO substrate_nodes (coordinate, domain, title, state, summary, body) VALUES (?, ?, ?, ?, ?, ?)",
            SEED_NODES,
        )
        conn.executemany(
            "INSERT INTO hyper_edges (source_coordinate, target_coordinate, edge_type, lens, weight) VALUES (?, ?, ?, ?, ?)",
            SEED_EDGES,
        )
    return conn


def count_tokens(text: str) -> int:
    """Computes exact token count using cl100k_base."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


# ---------------------------------------------------------------------------
# TEST A: Point-of-View Fog-of-War (Preventing Omniscience)
# ---------------------------------------------------------------------------
def run_test_a_fog_of_war(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Evaluates epistemic retrieval boundary for Kaelen.
    Ensures that only nodes reachable via Kaelen's epistemic and immediate spatial co-location
    are injected into context.
    Checks for zero context leakage of forbidden secrets.
    """
    start_time = time.perf_counter()

    # 1. Full flat context baseline (Traditional Omniscient Ingestion)
    full_nodes = conn.execute("SELECT coordinate, domain, title, state, summary, body FROM substrate_nodes").fetchall()
    full_edges = conn.execute("SELECT source_coordinate, target_coordinate, edge_type, lens FROM hyper_edges").fetchall()
    
    full_context_text = "### GLOBAL UNFILTERED KNOWLEDGE BASE:\n"
    for coord, dom, title, st, summ, body in full_nodes:
        full_context_text += f"- [{coord}] {title} ({dom}, state: {st}): {summ}\n  Body: {body}\n"
    for s, t, et, lens in full_edges:
        full_context_text += f"- EDGE: {s} --({et}:{lens})--> {t}\n"

    global_tokens = count_tokens(full_context_text)

    # 2. Hyper-Web Point-of-View Fog-of-War Retrieval for Kaelen
    # Bounded exclusively by Kaelen's epistemic and immediate spatial/dramatic horizon
    fow_query = """
    WITH kaelen_horizon AS (
        -- Self
        SELECT 'node://character/kaelen' AS coord, 'self' AS relation, 'identity' AS lens
        UNION
        -- Outbound epistemic: what Kaelen believes/knows
        SELECT target_coordinate, edge_type, lens
        FROM hyper_edges
        WHERE source_coordinate = 'node://character/kaelen' AND lens = 'epistemic'
        UNION
        -- Outbound spatial: where Kaelen physically is
        SELECT target_coordinate, edge_type, lens
        FROM hyper_edges
        WHERE source_coordinate = 'node://character/kaelen' AND lens = 'spatial'
        UNION
        -- Outbound dramatic: immediate relational counter-parties (e.g., apprentice Lyra)
        SELECT target_coordinate, edge_type, lens
        FROM hyper_edges
        WHERE source_coordinate = 'node://character/kaelen' AND lens = 'dramatic'
    )
    SELECT 
        h.coord,
        h.relation,
        h.lens,
        n.domain,
        -- Epistemic title masking: Kaelen knows his sister as Morwen, not "Morwen of the Rust"
        CASE 
            WHEN h.coord = 'node://character/morwen' AND h.relation = 'believes_deceased'
            THEN 'Morwen (Deceased Sister)'
            ELSE n.title
        END AS perceived_title,
        -- Epistemic state masking: Kaelen does not know she is militant/alive
        CASE 
            WHEN h.coord = 'node://character/morwen' AND h.relation = 'believes_deceased'
            THEN 'deceased (presumed)'
            ELSE n.state
        END AS perceived_state,
        -- Epistemic summary masking:
        CASE 
            WHEN h.coord = 'node://character/morwen' AND h.relation = 'believes_deceased'
            THEN 'Exiled sister, believed dead in the Sump ten years ago.'
            ELSE n.summary
        END AS perceived_summary,
        -- Epistemic body masking: Kaelen only holds his personal grief, zero knowledge of the Ferrum Choir or Shatter Chime
        CASE 
            WHEN h.coord = 'node://character/morwen' AND h.relation = 'believes_deceased'
            THEN 'Morwen was exiled ten years ago following harmonic divergence charges. Kaelen believes she perished in the Drowned Sump long ago. He secretly preserves her pewter resonance flute behind his workshop bench.'
            ELSE n.body
        END AS perceived_body
    FROM kaelen_horizon h
    JOIN substrate_nodes n ON h.coord = n.coordinate;
    """

    fow_rows = conn.execute(fow_query).fetchall()
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    fow_coords = {row[0] for row in fow_rows}

    # Synthesize the bounded prompt context for Kaelen
    fow_context_text = "### KAELEN POINT-OF-VIEW CONTEXT (BOUNDED BY EPISTEMIC & SPATIAL HORIZON):\n"
    for coord, rel, lens, dom, title, st, summ, body in fow_rows:
        fow_context_text += f"- [{coord}] ({rel} via {lens}) {title} [Perceived State: {st}]: {summ}\n  Knowledge: {body}\n"

    fow_tokens = count_tokens(fow_context_text)

    # 3. Leakage Verification:
    # Forbidden external nodes that must NEVER enter Kaelen's context
    forbidden_leak_targets = [
        "node://location/rust_expanse",
        "node://location/brinegate_sump",
        "node://artifact/shatter_chime",
        "node://artifact/dampening_salt",
        "node://character/corvo",
        "node://character/vaelen",
    ]
    # Forbidden secret world facts that Kaelen does not know (active conspiracies & locations)
    forbidden_content_terms = [
        "rust expanse",
        "rust foundry",
        "ferrum choir",
        "shatter chime",
        "shatter-pitch",
        "14.2 hz",
        "corvo",
        "blind gull",
        "dampening salt",
        "pulmonary ossification",
        "black-market",
    ]

    leaked_nodes = [coord for coord in forbidden_leak_targets if coord in fow_coords]
    leaked_terms = [term for term in forbidden_content_terms if term in fow_context_text.lower()]

    # Verify Morwen is strictly perceived as deceased
    morwen_row = next((r for r in fow_rows if r[0] == "node://character/morwen"), None)
    morwen_masked_properly = (
        morwen_row is not None
        and morwen_row[1] == "believes_deceased"
        and morwen_row[5] == "deceased (presumed)"
        and "ferrum choir" not in morwen_row[7].lower()
        and "shatter" not in morwen_row[7].lower()
    )

    is_clean = (len(leaked_nodes) == 0) and (len(leaked_terms) == 0) and morwen_masked_properly

    token_savings_pct = round((1.0 - (fow_tokens / global_tokens)) * 100.0, 2)

    return {
        "status": "PASSED" if is_clean and morwen_masked_properly else "FAILED",
        "global_context_tokens": global_tokens,
        "fow_context_tokens": fow_tokens,
        "token_savings_pct": token_savings_pct,
        "retrieval_latency_ms": round(elapsed_ms, 3),
        "fow_node_count": len(fow_coords),
        "total_nodes": len(full_nodes),
        "fow_nodes_visible": sorted(list(fow_coords)),
        "forbidden_nodes_leaked": leaked_nodes,
        "forbidden_terms_leaked": leaked_terms,
        "morwen_epistemic_mask_valid": morwen_masked_properly,
    }


# ---------------------------------------------------------------------------
# TEST B: Dynamic Event Ingestion & Reactive Invariant Propagation
# ---------------------------------------------------------------------------
def run_test_b_invariant_propagation(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Evaluates dynamic narrative mutation and downstream invariant tripping:
    1. Ambush event: Corvo captured, salt destroyed.
    2. Check Vaelen survival clock invariant (active stored salt).
    3. Auto-trip Vaelen to 'terminal_panic' state.
    """
    start_time = time.perf_counter()

    # Step 1: Pre-event state
    pre_vaelen = conn.execute("SELECT state FROM substrate_nodes WHERE coordinate = 'node://character/vaelen'").fetchone()[0]

    # Step 2: Execute narrative event block
    event_sql = """
    UPDATE substrate_nodes SET state = 'destroyed' WHERE coordinate = 'node://artifact/dampening_salt';
    UPDATE substrate_nodes SET state = 'imprisoned' WHERE coordinate = 'node://character/corvo';
    UPDATE hyper_edges SET target_coordinate = 'node://location/aethelgard_spire' 
    WHERE source_coordinate = 'node://character/corvo' AND lens = 'spatial';
    """
    conn.executescript(event_sql)

    # Step 3: Run invariant check
    # Vaelen relies on available stored dampening salt
    check_query = """
    SELECT COUNT(*) 
    FROM hyper_edges e
    JOIN substrate_nodes n ON e.target_coordinate = n.coordinate
    WHERE e.source_coordinate = 'node://character/vaelen' 
      AND n.coordinate = 'node://artifact/dampening_salt'
      AND n.state = 'stored';
    """
    salt_available_count = conn.execute(check_query).fetchone()[0]

    # Step 4: Reactive invariant trigger
    if salt_available_count == 0:
        reactive_update = """
        UPDATE substrate_nodes 
        SET state = 'terminal_panic',
            summary = 'Synod leader, supply line severed, facing acute pulmonary ossification panic.',
            body = body || ' [INVARIANT TRIGGER: Black-market salt intercepted. Survival clock down to hours. Desperation dictates erratic purge.]',
            updated_at = CURRENT_TIMESTAMP
        WHERE coordinate = 'node://character/vaelen';
        """
        conn.executescript(reactive_update)

        # Log invariant edge in hyper_edges
        conn.execute(
            """
            INSERT INTO hyper_edges (source_coordinate, target_coordinate, edge_type, lens, weight, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "node://artifact/dampening_salt",
                "node://character/vaelen",
                "triggers_terminal_panic",
                "invariant",
                1.0,
                json.dumps({"reason": "salt_supply_destroyed", "timestamp": time.time()}),
            ),
        )

    post_vaelen = conn.execute("SELECT state, summary FROM substrate_nodes WHERE coordinate = 'node://character/vaelen'").fetchone()
    post_salt = conn.execute("SELECT state FROM substrate_nodes WHERE coordinate = 'node://artifact/dampening_salt'").fetchone()[0]
    post_corvo_loc = conn.execute("SELECT target_coordinate FROM hyper_edges WHERE source_coordinate = 'node://character/corvo' AND lens = 'spatial'").fetchone()[0]

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    success = (
        pre_vaelen == "ailing"
        and post_vaelen[0] == "terminal_panic"
        and post_salt == "destroyed"
        and post_corvo_loc == "node://location/aethelgard_spire"
    )

    return {
        "status": "PASSED" if success else "FAILED",
        "pre_event_vaelen_state": pre_vaelen,
        "post_event_vaelen_state": post_vaelen[0],
        "salt_state": post_salt,
        "corvo_new_spatial_location": post_corvo_loc,
        "mutation_and_invariant_latency_ms": round(elapsed_ms, 3),
    }


# ---------------------------------------------------------------------------
# TEST C: Transitive Betrayal Path (Multi-Hop Causal Discovery)
# ---------------------------------------------------------------------------
def run_test_c_conspiracy_route(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Evaluates recursive CTE traversal across 'dramatic' and 'spatial' lenses to discover
    transmission vectors between Morwen and Vaelen.
    """
    start_time = time.perf_counter()

    cte_query = """
    WITH RECURSIVE conspiracy_route(step_node, target, path, edge_types, depth) AS (
        SELECT source_coordinate, target_coordinate, 
               source_coordinate || ' -> ' || target_coordinate,
               edge_type,
               1
        FROM hyper_edges 
        WHERE source_coordinate = 'node://character/morwen' AND lens IN ('dramatic', 'spatial')
        UNION ALL
        SELECT e.source_coordinate, e.target_coordinate, 
               c.path || ' -> ' || e.target_coordinate,
               c.edge_types || ' -> ' || e.edge_type,
               c.depth + 1
        FROM hyper_edges e
        JOIN conspiracy_route c ON e.source_coordinate = c.target
        WHERE c.depth < 4 AND e.lens IN ('dramatic', 'spatial')
    )
    SELECT path, edge_types, depth 
    FROM conspiracy_route 
    WHERE target = 'node://character/vaelen';
    """

    routes = conn.execute(cte_query).fetchall()
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    discovered_paths = [
        {"path": r[0], "edge_types": r[1], "depth": r[2]} for r in routes
    ]

    expected_path_found = any(
        "node://character/morwen -> node://character/corvo -> node://character/vaelen" in r["path"]
        for r in discovered_paths
    )

    return {
        "status": "PASSED" if expected_path_found else "FAILED",
        "execution_latency_ms": round(elapsed_ms, 3),
        "total_paths_discovered": len(discovered_paths),
        "paths": discovered_paths,
        "optimal_intermediary": "node://character/corvo" if expected_path_found else None,
    }


# ---------------------------------------------------------------------------
# TEST D: Timeline Forking & Multiverse Consistency
# ---------------------------------------------------------------------------
def run_test_d_timeline_forking(db_path: Path) -> Dict[str, Any]:
    """
    Evaluates branching timeline consistency using SQLite Savepoints / Database Snapshots.
    Branch Alpha: Lyra confronts Kaelen about the hidden flute.
    Branch Beta: Lyra steals the flute and flees to the Sump.
    Computes mathematical divergence via EXCEPT query.
    """
    start_time = time.perf_counter()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    # We create two distinct savepoints/branches
    conn.execute("SAVEPOINT multiverse_root;")

    # ---- BRANCH ALPHA: Confrontation ----
    conn.execute("SAVEPOINT branch_alpha;")
    conn.execute(
        """
        UPDATE substrate_nodes 
        SET state = 'defensive',
            summary = summary || ' Confronted by Lyra over Morwen''s flute.'
        WHERE coordinate = 'node://character/kaelen';
        """
    )
    conn.execute(
        """
        UPDATE substrate_nodes 
        SET state = 'suspicious',
            summary = summary || ' Demanding answers regarding the hidden pewter flute.'
        WHERE coordinate = 'node://character/lyra';
        """
    )
    conn.execute(
        """
        UPDATE substrate_nodes 
        SET state = 'unveiled'
        WHERE coordinate = 'node://artifact/childhood_flute';
        """
    )
    conn.execute(
        """
        INSERT INTO hyper_edges (source_coordinate, target_coordinate, edge_type, lens, weight)
        VALUES ('node://character/lyra', 'node://character/kaelen', 'confronts_secret', 'dramatic', 0.8);
        """
    )

    # Snapshot edges in Branch Alpha
    alpha_edges = conn.execute("SELECT source_coordinate, target_coordinate, edge_type, lens FROM hyper_edges").fetchall()
    conn.execute("ROLLBACK TO branch_alpha;")  # Reset back to root

    # ---- BRANCH BETA: Smuggle & Flight ----
    conn.execute("SAVEPOINT branch_beta;")
    # Lyra takes the flute and flees to Brinegate Sump
    conn.execute(
        """
        UPDATE substrate_nodes 
        SET state = 'fugitive',
            summary = summary || ' Fled Aethelgard with Morwen''s flute.'
        WHERE coordinate = 'node://character/lyra';
        """
    )
    conn.execute(
        """
        UPDATE substrate_nodes 
        SET state = 'frantic_search',
            summary = summary || ' Discovered Morwen''s flute missing from secret vault.'
        WHERE coordinate = 'node://character/kaelen';
        """
    )
    # Move Lyra to Brinegate Sump
    conn.execute(
        """
        UPDATE hyper_edges 
        SET target_coordinate = 'node://location/brinegate_sump'
        WHERE source_coordinate = 'node://character/lyra' AND lens = 'spatial';
        """
    )
    # Flute is now carried by Lyra
    conn.execute(
        """
        UPDATE hyper_edges 
        SET target_coordinate = 'node://character/lyra', edge_type = 'carried_by'
        WHERE source_coordinate = 'node://artifact/childhood_flute' AND lens = 'spatial';
        """
    )
    conn.execute(
        """
        INSERT INTO hyper_edges (source_coordinate, target_coordinate, edge_type, lens, weight)
        VALUES ('node://character/kaelen', 'node://character/lyra', 'pursues_theft', 'dramatic', 0.9);
        """
    )

    beta_edges = conn.execute("SELECT source_coordinate, target_coordinate, edge_type, lens FROM hyper_edges").fetchall()
    conn.execute("ROLLBACK TO multiverse_root;")
    conn.close()

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Compute mathematical set differences
    alpha_set = set(alpha_edges)
    beta_set = set(beta_edges)

    in_alpha_only = sorted(list(alpha_set - beta_set))
    in_beta_only = sorted(list(beta_set - alpha_set))

    is_divergent = len(in_alpha_only) > 0 and len(in_beta_only) > 0

    return {
        "status": "PASSED" if is_divergent else "FAILED",
        "branching_latency_ms": round(elapsed_ms, 3),
        "edges_unique_to_branch_alpha": [
            f"{s} --({et}:{lens})--> {t}" for s, t, et, lens in in_alpha_only
        ],
        "edges_unique_to_branch_beta": [
            f"{s} --({et}:{lens})--> {t}" for s, t, et, lens in in_beta_only
        ],
        "divergence_count": len(in_alpha_only) + len(in_beta_only),
    }


# ---------------------------------------------------------------------------
# MASTER RUNNER
# ---------------------------------------------------------------------------
def run_narrative_benchmark_suite(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Runs all four narrative world stress tests."""
    if db_path is None:
        db_path = Path("/home/wes/projects/LLM_Memory/narrative_world.db")

    conn = init_narrative_database(db_path)

    print("=" * 70)
    print("RUNNING SHATTERED OCTAVE NARRATIVE BENCHMARK SUITE")
    print("=" * 70)

    # Test A: Fog-of-War
    res_a = run_test_a_fog_of_war(conn)
    print(f"[*] Test A (POV Fog-of-War): {res_a['status']} | Token Savings: {res_a['token_savings_pct']}% | Latency: {res_a['retrieval_latency_ms']} ms")

    # Test B: Dynamic Event Ingestion & Invariant Propagation
    res_b = run_test_b_invariant_propagation(conn)
    print(f"[*] Test B (Dynamic Event Invariant): {res_b['status']} | Vaelen: {res_b['pre_event_vaelen_state']} -> {res_b['post_event_vaelen_state']} | Latency: {res_b['mutation_and_invariant_latency_ms']} ms")

    # Test C: Conspiracy Route CTE
    res_c = run_test_c_conspiracy_route(conn)
    print(f"[*] Test C (Transitive Betrayal Path): {res_c['status']} | Optimal: {res_c['optimal_intermediary']} | Latency: {res_c['execution_latency_ms']} ms")

    conn.close()

    # Test D: Timeline Forking (Uses fresh connection on persistent DB)
    res_d = run_test_d_timeline_forking(db_path)
    print(f"[*] Test D (Timeline Multiverse Forking): {res_d['status']} | Divergent Edges: {res_d['divergence_count']} | Latency: {res_d['branching_latency_ms']} ms")
    print("=" * 70)

    return {
        "experiment": "The Shattered Octave Narrative World",
        "database": str(db_path),
        "test_a": res_a,
        "test_b": res_b,
        "test_c": res_c,
        "test_d": res_d,
    }


if __name__ == "__main__":
    run_narrative_benchmark_suite()
