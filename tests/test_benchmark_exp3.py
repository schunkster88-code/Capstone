import pytest
from pathlib import Path
from benchmarks.benchmark_exp3 import execute_experiment_3


def test_experiment_3_teleological_drift_benchmark(tmp_path):
    """Test that manifold path tracking prevents teleological drift and eliminates tangential token waste."""
    results = execute_experiment_3(num_trials=3, db_dir=tmp_path)
    assert results["hypothesis_validated"] is True
    assert results["metrics"]["mean_hyperweb_hops"] == 3.0
    assert results["metrics"]["mean_hyperweb_wasted_tokens"] == 0.0
    assert results["metrics"]["hyperweb_goal_completion_rate"] == 100.0
    assert results["metrics"]["token_waste_eliminated_pct"] == 100.0

