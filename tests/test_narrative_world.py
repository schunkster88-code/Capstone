import sqlite3
from pathlib import Path
from benchmarks.narrative_world_benchmark import (
    init_narrative_database,
    run_test_a_fog_of_war,
    run_test_b_invariant_propagation,
    run_test_c_conspiracy_route,
    run_test_d_timeline_forking,
    run_narrative_benchmark_suite,
)


def test_narrative_world_seed_and_schema(tmp_path):
    db_file = tmp_path / "test_seed.db"
    conn = init_narrative_database(db_file)

    nodes = conn.execute("SELECT COUNT(*) FROM substrate_nodes").fetchone()[0]
    edges = conn.execute("SELECT COUNT(*) FROM hyper_edges").fetchone()[0]

    assert nodes == 11
    assert edges == 17  # 8 spatial + 5 epistemic + 4 dramatic

    conn.close()


def test_test_a_fog_of_war_boundary(tmp_path):
    db_file = tmp_path / "test_a.db"
    conn = init_narrative_database(db_file)

    res = run_test_a_fog_of_war(conn)

    assert res["status"] == "PASSED"
    assert res["token_savings_pct"] > 60.0
    assert len(res["forbidden_nodes_leaked"]) == 0
    assert len(res["forbidden_terms_leaked"]) == 0
    assert res["morwen_epistemic_mask_valid"] is True
    assert "node://character/corvo" not in res["fow_nodes_visible"]
    assert "node://location/rust_expanse" not in res["fow_nodes_visible"]

    conn.close()


def test_test_b_dynamic_event_and_invariant(tmp_path):
    db_file = tmp_path / "test_b.db"
    conn = init_narrative_database(db_file)

    res = run_test_b_invariant_propagation(conn)

    assert res["status"] == "PASSED"
    assert res["pre_event_vaelen_state"] == "ailing"
    assert res["post_event_vaelen_state"] == "terminal_panic"
    assert res["salt_state"] == "destroyed"
    assert res["corvo_new_spatial_location"] == "node://location/aethelgard_spire"

    conn.close()


def test_test_c_conspiracy_route_cte(tmp_path):
    db_file = tmp_path / "test_c.db"
    conn = init_narrative_database(db_file)

    res = run_test_c_conspiracy_route(conn)

    assert res["status"] == "PASSED"
    assert res["optimal_intermediary"] == "node://character/corvo"
    assert res["execution_latency_ms"] < 20.0  # Typically < 1 ms

    conn.close()


def test_test_d_timeline_forking(tmp_path):
    db_file = tmp_path / "test_d.db"
    init_narrative_database(db_file).close()

    res = run_test_d_timeline_forking(db_file)

    assert res["status"] == "PASSED"
    assert res["divergence_count"] > 0
    assert len(res["edges_unique_to_branch_alpha"]) > 0
    assert len(res["edges_unique_to_branch_beta"]) > 0


def test_master_narrative_benchmark_suite(tmp_path):
    db_file = tmp_path / "master_narrative.db"
    suite_res = run_narrative_benchmark_suite(db_file)

    assert suite_res["test_a"]["status"] == "PASSED"
    assert suite_res["test_b"]["status"] == "PASSED"
    assert suite_res["test_c"]["status"] == "PASSED"
    assert suite_res["test_d"]["status"] == "PASSED"

