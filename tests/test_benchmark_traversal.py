import sqlite3
from pathlib import Path
from tools.map_codebase import index_codebase
from tools.benchmark_traversal import TraversalBenchmark


def test_map_codebase_indexing(tmp_path):
    db_file = tmp_path / "test_substrate.db"
    repo_root = Path.cwd().resolve()
    res = index_codebase(target_dirs=["core", "api"], db_path=db_file, repo_root=repo_root)

    assert res["status"] == "success"
    assert res["nodes_indexed"] > 20
    assert res["edges_indexed"] > 20
    assert "call_graph" in res["lens_counts"]
    assert "structural" in res["lens_counts"]
    assert "imports" in res["lens_counts"]

    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    # Check that substrate_nodes has correct schema
    cols = [r[1] for r in cur.execute("PRAGMA table_info(substrate_nodes);").fetchall()]
    assert set(cols) == {"coordinate", "node_type", "summary", "body"}

    # Check that hyper_edges has correct schema
    edge_cols = [r[1] for r in cur.execute("PRAGMA table_info(hyper_edges);").fetchall()]
    assert set(edge_cols) == {"source", "target", "lens"}
    conn.close()


def test_traversal_benchmark_execution(tmp_path):
    db_file = tmp_path / "test_substrate.db"
    bench = TraversalBenchmark(db_path=db_file)
    res = bench.execute_benchmark(force_reindex=True)

    assert res["hops"] >= 2
    assert "handle_create_project" in res["chain_path"]
    assert "create_project" in res["chain_path"]
    assert res["token_reduction_pct"] > 80.0
    assert res["speedup_factor"] > 1.0
    assert res["method_b_substrate"]["false_positive_noise"] == 0
    assert res["method_b_substrate"]["precision_rate_pct"] == 100.0

    # Verify markdown report creation
    md_file = bench.repo_root / "benchmark_results.md"
    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")
    assert "| Metric | Grep / Text Search | Relational Substrate | Delta / Improvement |" in content
