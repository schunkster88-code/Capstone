import pytest
from pathlib import Path
from benchmarks.benchmark_exp1 import execute_experiment_1


def test_experiment_1_token_budget_needle(tmp_path):
    """Test that progressive disclosure with OpenGraph link previews reduces token usage >= 75%."""
    results = execute_experiment_1(num_trials=3, db_dir=tmp_path)
    assert results["hypothesis_validated"] is True
    assert results["metrics"]["mean_token_savings_percent"] >= 75.0
    assert results["metrics"]["hyperweb_accuracy"] == 1.0
    assert results["metrics"]["token_reduction_factor"] >= 10.0

