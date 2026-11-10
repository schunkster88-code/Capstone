from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.project_manager import (
    list_projects,
    create_project,
    activate_project,
    get_active_project_name,
    get_project_dir,
    get_project_db_path,
    get_project_scripts_dir,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., description="Unique alphanumeric identifier for the project")
    description: Optional[str] = Field("", description="Project description and scope")
    template: Optional[str] = Field("sim", description="Starter template ('sim', 'empty')")
    compress: Optional[bool] = Field(False, description="Whether to compress/minify exported script bodies")


class ProjectActivateRequest(BaseModel):
    name: str = Field(..., description="Name of the project to activate")


@router.get("")
def handle_list_projects(include_metadata: bool = True) -> List[Dict[str, Any]]:
    """List all project workspaces with metadata, database size, and script count."""
    try:
        return list_projects(include_metadata=include_metadata)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/active")
def handle_get_active_project(include_metadata: bool = True) -> Dict[str, Any]:
    """Retrieve metadata and status for the currently active project."""
    active_name = get_active_project_name()
    projects = list_projects(include_metadata=include_metadata)
    active_info = next((p for p in projects if p["name"] == active_name), None)
    if not active_info:
        active_info = {
            "name": active_name,
            "is_active": True,
            "db_path": str(get_project_db_path(active_name)),
        }
    return active_info


@router.post("/create")
def handle_create_project(req: ProjectCreateRequest) -> Dict[str, Any]:
    """Create a new self-contained project folder with isolated database and scripts."""
    try:
        return create_project(
            name=req.name,
            description=req.description or "",
            template=req.template or "sim",
            compress=bool(req.compress),
        )
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err)) from val_err
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/activate")
def handle_activate_project(req: ProjectActivateRequest) -> Dict[str, Any]:
    """Switch the active project, symlinks, and SQLite telemetry connection."""
    try:
        return activate_project(req.name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{name}")
def handle_get_project(name: str, include_metadata: bool = True) -> Dict[str, Any]:
    """Get metadata for a specific project workspace."""
    projects = list_projects(include_metadata=include_metadata)
    proj = next((p for p in projects if p["name"] == name), None)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found.")
    return proj

