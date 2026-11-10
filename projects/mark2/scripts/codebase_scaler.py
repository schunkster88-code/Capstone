"""
id: codebase_scaler
name: Codebase Scaler
description: Bundled Python simulation routine
default_params: {}
"""

import json
import random
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, Any

def scale_mark2_codebase(
    db_path: Path,
    num_modules: int = 20,
    classes_per_module: int = 5,
    methods_per_class: int = 4,
    seed: int = 42,
) -> Dict[str, Any]:
    random.seed(seed)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")

    start_time = time.perf_counter()

    subsystems = [
        "auth", "telemetry", "scheduler", "storage", "worker",
        "network", "ai_agent", "pipeline", "gateway", "cache",
        "vector_index", "crypto", "metrics", "logging", "events",
        "consensus", "rpc", "compiler", "sandbox", "profiler"
    ]

    nodes_to_insert = []
    edges_to_insert = []

    # Track all created methods to build call graphs
    all_methods = []
    all_modules = []

    # 1. Generate Subsystem Modules, Classes, and Methods
    for mod_idx in range(num_modules):
        subsys_name = subsystems[mod_idx % len(subsystems)]
        mod_name = f"mark.{subsys_name}.service_{mod_idx + 1}"
        mod_coord = f"node://code/mark/{subsys_name}/service_{mod_idx + 1}"
        all_modules.append(mod_coord)

        nodes_to_insert.append((
            mod_coord,
            "module",
            mod_name,
            "active",
            f"Module for {subsys_name} subsystem handling partition {mod_idx + 1}.",
            f"Exports service primitives, async connection pools, and lifecycle handlers for {subsys_name}."
        ))

        # Root app mounts services
        edges_to_insert.append((
            "node://code/mark/app",
            mod_coord,
            "mounts_subsystem",
            "structural",
            1.0,
            json.dumps({"subsystem": subsys_name})
        ))

        for c_idx in range(classes_per_module):
            cls_name = f"{subsys_name.title()}Handler{c_idx + 1}"
            cls_coord = f"{mod_coord}/{cls_name}"

            nodes_to_insert.append((
                cls_coord,
                "class",
                cls_name,
                "active",
                f"Core business logic class {cls_name} inside {mod_name}.",
                f"Implements thread-safe operations, caching policies, and state validation for {subsys_name}."
            ))

            # Structural edge: module defines class
            edges_to_insert.append((
                mod_coord,
                cls_coord,
                "defines_class",
                "structural",
                1.0,
                None
            ))

            for m_idx in range(methods_per_class):
                method_name = f"handle_step_{m_idx + 1}"
                method_coord = f"{cls_coord}/{method_name}"
                all_methods.append(method_coord)

                nodes_to_insert.append((
                    method_coord,
                    "method",
                    f"{cls_name}.{method_name}",
                    "active",
                    f"Executes pipeline operation {m_idx + 1} for {cls_name}.",
                    f"Validates payload schema, performs async RPC step, and emits telemetry event."
                ))

                # Structural edge: class defines method
                edges_to_insert.append((
                    cls_coord,
                    method_coord,
                    "defines_method",
                    "structural",
                    1.0,
                    None
                ))

    # 2. Wire Multi-Lens Call Graph & Data Flow Edges
    # Connect ExecutionEngine.run_task to services
    run_task_coord = "node://code/mark/core/engine/run_task"
    flightdeck_coord = "node://code/mark/routers/flightdeck"

    for i in range(min(5, len(all_methods))):
        edges_to_insert.append((
            run_task_coord,
            all_methods[i],
            "dispatches_to",
            "call_graph",
            0.9,
            None
        ))

    # Random call graph invocations across methods (DAG-leaning)
    for i, m_coord in enumerate(all_methods):
        if i + 1 < len(all_methods):
            # Pick 1-2 downstream methods
            targets = random.sample(all_methods[i + 1:], min(2, len(all_methods) - (i + 1)))
            for t in targets:
                edges_to_insert.append((
                    m_coord,
                    t,
                    "calls",
                    "call_graph",
                    round(random.uniform(0.5, 1.0), 2),
                    None
                ))

        # Data flow streaming to flightdeck or telemetry
        if random.random() < 0.25:
            edges_to_insert.append((
                m_coord,
                flightdeck_coord,
                "emits_telemetry_to",
                "data_flow",
                0.4,
                json.dumps({"metric_type": "latency_counter"})
            ))

    with conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO substrate_nodes (coordinate, domain, title, state, summary, body)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            nodes_to_insert
        )
        conn.executemany(
            """
            INSERT INTO hyper_edges (source_coordinate, target_coordinate, edge_type, lens, weight, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            edges_to_insert
        )

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    total_nodes = conn.execute("SELECT COUNT(*) FROM substrate_nodes").fetchone()[0]
    total_edges = conn.execute("SELECT COUNT(*) FROM hyper_edges").fetchone()[0]
    conn.close()

    return {
        "status": "success",
        "inserted_nodes": len(nodes_to_insert),
        "inserted_edges": len(edges_to_insert),
        "total_nodes_in_db": total_nodes,
        "total_edges_in_db": total_edges,
        "population_time_ms": round(elapsed_ms, 2)
    }

if __name__ == "__main__":
    num_mods = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    cls_per_mod = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    m_per_cls = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    db_path = Path(__file__).resolve().parent.parent / "project.db"
    res = scale_mark2_codebase(db_path, num_mods, cls_per_mod, m_per_cls)
    print("=== SCALE TEST POPULATION COMPLETED ===")
    print(f"Nodes Injected: {res['inserted_nodes']} | Total Nodes: {res['total_nodes_in_db']}")
    print(f"Edges Injected: {res['inserted_edges']} | Total Edges: {res['total_edges_in_db']}")
    print(f"Population Latency: {res['population_time_ms']} ms")
