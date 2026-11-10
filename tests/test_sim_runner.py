# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from server import app
import core.sim_telemetry as sim_telemetry
from core.sim_telemetry import init_sim_db, get_telemetry_frame
from core.sim_runner import (
    save_script,
    get_script,
    list_scripts,
    run_simulation,
    switch_simulation_db,
)


BASELINE_FORAGE_CODE = """
def step(state, params, emit_step):
    w = state["width"]
    h = state["height"]
    entities = [dict(e) for e in state["entities"]]
    events = []

    for e in entities:
        cx, cy = e["x"], e["y"]
        attrs = dict(e.get("attributes", {}))

        moves = [
            (cx + dx, cy + dy)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if 0 <= cx + dx < w and 0 <= cy + dy < h
        ]
        valid_moves = []
        for mx, my in moves:
            cell = next((c for c in state["cells"] if c["x"] == mx and c["y"] == my), None)
            if cell and cell.get("attributes", {}).get("traversable", True):
                valid_moves.append((mx, my))

        if valid_moves:
            nx, ny = random.choice(valid_moves)
            e["x"] = nx
            e["y"] = ny
            action_name = f"forage_to_{nx}_{ny}"
            attrs["last_action"] = action_name
            attrs["energy"] = round(attrs.get("energy", 100.0) - 1.0, 2)
            e["attributes"] = attrs
            events.append({"step": state["step"] + 1, "entity_id": e["id"], "action": action_name})

    emit_step(entities=entities, cells=state["cells"], events=events)
"""


@pytest.fixture
def sim_runner_env(tmp_path, monkeypatch):
    test_db = tmp_path / "test_sim_runner.db"
    monkeypatch.setattr(sim_telemetry, "SIM_DB_PATH", test_db)
    init_sim_db(test_db, force_seed=True)
    yield test_db
    # Restore primary sim.db pointer and symlink
    default_sim_db = Path("sim.db").resolve()
    sim_telemetry.SIM_DB_PATH = default_sim_db
    void_symlink = Path("void.db")
    try:
        if void_symlink.exists() or void_symlink.is_symlink():
            void_symlink.unlink()
        void_symlink.symlink_to(Path("sim.db"))
    except OSError:
        pass


def test_schema_and_script_save(sim_runner_env):
    with TestClient(app) as client:
        payload = {
            "id": "baseline_forage",
            "name": "Baseline Random Walk Foraging",
            "description": "Standard exploratory foraging pattern across traversable terrain",
            "script_body": BASELINE_FORAGE_CODE,
            "default_params": {"step_energy_cost": 1.0}
        }
        resp = client.post("/api/sim/script/save", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["id"] == "baseline_forage"

        # Verify listing
        list_resp = client.get("/api/sim/scripts")
        assert list_resp.status_code == 200
        scripts = list_resp.json()
        assert any(s["id"] == "baseline_forage" for s in scripts)

        # Verify single get
        get_resp = client.get("/api/sim/script/baseline_forage")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Baseline Random Walk Foraging"


def test_batch_advance_script_run(sim_runner_env):
    with TestClient(app) as client:
        # First save the script
        client.post("/api/sim/script/save", json={
            "id": "baseline_forage",
            "name": "Baseline Random Walk Foraging",
            "script_body": BASELINE_FORAGE_CODE,
            "default_params": {}
        })

        # Fetch current head step
        head_before = client.get("/api/sim/telemetry?latest=true").json()["step"]

        # Run 5 steps
        run_resp = client.post("/api/sim/script/run", json={
            "script_id": "baseline_forage",
            "steps": 5
        })
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        assert run_data["status"] == "success"
        assert run_data["steps_executed"] == 5
        assert run_data["head_step"] == head_before + 5

        # Verify new head step in telemetry
        head_after = client.get("/api/sim/telemetry?latest=true").json()
        assert head_after["step"] == head_before + 5
        assert head_after["max_step"] == head_before + 5


def test_inline_script_run(sim_runner_env):
    inline_code = """
def step(state, params, emit_step):
    entities = [dict(e) for e in state["entities"]]
    # Shift entity 0 to coordinate (0, 0)
    entities[0]["x"] = 0
    entities[0]["y"] = 0
    entities[0]["attributes"]["last_action"] = "teleport_origin"
    emit_step(entities=entities, cells=state["cells"], events=[{"action": "teleport"}])
"""
    with TestClient(app) as client:
        head_before = client.get("/api/sim/telemetry?latest=true").json()["step"]

        resp = client.post("/api/sim/script/run", json={
            "inline_script": inline_code,
            "steps": 1
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["steps_executed"] == 1
        assert data["head_step"] == head_before + 1

        # Check entity at (0, 0)
        head_frame = client.get("/api/sim/telemetry?latest=true").json()
        assert head_frame["entities"][0]["x"] == 0
        assert head_frame["entities"][0]["y"] == 0
        assert head_frame["entities"][0]["attributes"]["last_action"] == "teleport_origin"


def test_switch_db_endpoint(tmp_path, sim_runner_env):
    new_db = tmp_path / "alt_sim.db"
    with TestClient(app) as client:
        resp = client.post("/api/sim/switch_db", json={"db_path": str(new_db)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "sim_telemetry" in data["tables"]
        assert "sim_scripts" in data["tables"]
        assert new_db.exists()


def test_console_run_script_and_sim_run_function(sim_runner_env, monkeypatch):
    import core.void_engine as engine
    monkeypatch.setattr(engine, "DB_PATH", sim_runner_env)

    with TestClient(app) as client:
        # Save baseline script
        client.post("/api/sim/script/save", json={
            "id": "test_walk",
            "name": "Test Walk",
            "script_body": BASELINE_FORAGE_CODE,
            "default_params": {}
        })

        head_before = client.get("/api/sim/telemetry?latest=true").json()["step"]

        # Test 1: RUN SCRIPT <id> STEPS <n> via /api/execute
        cmd_resp = client.post("/api/execute", json={"sql": "RUN SCRIPT test_walk STEPS 2;"})
        assert cmd_resp.status_code == 200
        cmd_data = cmd_resp.json()
        assert cmd_data["status"] == "success"
        assert cmd_data["result"]["type"] == "sim_runner"
        assert cmd_data["result"]["steps_executed"] == 2
        assert cmd_data["result"]["head_step"] == head_before + 2

        # Test 2: SELECT sim_run('<id>', <n>); via /api/execute
        fn_resp = client.post("/api/execute", json={"sql": "SELECT sim_run('test_walk', 3);"})
        assert fn_resp.status_code == 200
        fn_data = fn_resp.json()
        assert fn_data["status"] == "success"
        assert fn_data["result"]["type"] == "query"
        assert fn_data["result"]["count"] == 1
        row = fn_data["result"]["rows"][0]
        val = next(iter(row.values()))
        import json
        parsed = json.loads(val)
        assert parsed["status"] == "success"
        assert parsed["steps_executed"] == 3
        assert parsed["head_step"] == head_before + 5

