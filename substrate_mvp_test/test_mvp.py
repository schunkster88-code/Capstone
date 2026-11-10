# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

"""MVP Capstone Validation Test Suite."""

import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure substrate_mvp_test is on sys.path
BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from init_db import init_database
from parser import parse_and_ingest_fixture
from tracer import trace_upstream_dependencies
from benchmark import run_ab_benchmark, run_cte_substrate, run_grep_baseline


@pytest.fixture(scope="module")
def mvp_env(tmp_path_factory):
    """Set up temporary isolated test environment for MVP test suite."""
    tmp_dir = tmp_path_factory.mktemp("substrate_mvp")
    fixture_dir = BASE_DIR / "fixture"
    db_path = tmp_dir / "test_substrate.db"

    conn = init_database(db_path, schema_file=BASE_DIR / "schema.sql")
    conn.close()

    stats = parse_and_ingest_fixture(fixture_dir, db_path)
    return {
        "tmp_dir": tmp_dir,
        "fixture_dir": fixture_dir,
        "db_path": db_path,
        "stats": stats,
    }


def test_fixture_integrity(mvp_env):
    """Test 1: Verify 5 fixture files exist and can execute the full workflow."""
    fixture_dir = mvp_env["fixture_dir"]
    expected_files = [
        fixture_dir / "main.py",
        fixture_dir / "core" / "router.py",
        fixture_dir / "core" / "engine.py",
        fixture_dir / "core" / "validator.py",
        fixture_dir / "storage" / "db.py",
    ]
    for ef in expected_files:
        assert ef.exists(), f"Expected fixture file missing: {ef}"

    # Dynamically run main.py workflow in isolated subprocess
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(fixture_dir / "main.py")],
        cwd=str(fixture_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Execution Result:" in proc.stdout
    assert "'persisted': True" in proc.stdout


def test_sqlite_wal_schema_and_indexes(mvp_env):
    """Test 2: Verify SQLite WAL mode, two-table schema, and compound B-tree indexes."""
    db_path = mvp_env["db_path"]
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Check journal mode
    cur.execute("PRAGMA journal_mode;")
    j_mode = cur.fetchone()[0]
    assert j_mode.upper() == "WAL"

    # Check tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {r[0] for r in cur.fetchall()}
    assert "substrate_nodes" in tables
    assert "hyper_edges" in tables

    # Check compound B-tree indexes
    cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indexes = {r[0] for r in cur.fetchall()}
    assert "idx_edges_forward" in indexes
    assert "idx_edges_reverse" in indexes

    conn.close()


def test_ast_parser_ingestion(mvp_env):
    """Test 3: Verify AST parser populates nodes and call_graph hyper_edges."""
    db_path = mvp_env["db_path"]
    stats = mvp_env["stats"]
    assert stats["nodes_indexed"] >= 10
    assert stats["edges_indexed"] >= 5

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Check nodes
    cur.execute("SELECT coordinate, node_type, summary FROM substrate_nodes;")
    nodes = {r[0]: r[1] for r in cur.fetchall()}
    assert "node://code/storage/db.py:save_record" in nodes
    assert "node://code/core/engine.py:execute_workflow" in nodes
    assert "node://code/core/router.py:route_request" in nodes
    assert "node://code/main.py:handle_cli_command" in nodes

    # Check call_graph edges
    cur.execute("SELECT source, target, lens FROM hyper_edges WHERE lens = 'call_graph';")
    edges = {(r[0], r[1]) for r in cur.fetchall()}
    assert ("node://code/main.py:handle_cli_command", "node://code/core/router.py:route_request") in edges
    assert ("node://code/core/router.py:route_request", "node://code/core/engine.py:execute_workflow") in edges
    assert ("node://code/core/engine.py:execute_workflow", "node://code/storage/db.py:save_record") in edges

    conn.close()


def test_recursive_cte_3hop_trace(mvp_env):
    """Test 4: Verify recursive CTE performs a complete 3-hop upstream dependency trace."""
    db_path = mvp_env["db_path"]
    target = "node://code/storage/db.py:save_record"

    res = trace_upstream_dependencies(target, db_path, max_depth=3)
    assert res["target"] == target
    assert res["total_callers"] >= 3
    assert res["execution_latency_ms"] < 20.0  # Sub-20ms bound

    depth_map = {c["coordinate"]: c["depth"] for c in res["callers_found"]}
    assert depth_map["node://code/core/engine.py:execute_workflow"] == 1
    assert depth_map["node://code/core/validator.py:audit_validation"] == 1
    assert depth_map["node://code/core/router.py:route_request"] == 2
    assert depth_map["node://code/main.py:handle_cli_command"] == 3


def test_ab_benchmark_execution(mvp_env):
    """Test 5: Verify automated A/B benchmark execution and comparative telemetry."""
    fixture_dir = mvp_env["fixture_dir"]
    db_path = mvp_env["db_path"]

    grep_res = run_grep_baseline(fixture_dir, target_symbol="save_record")
    cte_res = run_cte_substrate(db_path, target_coord="node://code/storage/db.py:save_record")

    # Verify zero false positives for CTE
    assert cte_res["false_positives"] == 0
    assert grep_res["false_positives"] > 0

    # Verify token reduction
    assert cte_res["token_payload_summary"] < grep_res["token_payload_full_files"]
    savings_pct = (1.0 - (cte_res["token_payload_summary"] / grep_res["token_payload_full_files"])) * 100.0
    assert savings_pct > 75.0  # At least 75% planning token savings

    # Run the full A/B benchmark generator
    report = run_ab_benchmark(num_trials=20)
    assert "Capstone MVP Substrate A/B Benchmark Results" in report
    assert "Empirical Comparative Matrix" in report
    assert "| **Execution Latency (Mean)** |" in report
