# Copyright (c) 2026 Wesley A. Schunk (ZeroSelf, LLC)
# SPDX-License-Identifier: AGPL-3.0-only
# Commercial licenses & inquiries: schunkster88@gmail.com
# See LICENSE and README.md for Dual-License terms.

from pathlib import Path
from datetime import datetime
import json
import re
import shutil
import sqlite3
from typing import Any, Dict, List, Optional

import core.sim_telemetry as sim_telemetry
import core.void_engine as void_engine
from core.sim_telemetry import init_sim_db, get_readonly_connection

PROJECTS_DIR = Path("projects").resolve()
ACTIVE_PROJECT_FILE = PROJECTS_DIR / ".active_project"


def get_projects_dir() -> Path:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECTS_DIR


def get_active_project_name() -> str:
    """Return the name of the currently active project."""
    if ACTIVE_PROJECT_FILE.exists():
        try:
            name = ACTIVE_PROJECT_FILE.read_text(encoding="utf-8").strip()
            if name:
                return name
        except OSError:
            pass
    return "default"


def get_project_dir(name: str) -> Path:
    """Get root directory path for a project."""
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip()) or "default"
    return get_projects_dir() / safe_name


def get_project_db_path(name: str) -> Path:
    """Get the SQLite database path for a project."""
    return get_project_dir(name) / "project.db"


def get_project_scripts_dir(name: str) -> Path:
    """Get the scripts directory path for a project."""
    scripts_dir = get_project_dir(name) / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    return scripts_dir


def get_active_project_db_path() -> Path:
    return get_project_db_path(get_active_project_name())


def get_active_project_scripts_dir() -> Path:
    return get_project_scripts_dir(get_active_project_name())


def export_script_to_disk(
    script_id: str,
    name: str,
    description: str,
    script_body: str,
    default_params: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None,
    compress: bool = False,
) -> Path:
    """Export a simulation script to an isolated .py file bundled in the project's scripts folder."""
    target_db = sim_telemetry.SIM_DB_PATH if db_path is None else Path(db_path).resolve()
    
    # If target_db is inside a project directory, bundle in its scripts/ folder
    if target_db.parent.parent == PROJECTS_DIR:
        scripts_dir = target_db.parent / "scripts"
    else:
        scripts_dir = target_db.parent / "scripts"

    scripts_dir.mkdir(parents=True, exist_ok=True)
    file_path = scripts_dir / f"{script_id}.py"

    params_json = json.dumps(default_params or {}, indent=2)
    header = (
        f'"""\n'
        f"id: {script_id}\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"default_params: {params_json}\n"
        f'"""\n\n'
    )
    body_text = script_body.strip()
    if compress:
        body_text = "\n".join(line.strip() for line in body_text.splitlines() if line.strip())
    file_path.write_text(header + body_text + "\n", encoding="utf-8")
    return file_path


def parse_script_file(file_path: Path) -> Dict[str, Any]:
    """Parse a bundled Python script file and extract metadata and executable body."""
    content = file_path.read_text(encoding="utf-8")
    script_id = file_path.stem
    name = script_id.replace("_", " ").title()
    description = "Bundled Python simulation routine"
    default_params = {}
    body = content

    docstring_match = re.match(r'^\s*"""(.*?)"""(.*)', content, re.DOTALL)
    if docstring_match:
        header = docstring_match.group(1)
        body = docstring_match.group(2).strip()

        # Parse simple YAML-like key-value pairs from header
        id_m = re.search(r"^id:\s*(.+)$", header, re.MULTILINE)
        if id_m:
            script_id = id_m.group(1).strip()
        name_m = re.search(r"^name:\s*(.+)$", header, re.MULTILINE)
        if name_m:
            name = name_m.group(1).strip()
        desc_m = re.search(r"^description:\s*(.+)$", header, re.MULTILINE)
        if desc_m:
            description = desc_m.group(1).strip()
        params_m = re.search(r"^default_params:\s*(\{.*\}|\[.*\])", header, re.MULTILINE | re.DOTALL)
        if params_m:
            try:
                default_params = json.loads(params_m.group(1).strip())
            except Exception:
                pass

    return {
        "id": script_id,
        "name": name,
        "description": description,
        "script_body": body,
        "default_params": default_params,
    }


def sync_scripts_from_disk_to_db(db_path: Optional[Path] = None) -> int:
    """Sync any Python files from the scripts folder into the target sim_scripts SQLite table."""
    target_db = sim_telemetry.SIM_DB_PATH if db_path is None else Path(db_path).resolve()
    if not target_db.exists():
        return 0

    if target_db.parent.parent == PROJECTS_DIR:
        scripts_dir = target_db.parent / "scripts"
    else:
        scripts_dir = target_db.parent / "scripts"

    if not scripts_dir.exists():
        return 0

    synced_count = 0
    py_files = list(scripts_dir.glob("*.py"))
    if not py_files:
        return 0

    init_sim_db(target_db)
    with sqlite3.connect(target_db) as conn:
        for py_path in py_files:
            parsed = parse_script_file(py_path)
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
                (
                    parsed["id"],
                    parsed["name"],
                    parsed["description"],
                    parsed["script_body"],
                    json.dumps(parsed["default_params"]),
                ),
            )
            synced_count += 1
        conn.commit()

    return synced_count


