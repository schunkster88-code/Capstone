import pytest
from pathlib import Path
from tools.triangulate_fault import triangulate_fault


@pytest.fixture(scope="module")
def substrate_db():
    db_path = Path("code_substrate.db")
    assert db_path.exists(), "code_substrate.db must exist"
    return db_path


def test_triangulation_intersection_and_ranking(substrate_db):
    """Verify that multiple disparate test suites intersect on common callee functions."""
    test_roots = [
        "node://code/tests/test_fanout_benchmark.py:test_list_projects_parameter_behavior",
        "node://code/tests/test_mark2_codebase.py:test_mark2_initial_seed_integrity",
        "node://code/tests/test_void.py:test_api_schema_empty",
    ]

    res = triangulate_fault(
        failing_test_coords=test_roots,
        db_path=substrate_db,
        fetch_body=True,
    )

    assert res["failing_test_count"] == 3
    assert res["total_intersection_candidates"] >= 1
    assert res["culprit"] is not None

    # #1 culprit must be get_projects_dir (leaf-most common ancestor)
    assert res["culprit"]["coordinate"] == "node://code/core/project_manager.py:get_projects_dir"
    assert res["culprit"]["node_type"] == "function"
    assert res["culprit"]["max_depth"] >= 5


def test_triangulation_token_budget(substrate_db):
    """Verify that triangulating the culprit node ingests < 500 tokens."""
    test_roots = [
        "node://code/tests/test_projects.py:test_list_and_create_projects",
        "node://code/tests/test_fanout_benchmark.py:test_api_routes_branch_propagation",
        "node://code/tests/test_mark2_codebase.py:test_mark2_initial_seed_integrity",
    ]

    res = triangulate_fault(
        failing_test_coords=test_roots,
        db_path=substrate_db,
        fetch_body=True,
    )

    culprit = res["culprit"]
    assert culprit is not None
    assert culprit["body_tokens_estimate"] < 100.0, "Culprit body must be well under 500 tokens"
    assert "PROJECTS_DIR" in culprit["body"]


def test_triangulation_error_handling(substrate_db):
    """Verify error handling for invalid or empty coordinates."""
    with pytest.raises(ValueError, match="At least one failing test coordinate is required"):
        triangulate_fault([], db_path=substrate_db)

    with pytest.raises(ValueError, match="Test coordinate\\(s\\) not found"):
        triangulate_fault(["node://code/tests/non_existent.py:test_fake"], db_path=substrate_db)
