import pytest
from pathlib import Path
from benchmarks.benchmark_exp4 import execute_experiment_4


def test_experiment_4_self_healing_topology(tmp_path):
    """Test that autonomous agent remediation restores pipeline throughput idempotently with 100% provenance."""
    results = execute_experiment_4(num_trials=3, db_dir=tmp_path)
    assert results["hypothesis_validated"] is True
    assert results["metrics"]["hyperweb_recovery_rate_pct"] == 100.0
    assert results["metrics"]["idempotency_success_rate_pct"] == 100.0
    assert results["metrics"]["provenance_audit_accuracy_pct"] == 100.0
    assert results["metrics"]["schema_alterations_required"] == 0

