import pytest
import sqlite3
from fastapi.testclient import TestClient
from server import app
import api.routes.workbench as wb_route
from core.workbench_substrate import CognitiveWorkbench

@pytest.fixture
def workbench_instance(tmp_path):
    db_file = str(tmp_path / "test_connectome.db")
    wb = CognitiveWorkbench(db_path=db_file, max_active_nodes=30)
    # Seed initial schema
    wb.conn.executescript("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        key TEXT NOT NULL UNIQUE,
        value TEXT NOT NULL,
        access_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS memory_edges (
        source_key TEXT NOT NULL,
        target_key TEXT NOT NULL,
        relation TEXT DEFAULT 'associated',
        weight REAL DEFAULT 1.0,
        PRIMARY KEY (source_key, target_key)
    );

    CREATE TABLE IF NOT EXISTS system_invariants (
        id TEXT PRIMARY KEY,
        statement TEXT NOT NULL,
        crystallized_from TEXT NOT NULL,
        confidence REAL DEFAULT 1.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS epoch_archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        epoch_number INTEGER NOT NULL,
        original_key TEXT NOT NULL,
        category TEXT NOT NULL,
        value TEXT NOT NULL,
        final_access_count INTEGER NOT NULL,
        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS task_dag_ledger (
        task_id TEXT PRIMARY KEY,
        description TEXT,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS cognitive_scratchpad (
        session_id TEXT NOT NULL,
        entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_tag TEXT NOT NULL,
        payload_type TEXT NOT NULL CHECK (payload_type IN ('graph_fragment', 'tabular_sim', 'raw_hypothesis')),
        data_payload TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE VIEW IF NOT EXISTS v_context_horizon_canonical AS
    SELECT 
        m.key AS origin,
        e.target_key AS reachable_concept,
        m.category AS category,
        1 AS min_depth,
        e.weight AS max_conductance,
        1 AS unique_path_permutations
    FROM memories m
    LEFT JOIN memory_edges e ON m.key = e.source_key;

    CREATE VIEW IF NOT EXISTS v_substrate_health AS
    SELECT 
        (SELECT COUNT(*) FROM memories) AS active_nodes,
        (SELECT COUNT(*) FROM memory_edges) AS edge_count,
        (SELECT COUNT(*) FROM system_invariants) AS invariant_count,
        'healthy' AS status;
    """)
    return wb

def test_savepoint_branch_and_rollback_zero_residual(workbench_instance):
    wb = workbench_instance
    cur = wb.conn.cursor()

    cur.execute("SELECT count(*) FROM memories;")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT count(*) FROM memory_edges;")
    assert cur.fetchone()[0] == 0

    # Branch savepoint
    sp = wb.branch_savepoint("transfactual_hypothesis_1")
    assert sp == "transfactual_hypothesis_1"

    # Add nodes and edges inside savepoint
    wb.conn.execute("INSERT INTO memories (category, key, value, access_count) VALUES ('hypothesis', 'hypo_1', 'val_1', 1);")
    wb.conn.execute("INSERT INTO memories (category, key, value, access_count) VALUES ('hypothesis', 'hypo_2', 'val_2', 1);")
    wb.conn.execute("INSERT INTO memory_edges (source_key, target_key, weight) VALUES ('hypo_1', 'hypo_2', 0.85);")

    cur.execute("SELECT count(*) FROM memories;")
    assert cur.fetchone()[0] == 2
    cur.execute("SELECT count(*) FROM memory_edges;")
    assert cur.fetchone()[0] == 1

    # Rollback savepoint
    wb.rollback_savepoint("transfactual_hypothesis_1")

    # Verify zero residual nodes or edges
    cur.execute("SELECT count(*) FROM memories;")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT count(*) FROM memory_edges;")
    assert cur.fetchone()[0] == 0

def test_savepoint_identifier_validation(workbench_instance):
    wb = workbench_instance
    with pytest.raises(ValueError):
        wb.branch_savepoint("invalid; DROP TABLE memories; --")

def test_forbid_trigger_creation(workbench_instance):
    wb = workbench_instance
    with pytest.raises(PermissionError):
        wb.mutate_substrate("CREATE TRIGGER trg_test AFTER INSERT ON memories BEGIN SELECT 1; END;")

def test_query_lens_read_only(workbench_instance):
    wb = workbench_instance
    with pytest.raises(PermissionError):
        wb.query_lens(custom_select="DELETE FROM memories;")

def test_api_crystallize_and_working_memory_cap(workbench_instance, monkeypatch):
    wb = workbench_instance
    monkeypatch.setattr(wb_route, "_workbench_instance", wb)

    # Populate 32 memories
    for i in range(32):
        wb.conn.execute(
            "INSERT INTO memories (category, key, value, access_count) VALUES ('concept', ?, ?, ?);",
            (f"node_{i}", f"value_{i}", i),
        )
    wb.conn.execute("INSERT INTO memory_edges (source_key, target_key, weight) VALUES ('node_0', 'node_1', 0.5);")
    wb.conn.commit()

    with TestClient(app) as client:
        payload = {
            "axiom_id": "axiom_99",
            "statement": "Energy conservation holds across simulated branches.",
            "crystallized_from": "node_0",
            "prune_keys": ["node_0"],
            "epoch_number": 3
        }
        resp = client.post("/api/workbench/crystallize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["crystallized"] == "axiom_99"
        assert data["archived_scaffolding"] == 1

        # Check system_invariants has the new row
        cur = wb.conn.cursor()
        cur.execute("SELECT statement, crystallized_from, confidence FROM system_invariants WHERE id = 'axiom_99';")
        row = cur.fetchone()
        assert row is not None
        assert row["statement"] == "Energy conservation holds across simulated branches."
        assert row["crystallized_from"] == "node_0"
        assert row["confidence"] == 1.0

        # Check prune_keys were archived in epoch_archive
        cur.execute("SELECT original_key, epoch_number FROM epoch_archive WHERE original_key = 'node_0';")
        archived = cur.fetchone()
        assert archived is not None
        assert archived["original_key"] == "node_0"
        assert archived["epoch_number"] == 3

        # Check node_0 is pruned from memories and edges
        cur.execute("SELECT count(*) FROM memories WHERE key = 'node_0';")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM memory_edges WHERE source_key = 'node_0' OR target_key = 'node_0';")
        assert cur.fetchone()[0] == 0

        # Check active_nodes <= 30
        cur.execute("SELECT count(*) FROM memories;")
        active_count = cur.fetchone()[0]
        assert active_count <= 30

def test_api_savepoint_router(workbench_instance, monkeypatch):
    wb = workbench_instance
    monkeypatch.setattr(wb_route, "_workbench_instance", wb)

    with TestClient(app) as client:
        # Branch
        resp = client.post("/api/workbench/savepoint", json={"name": "branch_alpha", "action": "branch"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["savepoint"] == "branch_alpha"

        # Rollback
        resp = client.post("/api/workbench/savepoint", json={"name": "branch_alpha", "action": "rollback"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

def test_api_sleep_consolidation(workbench_instance, monkeypatch):
    wb = workbench_instance
    monkeypatch.setattr(wb_route, "_workbench_instance", wb)

    wb.conn.execute("INSERT INTO memory_edges (source_key, target_key, weight) VALUES ('k1', 'k2', 0.90);")
    wb.conn.commit()

    with TestClient(app) as client:
        resp = client.post("/api/workbench/sleep_consolidate?decay_factor=0.90")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "consolidated"
        assert data["decay_factor"] == 0.90

        cur = wb.conn.cursor()
        cur.execute("SELECT weight FROM memory_edges WHERE source_key = 'k1' AND target_key = 'k2';")
        assert cur.fetchone()[0] == 0.81

