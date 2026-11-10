import pytest
import sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from server import app
from core.sim_telemetry import (
    init_sim_db,
    get_readonly_connection,
    get_telemetry_frame,
    record_telemetry_frame,
)


@pytest.fixture(autouse=True)
def setup_sim_db(tmp_path, monkeypatch):
    test_db = tmp_path / "sim.db"
    import core.sim_telemetry as sim_core
    monkeypatch.setattr(sim_core, "SIM_DB_PATH", test_db)
    init_sim_db(test_db, force_seed=True)
    yield test_db


def test_telemetry_endpoint_latest(setup_sim_db):
    with TestClient(app) as client:
        resp = client.get("/api/sim/telemetry?latest=true")
        assert resp.status_code == 200
        data = resp.json()

        assert "step" in data
        assert "max_step" in data
        assert data["step"] == data["max_step"]
        assert "grid" in data
        assert "width" in data["grid"]
        assert "height" in data["grid"]
        assert "cells" in data
        assert isinstance(data["cells"], list)
        assert len(data["cells"]) > 0
        assert "attributes" in data["cells"][0]
        assert "entities" in data
        assert isinstance(data["entities"], list)
        assert "events" in data
        assert isinstance(data["events"], list)


def test_telemetry_endpoint_specific_step(setup_sim_db):
    with TestClient(app) as client:
        resp = client.get("/api/sim/telemetry?step=6")
        assert resp.status_code == 200
        data = resp.json()

        assert data["step"] == 6
        assert data["max_step"] == 10
        assert data["grid"]["width"] == 4
        assert data["grid"]["height"] == 4

        # Verify entity schema
        agent = next((e for e in data["entities"] if e["id"] == "agent_1"), None)
        assert agent is not None
        assert agent["x"] == 1
        assert agent["y"] == 1
        assert "energy" in agent["attributes"]
        assert "stress_level" in agent["attributes"]
        assert agent["attributes"]["last_action"] == "returned_to_1_1"


def test_telemetry_endpoint_not_found(setup_sim_db):
    with TestClient(app) as client:
        resp = client.get("/api/sim/telemetry?step=9999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


def test_readonly_concurrency_constraint(setup_sim_db):
    db_path = setup_sim_db
    conn = get_readonly_connection(db_path)

    # Check PRAGMA query_only is ON
    cur = conn.cursor()
    cur.execute("PRAGMA query_only;")
    assert cur.fetchone()[0] == 1

    # Verify write attempts fail with operational error
    with pytest.raises(sqlite3.OperationalError) as exc_info:
        conn.execute("INSERT INTO sim_telemetry (step, grid_width, grid_height, cells, entities, events) VALUES (99, 1, 1, '[]', '[]', '[]');")
    assert "readonly" in str(exc_info.value).lower()
    conn.close()


def test_sim_viewer_html_route():
    with TestClient(app) as client:
        resp = client.get("/sim-viewer")
        assert resp.status_code == 200
        text = resp.text

        # Verify required controls
        assert 'id="stepScrubber"' in text
        assert 'id="prevBtn"' in text
        assert 'id="nextBtn"' in text
        assert 'id="liveFollow"' in text
        assert 'id="stepCounter"' in text

        # Verify arena and inspector panes
        assert 'id="gridSvg"' in text
        assert 'id="inspectorTitle"' in text
        assert 'id="inspectorProps"' in text
        assert 'id="inspectorTabs"' in text
        assert 'tab-pill' in text
        assert 'fetchTelemetry' in text

        # Verify wave field rendering hook
        assert 'rgba(0, 240, 255' in text
        assert 'rgba(0, 200, 255' in text
        assert 'rgba(220, 50, 150' in text
        assert 'cellBoxShadow' in text

        # Verify play button & 0.25 fps auto-step playback
        assert 'id="playBtn"' in text
        assert 'id="playSpeedSelect"' in text
        assert '0.25 FPS' in text
        assert 'togglePlay' in text
        assert 'changePlaySpeed' in text

