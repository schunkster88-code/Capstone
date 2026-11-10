import datetime
import inspect
import json
import math
import os
from pathlib import Path
import random
import sqlite3
import time
from typing import Any, Dict, List, Optional

import core.sim_telemetry as sim_telemetry
from core.sim_telemetry import (
    SIM_DB_PATH,
    get_readonly_connection,
    init_sim_db,
    record_telemetry_frame,
)


BASELINE_FORAGE_CODE = """def step(state, params, emit_step):
    w = state["width"]
    h = state["height"]
    entities = [dict(e) for e in state["entities"]]
    events = []

    for e in entities:
        cx, cy = e["x"], e["y"]
        attrs = dict(e.get("attributes", {}))

        # Check adjacent traversable moves
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
            action_name = f"forage_step_to_{nx}_{ny}"
            attrs["last_action"] = action_name
            attrs["energy"] = round(attrs.get("energy", 100.0) - params.get("energy_decay", 1.0), 2)
            attrs["stress_level"] = round(max(0.0, attrs.get("stress_level", 4.0) + random.uniform(-0.15, 0.15)), 2)
            attrs["cumulative_surprise"] = round(attrs.get("cumulative_surprise", 0.0) + random.uniform(0.1, 0.4), 2)
            e["attributes"] = attrs
            events.append({"step": state["step"] + 1, "entity_id": e["id"], "action": action_name, "surprise": 0.22})

    emit_step(entities=entities, cells=state["cells"], events=events)
"""


def get_active_db_path(db_path: Optional[Path] = None) -> Path:
    return sim_telemetry.SIM_DB_PATH if db_path is None else db_path


