import sqlite3
from pathlib import Path
import pytest

from tools.blast_radius import trace_upstream_blast_radius
from tools.trace_runtime import RuntimeTracer


@pytest.fixture(scope="module")
def substrate_db():
    db_path = Path("code_substrate.db")
    assert db_path.exists(), "code_substrate.db must exist"
    return db_path


def test_static_ast_blind_spot(substrate_db):
    """Verify that static AST analysis snaps the edge at dynamic dispatch boundaries."""
    target_cmd = "node://code/core/void_engine.py:handle_create_project_cmd"
    static_res = trace_upstream_blast_radius(
        target_coord=target_cmd,
        db_path=substrate_db,
        lenses=["call_graph"],
    )
    # Static AST discovers 0 upstream callers due to dynamic dict/string dispatch
    assert static_res["upstream_count"] == 0
    assert len(static_res["upstream_callers"]) == 0

    target_list_cmd = "node://code/core/void_engine.py:handle_list_projects_cmd"
    static_list_res = trace_upstream_blast_radius(
        target_coord=target_list_cmd,
        db_path=substrate_db,
        lenses=["call_graph"],
    )
    assert static_list_res["upstream_count"] == 0


def test_runtime_trace_edge_capture(substrate_db):
    """Verify that code_substrate.db contains runtime_trace edges captured during execution."""
    conn = sqlite3.connect(str(substrate_db))
    cur = conn.cursor()

    # Verify runtime_trace lens exists
    trace_count = cur.execute(
        "SELECT COUNT(*) FROM hyper_edges WHERE lens = 'runtime_trace'"
    ).fetchone()[0]
    assert trace_count > 0, "hyper_edges must contain runtime_trace records"

    # Verify specific dynamic dispatch edge was captured
    edge = cur.execute(
        """
        SELECT source, target, lens FROM hyper_edges 
        WHERE source = 'node://code/core/void_engine.py:dispatch_console_command'
          AND target = 'node://code/core/void_engine.py:handle_create_project_cmd'
          AND lens = 'runtime_trace'
        """
    ).fetchone()
    assert edge is not None, "Dynamic dispatch edge must be captured by runtime tracer"
    conn.close()


def test_multiplex_blast_radius_recovery(substrate_db):
    """Verify that multiplex mode bridges dynamic edges into static call graph."""
    target_cmd = "node://code/core/void_engine.py:handle_create_project_cmd"
    multiplex_res = trace_upstream_blast_radius(
        target_coord=target_cmd,
        db_path=substrate_db,
        lenses=["call_graph", "runtime_trace"],
    )

    # Discovers upstream callers: dispatch_console_command, execute_raw, run_command
    assert multiplex_res["upstream_count"] >= 3
    coords = [c["coordinate"] for c in multiplex_res["upstream_callers"]]
    assert "node://code/core/void_engine.py:dispatch_console_command" in coords
    assert "node://code/core/void_engine.py:execute_raw" in coords
    assert "node://code/server.py:run_command" in coords

    # Verify provenance tagging
    dispatch_node = next(
        c for c in multiplex_res["upstream_callers"]
        if c["coordinate"] == "node://code/core/void_engine.py:dispatch_console_command"
    )
    assert dispatch_node["provenance"] == "dynamic:runtime_trace"
    assert dispatch_node["depth"] == 1


def test_multi_lens_schema_orthogonality(substrate_db):
    """Verify schema remained strictly two tables with orthogonal lenses."""
    conn = sqlite3.connect(str(substrate_db))
    cur = conn.cursor()

    tables = [
        r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    ]
    assert "substrate_nodes" in tables
    assert "hyper_edges" in tables

    # Verify lenses present in hyper_edges
    lenses = {
        r[0] for r in cur.execute("SELECT DISTINCT lens FROM hyper_edges").fetchall()
    }
    assert "call_graph" in lenses
    assert "runtime_trace" in lenses
    assert "structural" in lenses
    assert "imports" in lenses

    conn.close()
