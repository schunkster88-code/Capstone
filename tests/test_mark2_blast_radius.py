from benchmarks.benchmark_mark2_blast_radius import (
    execute_blast_radius_benchmark,
    generate_codebase_with_needle,
    evaluate_condition_a_grep_baseline,
    evaluate_condition_b_hyperweb_cte,
)
import sqlite3


def test_blast_radius_benchmark_suite(tmp_path):
    results = execute_blast_radius_benchmark(num_trials=3, db_dir=tmp_path)

    metrics = results["metrics"]
    assert metrics["token_reduction_pct"] > 95.0
    assert metrics["token_efficiency_factor"] > 50.0
    assert metrics["mean_hyperweb_precision"] == 100.0
    assert metrics["mean_hyperweb_recall"] == 100.0
    assert metrics["mean_baseline_precision"] < 10.0
    assert metrics["mean_hyperweb_latency_ms"] < 5.0
    assert metrics["latency_speedup_factor"] > 10.0


def test_blast_radius_single_trial_isolation():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    topo = generate_codebase_with_needle(conn, trial_seed=42)

    res_a = evaluate_condition_a_grep_baseline(
        conn, topo["target_name"], topo["ground_truth_impacted"], topo["target_coord"]
    )
    res_b = evaluate_condition_b_hyperweb_cte(
        conn, topo["target_coord"], topo["ground_truth_impacted"]
    )

    assert res_b["precision_pct"] == 100.0
    assert res_b["recall_pct"] == 100.0
    assert res_b["false_positives"] == 0
    assert res_b["false_negatives"] == 0
    assert res_b["causal_depth_reached"] == 4
    assert res_a["recall_pct"] < 100.0  # Missed top-level transitive callers

    conn.close()