def save_script(
    script_id: str,
    name: str,
    description: str,
    script_body: str,
    default_params: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Upsert a script into the sim_scripts table and bundle as a .py file in the project's scripts folder."""
    target_db = get_active_db_path(db_path)
    init_sim_db(target_db)

    params_json = json.dumps(default_params or {})
    conn = sqlite3.connect(target_db)
    conn.execute(
        """
        INSERT INTO sim_scripts (id, name, description, script_body, default_params, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            script_body = excluded.script_body,
            default_params = excluded.default_params,
            updated_at = CURRENT_TIMESTAMP;
        """,
        (script_id, name, description, script_body, params_json),
    )
    conn.commit()
    conn.close()

    # Automatically bundle as a .py file in the project's scripts directory
    try:
        from core.project_manager import export_script_to_disk
        export_script_to_disk(
            script_id=script_id,
            name=name,
            description=description,
            script_body=script_body,
            default_params=default_params or {},
            db_path=target_db,
        )
    except Exception:
        pass

    return {"status": "success", "id": script_id, "name": name}


def get_script(script_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a script by id from sim_scripts (or discover directly from project's scripts/ folder)."""
    target_db = get_active_db_path(db_path)
    with get_readonly_connection(target_db) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, description, script_body, default_params, created_at, updated_at
            FROM sim_scripts
            WHERE id = ?;
            """,
            (script_id,),
        )
        row = cur.fetchone()

    if not row:
        # Check if script exists directly on disk in the project's scripts folder
        try:
            from core.project_manager import parse_script_file
            scripts_dir = target_db.parent / "scripts"
            cand_file = scripts_dir / f"{script_id}.py"
            if cand_file.exists():
                parsed = parse_script_file(cand_file)
                save_script(
                    script_id=parsed["id"],
                    name=parsed["name"],
                    description=parsed["description"],
                    script_body=parsed["script_body"],
                    default_params=parsed["default_params"],
                    db_path=target_db,
                )
                return {
                    "id": parsed["id"],
                    "name": parsed["name"],
                    "description": parsed["description"],
                    "script_body": parsed["script_body"],
                    "default_params": parsed["default_params"],
                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
        except Exception:
            pass
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "script_body": row["script_body"],
        "default_params": json.loads(row["default_params"] or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_scripts(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """List all available simulation scripts, auto-syncing from disk."""
    target_db = get_active_db_path(db_path)
    try:
        from core.project_manager import sync_scripts_from_disk_to_db
        sync_scripts_from_disk_to_db(target_db)
    except Exception:
        pass

    with get_readonly_connection(target_db) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, description, default_params, created_at, updated_at
            FROM sim_scripts
            ORDER BY id;
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "default_params": json.loads(r["default_params"] or "{}"),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]


def switch_simulation_db(new_path_str: str) -> Dict[str, Any]:
    """Validate target database path, re-initialize if needed, and update symlink and global pointers."""
    target_path = Path(new_path_str).expanduser().resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize schema on target database
    init_sim_db(target_path)

    # Update active DB path in sim_telemetry
    sim_telemetry.SIM_DB_PATH = target_path

    # Mirror to void.db symlink in project root
    void_symlink = Path("/home/wes/projects/LLM_Memory/void.db")
    try:
        if void_symlink.exists() or void_symlink.is_symlink():
            void_symlink.unlink()
        void_symlink.symlink_to(target_path)
    except OSError:
        pass

    # Verify tables
    conn = sqlite3.connect(target_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name;")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()

    return {
        "status": "success",
        "active_db": str(target_path),
        "tables": tables,
    }


def run_simulation(
    script_id: Optional[str] = None,
    inline_script: Optional[str] = None,
    steps: int = 1,
    params: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute a simulation routine headlessly and append new sequential frames to sim_telemetry."""
    target_db = get_active_db_path(db_path)
    init_sim_db(target_db)

    # 1. State Injection: Read current head row
    conn = sqlite3.connect(target_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT step, grid_width, grid_height, cells, entities, events FROM sim_telemetry ORDER BY step DESC LIMIT 1;")
    head_row = cur.fetchone()
    conn.close()

    if not head_row:
        raise RuntimeError("sim_telemetry is empty. No head state available for simulation.")

    state = {
        "step": head_row["step"],
        "width": head_row["grid_width"],
        "height": head_row["grid_height"],
        "cells": json.loads(head_row["cells"]),
        "entities": json.loads(head_row["entities"]),
        "events": json.loads(head_row["events"]),
    }

    # 2. Resolve script body and parameters
    merged_params: Dict[str, Any] = {}
    if script_id:
        script_record = get_script(script_id, db_path=target_db)
        if not script_record:
            raise ValueError(f"Script with id '{script_id}' not found.")
        merged_params.update(script_record["default_params"])
        code_to_run = script_record["script_body"]
    elif inline_script:
        code_to_run = inline_script
    else:
        raise ValueError("Either script_id or inline_script must be provided.")

    if params:
        merged_params.update(params)
    merged_params["steps"] = steps
    merged_params["steps_to_run"] = steps

    # 3. Context Sandbox & emit_step helper
    steps_emitted = 0

    def emit_step(
        entities: Optional[List[Dict[str, Any]]] = None,
        cells: Optional[List[Dict[str, Any]]] = None,
        events: Optional[List[Dict[str, Any]]] = None,
        *args,
        **kwargs,
    ) -> int:
        nonlocal steps_emitted, state

        target_entities = entities
        if target_entities is None:
            if args:
                target_entities = args[0]
            elif "new_entities" in kwargs:
                target_entities = kwargs["new_entities"]
            elif "new_state" in kwargs and isinstance(kwargs["new_state"], dict):
                target_entities = kwargs["new_state"].get("entities")
            else:
                target_entities = state["entities"]

        target_cells = cells
        if target_cells is None:
            if len(args) > 1:
                target_cells = args[1]
            elif "new_cells" in kwargs:
                target_cells = kwargs["new_cells"]
            else:
                target_cells = state["cells"]

        target_events = events
        if target_events is None:
            if len(args) > 2:
                target_events = args[2]
            elif "new_events" in kwargs:
                target_events = kwargs["new_events"]
            else:
                target_events = []

        next_step = state["step"] + 1

        record_telemetry_frame(
            step=next_step,
            grid_width=state["width"],
            grid_height=state["height"],
            cells=target_cells,
            entities=target_entities,
            events=target_events,
            db_path=target_db,
        )

        state["step"] = next_step
        state["entities"] = target_entities
        state["cells"] = target_cells
        state["events"] = target_events
        steps_emitted += 1
        return next_step

    # Sandbox environment
    safe_globals = {
        "__builtins__": {
            "abs": abs,
            "all": all,
            "any": any,
            "bin": bin,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "format": format,
            "getattr": getattr,
            "hasattr": hasattr,
            "hex": hex,
            "int": int,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "iter": iter,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "next": next,
            "oct": oct,
            "ord": ord,
            "pow": pow,
            "print": print,
            "range": range,
            "reversed": reversed,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "True": True,
            "False": False,
            "None": None,
        },
        "math": math,
        "random": random,
        "json": json,
        "datetime": datetime,
        "time": time,
    }

    local_ns: Dict[str, Any] = {
        "state": state,
        "params": merged_params,
        "emit_step": emit_step,
        "steps": steps,
        "steps_to_run": steps,
    }

    compiled = compile(code_to_run, "<sim_script>", "exec")
    exec(compiled, safe_globals, local_ns)

    # 4. Check for callable step function or loop execution
    if "step" in local_ns and callable(local_ns["step"]):
        step_fn = local_ns["step"]
        sig = inspect.signature(step_fn)
        num_args = len(sig.parameters)

        for _ in range(steps):
            if num_args >= 3:
                step_fn(state, merged_params, emit_step)
            elif num_args == 2:
                step_fn(state, merged_params)
            elif num_args == 1:
                step_fn(state)
            else:
                step_fn()
    else:
        # If top-level code was executed, check if more iterations are requested
        if steps_emitted == 1 and steps > 1:
            for i in range(1, steps):
                local_ns["iteration"] = i
                exec(compiled, safe_globals, local_ns)
        elif steps_emitted == 0:
            for i in range(steps):
                local_ns["iteration"] = i
                exec(compiled, safe_globals, local_ns)

    return {
        "status": "success",
        "steps_executed": steps_emitted,
        "head_step": state["step"],
    }
