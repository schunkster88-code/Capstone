# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

from pathlib import Path
import json
import sqlite3
from typing import Any, Dict, List, Optional

DB_PATH = Path("void.db")


def _sim_run_fn(sid: str, steps: int = 1, db_path: Optional[Path] = None) -> str:
    from core.sim_runner import run_simulation
    target = DB_PATH if db_path is None else db_path
    res = run_simulation(script_id=str(sid), steps=int(steps), db_path=target)
    return json.dumps(res)


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = DB_PATH if db_path is None else db_path
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.create_function("sim_run", 1, lambda sid: _sim_run_fn(sid, 1, target_path))
    conn.create_function("sim_run", 2, lambda sid, steps: _sim_run_fn(sid, steps, target_path))
    return conn


def init_empty_db(db_path: Optional[Path] = None) -> None:
    target_path = DB_PATH if db_path is None else db_path
    with get_connection(target_path):
        pass


def inspect_schema(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    target_path = DB_PATH if db_path is None else db_path
    with get_connection(target_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name;"
        )
        return [dict(r) for r in cur.fetchall()]


def handle_create_project_cmd(stmt: str, target_path: Optional[Path] = None) -> Dict[str, Any]:
    from core.project_manager import create_project, activate_project
    parts = stmt.rstrip(";").split()
    proj_name = parts[2].strip("'\"")
    desc = ""
    upper_stmt = stmt.upper()
    if "DESCRIPTION" in upper_stmt:
        desc_part = stmt.split("DESCRIPTION", 1)[1].strip().strip("'\"")
        desc = desc_part
    create_project(name=proj_name, description=desc)
    activated = activate_project(proj_name)
    return {
        "type": "project_create",
        "status": "success",
        "message": f"Successfully created and activated project '{proj_name}'",
        "project": activated,
    }


def handle_activate_project_cmd(stmt: str, target_path: Optional[Path] = None) -> Dict[str, Any]:
    from core.project_manager import activate_project
    parts = stmt.rstrip(";").split()
    proj_name = parts[2].strip("'\"")
    activated = activate_project(proj_name)
    return {
        "type": "project_activate",
        "status": "success",
        "message": f"Successfully activated project '{proj_name}'",
        "project": activated,
    }


def handle_list_projects_cmd(stmt: str = "", target_path: Optional[Path] = None) -> Dict[str, Any]:
    from core.project_manager import list_projects
    projs = list_projects(include_metadata=True)
    return {
        "type": "query",
        "count": len(projs),
        "rows": projs,
    }


def handle_save_script_cmd(stmt: str, target_path: Optional[Path] = None) -> Dict[str, Any]:
    from core.sim_runner import save_script
    lines = stmt.splitlines()
    first_line = lines[0].strip()
    parts = first_line.split()
    script_id = parts[2].strip("'\"")
    name = script_id.replace("_", " ").title()
    desc = ""
    code_lines = []
    is_code = False
    for line in lines[1:]:
        line_str = line.strip()
        if not is_code and line_str.upper().startswith("NAME:"):
            name = line_str.split(":", 1)[1].strip().strip("'\"")
        elif not is_code and (line_str.upper().startswith("DESC:") or line_str.upper().startswith("DESCRIPTION:")):
            desc = line_str.split(":", 1)[1].strip().strip("'\"")
        elif not is_code and (line_str.upper().startswith("CODE:") or line_str.startswith("```")):
            is_code = True
        else:
            code_lines.append(line)
    script_body = "\n".join(code_lines).strip()
    if script_body.startswith("```python"):
        script_body = script_body[len("```python"):].strip()
    if script_body.startswith("```"):
        script_body = script_body[3:].strip()
    if script_body.endswith("```"):
        script_body = script_body[:-3].strip()
    res = save_script(script_id=script_id, name=name, description=desc, script_body=script_body, db_path=target_path)
    return {
        "type": "script_save",
        "status": "success",
        "message": f"Successfully registered and bundled script '{script_id}'",
        "script": res,
    }


def handle_list_scripts_cmd(stmt: str = "", target_path: Optional[Path] = None) -> Dict[str, Any]:
    from core.sim_runner import list_scripts
    scripts = list_scripts(db_path=target_path)
    return {
        "type": "query",
        "count": len(scripts),
        "rows": scripts,
    }


def handle_run_script_cmd(stmt: str, target_path: Optional[Path] = None) -> Dict[str, Any]:
    tokens = stmt.rstrip(";").split()
    script_id = None
    steps = 1
    if tokens[0].upper() in ("RUN", "SIM") and len(tokens) >= 2:
        if tokens[1].upper() in ("SCRIPT", "RUN"):
            if len(tokens) >= 3:
                script_id = tokens[2].strip("'\"")
                if len(tokens) >= 5 and tokens[3].upper() == "STEPS":
                    try:
                        steps = int(tokens[4])
                    except ValueError:
                        pass
                elif len(tokens) >= 4:
                    try:
                        steps = int(tokens[3])
                    except ValueError:
                        pass
        else:
            script_id = tokens[1].strip("'\"")
            if len(tokens) >= 4 and tokens[2].upper() == "STEPS":
                try:
                    steps = int(tokens[3])
                except ValueError:
                    pass
            elif len(tokens) >= 3:
                try:
                    steps = int(tokens[2])
                except ValueError:
                    pass

    if script_id:
        from core.sim_runner import run_simulation
        result = run_simulation(script_id=script_id, steps=steps, db_path=target_path)
        return {"type": "sim_runner", **result}
    return {"type": "error", "message": f"Invalid run command: {stmt}"}


CONSOLE_COMMAND_HANDLERS = {
    "CREATE PROJECT": handle_create_project_cmd,
    "PROJECT CREATE": handle_create_project_cmd,
    "USE PROJECT": handle_activate_project_cmd,
    "ACTIVATE PROJECT": handle_activate_project_cmd,
    "SWITCH PROJECT": handle_activate_project_cmd,
    "LIST PROJECTS": handle_list_projects_cmd,
    "SHOW PROJECTS": handle_list_projects_cmd,
    "SAVE SCRIPT": handle_save_script_cmd,
    "REGISTER SCRIPT": handle_save_script_cmd,
    "LIST SCRIPTS": handle_list_scripts_cmd,
    "SHOW SCRIPTS": handle_list_scripts_cmd,
    "RUN SCRIPT": handle_run_script_cmd,
    "SIM RUN": handle_run_script_cmd,
    "RUN": handle_run_script_cmd,
}


def dispatch_console_command(stmt: str, target_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    upper_stmt = stmt.upper().rstrip(";")
    for cmd_prefix, handler in CONSOLE_COMMAND_HANDLERS.items():
        if upper_stmt == cmd_prefix or upper_stmt.startswith(cmd_prefix + " "):
            return handler(stmt, target_path=target_path)
    return None


def execute_raw(sql: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    target_path = DB_PATH if db_path is None else db_path
    stmt = sql.strip()

    # 1. Intercept JSON payloads pasted directly into the console
    if stmt.startswith("{") and stmt.endswith("}"):
        try:
            data = json.loads(stmt)
            if isinstance(data, dict):
                # A. Project creation / activation payload
                if "name" in data and ("template" in data or "description" in data or "project" in data):
                    from core.project_manager import create_project, activate_project
                    proj_name = data.get("name") or data.get("project")
                    desc = data.get("description", "")
                    tmpl = data.get("template", "sim")
                    create_project(name=proj_name, description=desc, template=tmpl)
                    activated = activate_project(proj_name)
                    return {
                        "type": "project_create",
                        "status": "success",
                        "message": f"Successfully created and activated project '{proj_name}'",
                        "project": activated,
                    }
                # B. Script save payload
                if ("script_body" in data or "code" in data) and ("id" in data or "name" in data):
                    from core.sim_runner import save_script
                    sid = data.get("id") or data.get("name", "").lower().replace(" ", "_")
                    sname = data.get("name") or sid.replace("_", " ").title()
                    sdesc = data.get("description", "")
                    sbody = data.get("script_body") or data.get("code")
                    sparams = data.get("default_params") or data.get("params") or {}
                    res = save_script(script_id=sid, name=sname, description=sdesc, script_body=sbody, default_params=sparams, db_path=target_path)
                    return {
                        "type": "script_save",
                        "status": "success",
                        "message": f"Successfully saved and bundled script '{sid}'",
                        "script": res,
                    }
                # C. Script run payload
                if "script_id" in data or ("steps" in data and ("script" in data or "run" in data)):
                    from core.sim_runner import run_simulation
                    sid = data.get("script_id") or data.get("script") or data.get("run")
                    n_steps = int(data.get("steps", 1))
                    params = data.get("params") or {}
                    res = run_simulation(script_id=sid, steps=n_steps, params=params, db_path=target_path)
                    return {"type": "sim_runner", **res}
        except json.JSONDecodeError:
            pass

    # 2. Intercept console commands via dynamic dispatch
    upper_stmt = stmt.upper().rstrip(";")
    if upper_stmt in ("LIST PROJECTS", "SHOW PROJECTS"):
        from core.project_manager import list_projects
        projs = list_projects(include_metadata=True)
        return {
            "type": "query",
            "count": len(projs),
            "rows": projs,
        }

    cmd_res = dispatch_console_command(stmt, target_path=target_path)
    if cmd_res is not None:
        return cmd_res

    with get_connection(target_path) as conn:
        cur = conn.cursor()
        # Handle multi-statement scripts (e.g. batch CREATE TABLE or bulk INSERT)
        if ";" in stmt[:-1]:
            cur.executescript(stmt)
            conn.commit()
            if "sim_scripts" in stmt.lower():
                try:
                    from core.project_manager import sync_db_scripts_to_disk
                    sync_db_scripts_to_disk(target_path)
                except Exception:
                    pass
            return {"type": "script", "status": "executed", "statement": stmt}

        cur.execute(stmt)
        if cur.description:
            rows = [dict(r) for r in cur.fetchall()]
            return {"type": "query", "count": len(rows), "rows": rows}

        conn.commit()
        if "sim_scripts" in stmt.lower():
            try:
                from core.project_manager import sync_db_scripts_to_disk
                sync_db_scripts_to_disk(target_path)
            except Exception:
                pass
        return {
            "type": "mutation",
            "affected_rows": cur.rowcount,
            "lastrowid": cur.lastrowid,
            "status": "success",
        }
