import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from server import app
import core.project_manager as pm
from core.sim_runner import save_script, list_scripts, get_script


@pytest.fixture
def project_test_env(tmp_path, monkeypatch):
    test_projects_dir = tmp_path / "projects"
    test_active_file = test_projects_dir / ".active_project"
    monkeypatch.setattr(pm, "PROJECTS_DIR", test_projects_dir)
    monkeypatch.setattr(pm, "ACTIVE_PROJECT_FILE", test_active_file)

    pm.init_default_project()
    yield test_projects_dir


def test_list_and_create_projects(project_test_env):
    with TestClient(app) as client:
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        projs = resp.json()
        assert len(projs) >= 1
        assert any(p["name"] == "default" and p["is_active"] for p in projs)

        # Create new project
        create_resp = client.post("/api/projects/create", json={
            "name": "neural_swarm",
            "description": "Flocking simulation with local alignment"
        })
        assert create_resp.status_code == 200
        created = create_resp.json()
        assert created["name"] == "neural_swarm"
        assert Path(created["db_path"]).exists()
        assert Path(created["scripts_dir"]).exists()

        # Verify listed
        projs_after = client.get("/api/projects").json()
        assert any(p["name"] == "neural_swarm" for p in projs_after)


def test_activate_project_and_bundle_scripts(project_test_env):
    with TestClient(app) as client:
        # Create and activate
        client.post("/api/projects/create", json={"name": "colony_alpha"})
        act_resp = client.post("/api/projects/activate", json={"name": "colony_alpha"})
        assert act_resp.status_code == 200
        data = act_resp.json()
        assert data["active_project"] == "colony_alpha"

        # Check active endpoint
        active_resp = client.get("/api/projects/active")
        assert active_resp.status_code == 200
        assert active_resp.json()["name"] == "colony_alpha"

        # 1. Save script via API -> must write to colony_alpha/scripts/forage_tune.py
        save_resp = client.post("/api/sim/script/save", json={
            "id": "forage_tune",
            "name": "Forage Tuning",
            "description": "Adjusts step discount",
            "script_body": "def step(state, params, emit_step):\n    pass\n",
            "default_params": {"discount": 0.9}
        })
        assert save_resp.status_code == 200

        disk_file = project_test_env / "colony_alpha" / "scripts" / "forage_tune.py"
        assert disk_file.exists()
        content = disk_file.read_text()
        assert "Forage Tuning" in content
        assert "discount" in content

        # 2. Write script directly to disk -> must be auto-discovered by API
        manual_py = project_test_env / "colony_alpha" / "scripts" / "manual_pulse.py"
        manual_py.write_text('''"""
id: manual_pulse
name: Manual Pulse Routine
description: Periodic pulse emitter
default_params: {"freq": 5}
"""
def step(state, params, emit_step):
    pass
''')

        scripts_list = client.get("/api/sim/scripts").json()
        assert any(s["id"] == "manual_pulse" for s in scripts_list)

        # Single get should also load it
        get_res = client.get("/api/sim/script/manual_pulse")
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Manual Pulse Routine"


def test_console_json_payload_and_commands(project_test_env):
    with TestClient(app) as client:
        # 1. Test pasting raw JSON payload into /api/execute
        payload = """{
            "name": "hyper_web_sim",
            "description": "Graph-relational hybrid substrate with hyperlinked rows and script execution nodes",
            "template": "sim"
        }"""
        resp = client.post("/api/execute", json={"sql": payload})
        assert resp.status_code == 200
        res = resp.json()
        assert res["status"] == "success"
        assert res["result"]["type"] == "project_create"
        assert res["result"]["project"]["active_project"] == "hyper_web_sim"

        # Check project files created
        assert (project_test_env / "hyper_web_sim" / "project.db").exists()

        # 2. Test text command: CREATE PROJECT
        cmd_resp = client.post("/api/execute", json={"sql": "CREATE PROJECT alpha_grid;"})
        assert cmd_resp.status_code == 200
        assert cmd_resp.json()["result"]["type"] == "project_create"

        # 3. Test text command: LIST PROJECTS
        list_resp = client.post("/api/execute", json={"sql": "LIST PROJECTS;"})
        assert list_resp.status_code == 200
        assert list_resp.json()["result"]["type"] == "query"
        rows = list_resp.json()["result"]["rows"]
        assert any(r["name"] == "alpha_grid" for r in rows)