def sync_db_scripts_to_disk(
    db_path: Optional[Path] = None,
    compress: bool = False,
) -> int:
    """Export all scripts from the database to individual .py files in the project's scripts folder."""
    target_db = sim_telemetry.SIM_DB_PATH if db_path is None else Path(db_path).resolve()
    if not target_db.exists():
        return 0

    try:
        with get_readonly_connection(target_db) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, description, script_body, default_params FROM sim_scripts;")
            rows = cur.fetchall()
    except Exception:
        return 0

    exported = 0
    for r in rows:
        params = {}
        try:
            params = json.loads(r["default_params"] or "{}")
        except Exception:
            pass
        export_script_to_disk(
            script_id=r["id"],
            name=r["name"],
            description=r["description"] or "",
            script_body=r["script_body"],
            default_params=params,
            db_path=target_db,
            compress=compress,
        )
        exported += 1
    return exported


def create_project(
    name: str,
    description: str = "",
    template: str = "sim",
    compress: bool = False,
) -> Dict[str, Any]:
    """Create a new self-contained project folder with its own SQLite database and scripts directory."""
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip())
    if not safe_name:
        raise ValueError("Project name must contain valid alphanumeric characters, hyphens, or underscores.")

    proj_dir = get_project_dir(safe_name)
    proj_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = get_project_scripts_dir(safe_name)
    db_path = get_project_db_path(safe_name)

    # Initialize SQLite database
    init_sim_db(db_path, force_seed=(template == "sim"))

    # Write project metadata
    meta = {
        "name": safe_name,
        "description": description or f"Project {safe_name}",
        "template": template,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    (proj_dir / "project.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Export any seeded scripts into scripts/
    sync_db_scripts_to_disk(db_path, compress=compress)

    return {
        "status": "success",
        "name": safe_name,
        "dir": str(proj_dir),
        "db_path": str(db_path),
        "scripts_dir": str(scripts_dir),
        "template": template,
    }


def activate_project(name: str) -> Dict[str, Any]:
    """Switch the global active project, repointing SQLite symlinks and telemetry pointers."""
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip()) or "default"
    proj_dir = get_project_dir(safe_name)
    if not proj_dir.exists():
        create_project(safe_name)

    db_path = get_project_db_path(safe_name)
    init_sim_db(db_path)

    # Update active project tracker
    ACTIVE_PROJECT_FILE.write_text(safe_name, encoding="utf-8")

    # Update in-memory pointers
    sim_telemetry.SIM_DB_PATH = db_path
    void_engine.DB_PATH = db_path

    # Update root symlinks so legacy paths hit the active project
    workspace_root = Path("/home/wes/projects/LLM_Memory").resolve()
    void_symlink = workspace_root / "void.db"
    try:
        if void_symlink.exists() or void_symlink.is_symlink():
            void_symlink.unlink()
        void_symlink.symlink_to(db_path)
    except OSError:
        pass

    # Ensure scripts are bidirectionally synchronized
    sync_scripts_from_disk_to_db(db_path)
    sync_db_scripts_to_disk(db_path)

    # Gather table names
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name;")
        tables = [r[0] for r in cur.fetchall()]

    scripts_count = len(list(get_project_scripts_dir(safe_name).glob("*.py")))

    return {
        "status": "success",
        "active_project": safe_name,
        "db_path": str(db_path),
        "scripts_count": scripts_count,
        "tables": tables,
    }


def list_projects(include_metadata: bool = True) -> List[Dict[str, Any]]:
    """List all project folders with metadata, database size, and script counts."""
    init_default_project()
    p_dir = get_projects_dir()
    active_name = get_active_project_name()
    projects = []

    for entry in sorted(p_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        meta_file = entry / "project.json"
        meta = {}
        if include_metadata and meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        db_path = entry / "project.db"
        db_size_bytes = db_path.stat().st_size if db_path.exists() else 0
        scripts_dir = entry / "scripts"
        scripts_count = len(list(scripts_dir.glob("*.py"))) if scripts_dir.exists() else 0

        projects.append(
            {
                "name": entry.name,
                "description": meta.get("description", ""),
                "is_active": (entry.name == active_name),
                "db_path": str(db_path),
                "db_size_bytes": db_size_bytes,
                "scripts_count": scripts_count,
                "created_at": meta.get("created_at", ""),
                "updated_at": meta.get("updated_at", ""),
                "include_metadata": include_metadata,
            }
        )

    return projects


def init_default_project():
    """Ensure the 'default' project exists and migrate root sim.db if needed."""
    get_projects_dir()
    default_dir = get_project_dir("default")
    default_db = get_project_db_path("default")

    if not default_dir.exists() or not default_db.exists():
        default_dir.mkdir(parents=True, exist_ok=True)
        get_project_scripts_dir("default")

        root_sim = Path("sim.db").resolve()
        if root_sim.exists() and not root_sim.is_symlink():
            shutil.copy2(root_sim, default_db)
        else:
            init_sim_db(default_db, force_seed=True)

        meta = {
            "name": "default",
            "description": "Default simulation and memory workspace",
            "template": "sim",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        (default_dir / "project.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # Export any existing scripts from default_db into default/scripts/
        sync_db_scripts_to_disk(default_db)

    if not ACTIVE_PROJECT_FILE.exists():
        ACTIVE_PROJECT_FILE.write_text("default", encoding="utf-8")

