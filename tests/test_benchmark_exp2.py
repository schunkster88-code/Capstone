import pytest
from pathlib import Path
from benchmarks.benchmark_exp2 import execute_experiment_2


def test_experiment_2_multi_lens_conflict_resolution(tmp_path):
    """Test that pre-filtering by semantic lens eliminates circular loops and isolates critical path."""
    results = execute_experiment_2(num_trials=3, db_dir=tmp_path)
    assert results["hypothesis_validated"] is True
    assert results["metrics"]["hyperweb_circular_loop_rate"] == 0.0
    assert results["metrics"]["hyperweb_accuracy"] == 100.0
    assert results["metrics"]["baseline_circular_loop_rate"] >= 80.0

