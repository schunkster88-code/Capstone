from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.sim_telemetry import get_telemetry_frame
from core.sim_runner import (
    save_script,
    get_script,
    list_scripts,
    run_simulation,
    switch_simulation_db,
)

router = APIRouter(prefix="/api/sim", tags=["simulation"])


class ScriptSaveRequest(BaseModel):
    id: str = Field(..., description="Unique alphanumeric identifier for the script")
    name: str = Field(..., description="Human-readable title")
    description: Optional[str] = Field("", description="Functional summary")
    script_body: str = Field(..., description="Executable Python script body")
    default_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Default parameters")


class ScriptRunRequest(BaseModel):
    script_id: Optional[str] = Field(None, description="Registered script identifier")
    inline_script: Optional[str] = Field(None, description="Inline Python routine to execute")
    steps: int = Field(1, ge=1, description="Number of steps to advance")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Runtime parameter overrides")


class SwitchDbRequest(BaseModel):
    db_path: str = Field(..., description="Filesystem path to the target SQLite database")


@router.get("/telemetry")
def get_telemetry(
    step: Optional[int] = Query(None, description="Specific step to fetch"),
    latest: Optional[bool] = Query(False, description="Whether to fetch head frame"),
):
    """Fetch simulation state frame in strictly read-only mode."""
    frame = get_telemetry_frame(step=step, latest=bool(latest))
    if not frame:
        target = "latest" if latest or step is None else f"step {step}"
        raise HTTPException(status_code=404, detail=f"Telemetry frame not found for {target}")
    return frame


@router.get("/scripts")
def get_scripts() -> List[Dict[str, Any]]:
    """List all registered simulation scripts."""
    try:
        return list_scripts()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/script/{script_id}")
def get_single_script(script_id: str) -> Dict[str, Any]:
    """Retrieve full code and metadata of a registered script."""
    script = get_script(script_id)
    if not script:
        raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found.")
    return script


@router.post("/script/save")
def handle_save_script(req: ScriptSaveRequest) -> Dict[str, Any]:
    """Save or update a simulation routine in sim_scripts."""
    try:
        return save_script(
            script_id=req.id,
            name=req.name,
            description=req.description or "",
            script_body=req.script_body,
            default_params=req.default_params or {},
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/script/run")
def handle_run_script(req: ScriptRunRequest) -> Dict[str, Any]:
    """Execute a registered script or inline Python routine across N simulation steps."""
    try:
        return run_simulation(
            script_id=req.script_id,
            inline_script=req.inline_script,
            steps=req.steps,
            params=req.params,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/switch_db")
def handle_switch_db(req: SwitchDbRequest) -> Dict[str, Any]:
    """Repoint the active simulation database, verify schema, and update harness symlink."""
    try:
        return switch_simulation_db(req.db_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
