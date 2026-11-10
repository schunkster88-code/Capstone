import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from server import app
import core.void_engine as engine

DB_FILES = [Path("test_void.db"), Path("test_void.db-wal"), Path("test_void.db-shm")]

def clean_db_files(db_path: Path):
    for ext in ["", "-wal", "-shm", "-journal"]:
        p = Path(f"{db_path}{ext}")
        if p.exists() or p.is_symlink():
            try:
                p.unlink()
            except OSError:
                pass

@pytest.fixture(autouse=True)
def run_around_tests(tmp_path, monkeypatch):
    test_db = tmp_path / "test_void.db"
    clean_db_files(test_db)
    monkeypatch.setattr(engine, "DB_PATH", test_db)
    yield
    clean_db_files(test_db)
    # Ensure default symlink void.db -> sim.db is intact
    sim_db = Path("sim.db")
    void_db = Path("void.db")
    if sim_db.exists() and not void_db.exists():
        try:
            void_db.symlink_to(sim_db)
        except OSError:
            pass

def test_zero_state_boot():
    engine.init_empty_db()
    schema = engine.inspect_schema()
    assert schema == []

def test_api_schema_empty():
    with TestClient(app) as client:
        resp = client.get("/api/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["schema"] == []

def test_api_execute_multi_statement_and_schema():
    with TestClient(app) as client:
        script = """
        CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);
        INSERT INTO items (name) VALUES ('item_1'), ('item_2');
        """
        resp = client.post("/api/execute", json={"sql": script})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["result"]["type"] == "script"
        assert data["result"]["status"] == "executed"

        # Check schema endpoint reflects newly created table
        schema_resp = client.get("/api/schema")
        assert schema_resp.status_code == 200
        schema_data = schema_resp.json()
        assert len(schema_data["schema"]) == 1
        assert schema_data["schema"][0]["name"] == "items"
        assert schema_data["schema"][0]["type"] == "table"

        # Query items
        query_resp = client.post("/api/execute", json={"sql": "SELECT * FROM items;"})
        assert query_resp.status_code == 200
        query_data = query_resp.json()
        assert query_data["result"]["type"] == "query"
        assert query_data["result"]["count"] == 2
        assert query_data["result"]["rows"][0]["name"] == "item_1"
        assert query_data["result"]["rows"][1]["name"] == "item_2"

def test_api_execute_mutation():
    with TestClient(app) as client:
        client.post("/api/execute", json={"sql": "CREATE TABLE logs (msg TEXT);"})
        resp = client.post("/api/execute", json={"sql": "INSERT INTO logs VALUES ('hello')"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["type"] == "mutation"
        assert data["result"]["status"] == "success"
        assert data["result"]["affected_rows"] == 1

def test_root_serves_html():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Void Substrate Raw IO" in resp.text
        assert "cmdInput" in resp.text
        assert "outputStream" in resp.text
        assert "Copy LLM Prompt" in resp.text
        assert "Copy Output" in resp.text
        assert "copyOutput" in resp.text
        assert "LLM_SYSTEM_PROMPT" in resp.text
        assert "<table" not in resp.text
