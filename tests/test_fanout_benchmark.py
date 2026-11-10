# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

import inspect
from core.project_manager import list_projects
from core.void_engine import execute_raw
from api.routes.projects import handle_list_projects, handle_get_active_project, handle_get_project
from tools.blast_radius import trace_upstream_blast_radius


def test_fanout_blast_radius_discovery():
    target = "node://code/core/project_manager.py:list_projects"
    res = trace_upstream_blast_radius(target)

    coords = [c["coordinate"] for c in res["upstream_callers"]]
    # Verify all distinct branches are discovered
    assert "node://code/api/routes/projects.py:handle_list_projects" in coords
    assert "node://code/api/routes/projects.py:handle_get_active_project" in coords
    assert "node://code/api/routes/projects.py:handle_get_project" in coords
    assert "node://code/core/void_engine.py:execute_raw" in coords
    assert "node://code/server.py:run_command" in coords

    # Check distinct files calling
    files = {c["coordinate"].split("node://code/")[1].split(":")[0] for c in res["upstream_callers"]}
    assert files == {"api/routes/projects.py", "core/void_engine.py", "server.py"}


def test_list_projects_parameter_behavior():
    sig = inspect.signature(list_projects)
    assert "include_metadata" in sig.parameters
    assert sig.parameters["include_metadata"].default is True

    # Test with include_metadata=True
    with_meta = list_projects(include_metadata=True)
    assert len(with_meta) > 0
    default_proj = next((p for p in with_meta if p["name"] == "default"), None)
    assert default_proj is not None
    assert default_proj["include_metadata"] is True
    assert default_proj["description"] != ""

    # Test with include_metadata=False
    without_meta = list_projects(include_metadata=False)
    default_no_meta = next((p for p in without_meta if p["name"] == "default"), None)
    assert default_no_meta is not None
    assert default_no_meta["include_metadata"] is False
    assert default_no_meta["description"] == ""  # metadata skipped


def test_api_routes_branch_propagation():
    # Branch A: handle_list_projects
    res_list = handle_list_projects(include_metadata=False)
    assert len(res_list) > 0
    assert res_list[0]["include_metadata"] is False

    # Branch B: handle_get_active_project
    res_active = handle_get_active_project(include_metadata=False)
    assert "name" in res_active
    assert res_active.get("include_metadata", False) is False

    # Branch C: handle_get_project
    res_proj = handle_get_project("default", include_metadata=False)
    assert res_proj["name"] == "default"
    assert res_proj["include_metadata"] is False


def test_void_engine_branch_propagation():
    # Branch D: execute_raw console command
    result = execute_raw("LIST PROJECTS")
    assert result["type"] == "query"
    assert result["count"] > 0
    assert result["rows"][0]["include_metadata"] is True
