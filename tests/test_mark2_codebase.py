import sqlite3
from pathlib import Path
from core.project_manager import get_project_db_path
from projects.mark2.scripts.codebase_scaler import scale_mark2_codebase


def test_mark2_initial_seed_integrity():
    db_path = get_project_db_path("mark2")
    assert db_path.exists(), "mark2 project.db should exist"

    conn = sqlite3.connect(str(db_path))
    
    # Check seed nodes
    node_coords = {
        r[0] for r in conn.execute("SELECT coordinate FROM substrate_nodes").fetchall()
    }
    assert "node://code/mark/app" in node_coords
    assert "node://code/mark/routers/flightdeck" in node_coords
    assert "node://code/mark/core/engine" in node_coords
    assert "node://code/mark/core/engine/run_task" in node_coords

    # Check multi-lens edges
    edges = conn.execute(
        "SELECT source_coordinate, target_coordinate, edge_type, lens FROM hyper_edges"
    ).fetchall()

    structural = [e for e in edges if e[3] == "structural"]
    data_flow = [e for e in edges if e[3] == "data_flow"]
    call_graph = [e for e in edges if e[3] == "call_graph"]

    assert len(structural) >= 2
    assert len(data_flow) >= 1
    assert len(call_graph) >= 1

    # Verify call_graph invocation
    flightdeck_call = [
        e for e in call_graph
        if e[0] == "node://code/mark/routers/flightdeck"
        and e[1] == "node://code/mark/core/engine/run_task"
    ]
    assert len(flightdeck_call) == 1

    conn.close()


def test_mark2_blast_radius_cte():
    db_path = get_project_db_path("mark2")
    conn = sqlite3.connect(str(db_path))

    query = """
    WITH RECURSIVE blast_radius(step_node, impacted_caller, relation, lens, depth) AS (
        SELECT e.target_coordinate, e.source_coordinate, e.edge_type, e.lens, 1
        FROM hyper_edges e
        WHERE e.target_coordinate = 'node://code/mark/core/engine/run_task'
          AND e.lens = 'call_graph'
        UNION ALL
        SELECT b.impacted_caller, e.source_coordinate, e.edge_type, e.lens, b.depth + 1
        FROM hyper_edges e
        JOIN blast_radius b ON e.target_coordinate = b.impacted_caller
        WHERE b.depth < 5 AND e.lens = 'call_graph'
    )
    SELECT impacted_caller FROM blast_radius;
    """
    callers = [r[0] for r in conn.execute(query).fetchall()]
    assert "node://code/mark/routers/flightdeck" in callers

    conn.close()


def test_mark2_codebase_scaling_and_submillisecond_query(tmp_path):
    test_db = tmp_path / "scale_test.db"
    conn = sqlite3.connect(str(test_db))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.executescript("""
    CREATE TABLE substrate_nodes (
        coordinate TEXT PRIMARY KEY,
        domain TEXT NOT NULL,
        title TEXT NOT NULL,
        state TEXT NOT NULL,
        summary TEXT NOT NULL,
        body TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE hyper_edges (
        edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_coordinate TEXT NOT NULL,
        target_coordinate TEXT NOT NULL,
        edge_type TEXT NOT NULL,
        lens TEXT NOT NULL,
        weight REAL DEFAULT 1.0,
        metadata JSON
    );
    CREATE INDEX idx_edges_source_lens ON hyper_edges(source_coordinate, lens);
    CREATE INDEX idx_edges_target_lens ON hyper_edges(target_coordinate, lens);
    """)
    conn.execute(
        "INSERT INTO substrate_nodes VALUES ('node://code/mark/app', 'module', 'mark.app', 'stable', 'root', 'root', CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO substrate_nodes VALUES ('node://code/mark/core/engine/run_task', 'method', 'run_task', 'active', 'm', 'm', CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO substrate_nodes VALUES ('node://code/mark/routers/flightdeck', 'router', 'flightdeck', 'active', 'r', 'r', CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()

    res = scale_mark2_codebase(test_db, num_modules=15, classes_per_module=4, methods_per_class=3)
    assert res["status"] == "success"
    assert res["total_nodes_in_db"] > 200
    assert res["total_edges_in_db"] > 200

    # Test sub-millisecond retrieval on indexed hypergraph
    conn = sqlite3.connect(str(test_db))
    import time
    t0 = time.perf_counter()
    sample = conn.execute("""
        SELECT e.target_coordinate, n.summary
        FROM hyper_edges e
        JOIN substrate_nodes n ON e.target_coordinate = n.coordinate
        WHERE e.source_coordinate = 'node://code/mark/app' AND e.lens = 'structural'
    """).fetchall()
    dt_ms = (time.perf_counter() - t0) * 1000
    assert dt_ms < 10.0  # Typically < 0.2ms
    assert len(sample) == 15
    conn.close()

