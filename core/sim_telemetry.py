from pathlib import Path
import json
import sqlite3
from typing import Any, Dict, List, Optional

SIM_DB_PATH = Path("sim.db")


def init_sim_db(db_path: Optional[Path] = None, force_seed: bool = False) -> None:
    """Initialize the simulation telemetry database with WAL mode and seed data."""
    target_path = SIM_DB_PATH if db_path is None else db_path
    conn = sqlite3.connect(target_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sim_telemetry (
            step INTEGER PRIMARY KEY,
            grid_width INTEGER NOT NULL,
            grid_height INTEGER NOT NULL,
            cells TEXT NOT NULL,
            entities TEXT NOT NULL,
            events TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        """
        CREATE VIEW IF NOT EXISTS v_sim_telemetry AS
        SELECT step, grid_width, grid_height, cells, entities, events, created_at
        FROM sim_telemetry;
        """
    )
    conn.execute(
        """
        CREATE VIEW IF NOT EXISTS v_sim_entities AS
        SELECT 
            t.step,
            json_extract(e.value, '$.id') AS entity_id,
            CAST(json_extract(e.value, '$.x') AS INTEGER) AS x,
            CAST(json_extract(e.value, '$.y') AS INTEGER) AS y,
            json_extract(e.value, '$.attributes') AS attributes
        FROM sim_telemetry t, json_each(t.entities) e;
        """
    )
    conn.execute(
        """
        CREATE VIEW IF NOT EXISTS v_sim_cells AS
        SELECT 
            t.step,
            CAST(json_extract(c.value, '$.x') AS INTEGER) AS x,
            CAST(json_extract(c.value, '$.y') AS INTEGER) AS y,
            json_extract(c.value, '$.attributes') AS attributes
        FROM sim_telemetry t, json_each(t.cells) c;
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sim_scripts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            script_body TEXT NOT NULL,
            default_params TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        """
        CREATE VIEW IF NOT EXISTS v_sim_scripts AS
        SELECT id, name, description, script_body, default_params, created_at, updated_at
        FROM sim_scripts;
        """
    )

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sim_telemetry;")
    count = cur.fetchone()[0]

    if count == 0 or force_seed:
        seed_demo_telemetry(conn)

    conn.commit()
    conn.close()


def seed_demo_telemetry(conn: sqlite3.Connection) -> None:
    """Seed steps 0 through 10 with realistic simulation progression."""
    width, height = 4, 4

    # Baseline cell map for 4x4 grid
    def make_cells(step: int) -> List[Dict[str, Any]]:
        cells = []
        for x in range(width):
            for y in range(height):
                hazard = 25.0 if (x == 1 and y == 0) or (x == 2 and y == 2 and step > 3) else 0.0
                resource = 1.0 if (x == 1 and y == 1) or (x == 3 and y == 3 and step > 5) else 0.0
                cells.append({
                    "x": x,
                    "y": y,
                    "attributes": {
                        "traversable": not (x == 2 and y == 1),
                        "resource": resource,
                        "hazard": hazard,
                        "elevation": round((x + y) * 0.5, 1)
                    }
                })
        return cells

    # Agent positions across steps 0-10
    agent_path = [
        (0, 0), (0, 1), (1, 1), (1, 2), (0, 2),
        (0, 1), (1, 1), (1, 2), (2, 2), (3, 2), (3, 3)
    ]

    for s in range(11):
        ax, ay = agent_path[s]
        energy = round(160.0 - s * 2.2 + (10.0 if (ax, ay) == (1, 1) else 0), 2)
        stress = round(4.0 + (3.5 if (ax, ay) in [(1, 0), (2, 2)] else 0.3 * (s % 3)), 2)
        action_name = "returned_to_1_1" if s == 6 else (f"move_to_{ax}_{ay}" if s > 0 else "spawn")
        surprise = 0.44 if s == 6 else round(0.12 * ((s * 3) % 7 + 1), 2)

        entities = [
            {
                "id": "agent_1",
                "x": ax,
                "y": ay,
                "attributes": {
                    "energy": energy,
                    "stress_level": stress,
                    "last_action": action_name,
                    "cumulative_surprise": round(60.0 + s * 2.37, 2),
                    "active_goal": "forage_resource" if s < 8 else "return_to_hub",
                    "alive": True
                }
            }
        ]

        # Add a secondary scout entity at later steps
        if s >= 4:
            entities.append({
                "id": "drone_alpha",
                "x": (s - 3) % width,
                "y": 3,
                "attributes": {
                    "energy": 90.0,
                    "mode": "recon",
                    "altitude": 12.5,
                    "signal_db": -42.0
                }
            })

        events = [
            {"step": s, "action": action_name, "surprise": surprise}
        ]
        if (ax, ay) == (1, 1):
            events.append({"step": s, "action": "harvest_resource", "yield": 1.0})

        conn.execute(
            """
            INSERT OR REPLACE INTO sim_telemetry (step, grid_width, grid_height, cells, entities, events)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                s,
                width,
                height,
                json.dumps(make_cells(s)),
                json.dumps(entities),
                json.dumps(events)
            )
        )


def get_readonly_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open an SQLite connection strictly in read-only mode."""
    target_path = SIM_DB_PATH if db_path is None else db_path
    if not target_path.exists():
        init_sim_db(target_path)

    # Use URI file:... mode=ro to prevent any write locks or journal operations
    conn = sqlite3.connect(f"file:{target_path.resolve()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")
    return conn


def get_telemetry_frame(
    step: Optional[int] = None,
    latest: bool = False,
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Fetch standardized simulation telemetry frame in read-only mode."""
    target_path = SIM_DB_PATH if db_path is None else db_path
    with get_readonly_connection(target_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(step) AS max_step FROM sim_telemetry;")
        row_max = cur.fetchone()
        if not row_max or row_max["max_step"] is None:
            return None

        max_step = row_max["max_step"]

        if latest or step is None:
            target_step = max_step
        else:
            target_step = step

        cur.execute(
            """
            SELECT step, grid_width, grid_height, cells, entities, events
            FROM sim_telemetry
            WHERE step = ?;
            """,
            (target_step,)
        )
        row = cur.fetchone()
        if not row:
            return None

        return {
            "step": row["step"],
            "max_step": max_step,
            "grid": {
                "width": row["grid_width"],
                "height": row["grid_height"]
            },
            "cells": json.loads(row["cells"]),
            "entities": json.loads(row["entities"]),
            "events": json.loads(row["events"])
        }


def record_telemetry_frame(
    step: int,
    grid_width: int,
    grid_height: int,
    cells: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    db_path: Optional[Path] = None
) -> None:
    """Record a new telemetry frame into the simulation database."""
    target_path = SIM_DB_PATH if db_path is None else db_path
    conn = sqlite3.connect(target_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute(
        """
        INSERT OR REPLACE INTO sim_telemetry (step, grid_width, grid_height, cells, entities, events)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (step, grid_width, grid_height, json.dumps(cells), json.dumps(entities), json.dumps(events))
    )
    conn.commit()
    conn.close()

