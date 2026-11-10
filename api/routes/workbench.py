from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from core.workbench_substrate import CognitiveWorkbench

router = APIRouter(prefix="/api/workbench", tags=["cognitive_workbench"])

_workbench_instance: Optional[CognitiveWorkbench] = None


def get_workbench() -> CognitiveWorkbench:
    global _workbench_instance
    if _workbench_instance is None:
        _workbench_instance = CognitiveWorkbench(db_path="connectome.db", max_active_nodes=30)
    return _workbench_instance


class SavepointRequest(BaseModel):
    name: str = Field(..., description="Alphanumeric savepoint branch identifier")
    action: str = Field(..., pattern="^(branch|rollback|release)$")


class MutateRequest(BaseModel):
    sql_batch: str = Field(..., description="DDL/DML batch without triggers")


class LensRequest(BaseModel):
    origin_key: Optional[str] = None
    custom_select: Optional[str] = None


class CrystallizeRequest(BaseModel):
    axiom_id: str
    statement: str
    crystallized_from: str
    prune_keys: List[str] = Field(default_factory=list)
    epoch_number: int = 3


@router.post("/savepoint")
def handle_savepoint(req: SavepointRequest, wb: CognitiveWorkbench = Depends(get_workbench)) -> Dict[str, str]:
    try:
        if req.action == "branch":
            sp = wb.branch_savepoint(req.name)
        elif req.action == "rollback":
            sp = wb.rollback_savepoint(req.name)
        else:
            sp = wb.release_savepoint(req.name)
        return {"status": "ok", "savepoint": sp, "action": req.action}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/mutate")
def handle_mutate(req: MutateRequest, wb: CognitiveWorkbench = Depends(get_workbench)) -> Dict[str, Any]:
    try:
        cap_status = wb.mutate_substrate(req.sql_batch)
        return {"status": "ok", "memory_cap": cap_status}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/lens")
def handle_lens(req: LensRequest, wb: CognitiveWorkbench = Depends(get_workbench)) -> Dict[str, Any]:
    try:
        rows = wb.query_lens(origin_key=req.origin_key, custom_select=req.custom_select)
        return {"count": len(rows), "rows": rows}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/crystallize")
def handle_crystallize(req: CrystallizeRequest, wb: CognitiveWorkbench = Depends(get_workbench)) -> Dict[str, Any]:
    try:
        return wb.crystallize_invariant(
            axiom_id=req.axiom_id,
            statement=req.statement,
            crystallized_from=req.crystallized_from,
            prune_keys=req.prune_keys,
            epoch_number=req.epoch_number,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sleep_consolidate")
def handle_sleep_consolidation(
    decay_factor: float = 0.92,
    wb: CognitiveWorkbench = Depends(get_workbench),
) -> Dict[str, Any]:
    """Batched offline sleep cycle: attenuate peripheral weights and enforce LRU working memory cap."""
    wb.conn.execute(
        """
        UPDATE memory_edges
        SET weight = ROUND(weight * ?, 3)
        WHERE weight < 0.95
          AND source_key NOT LIKE 'landmark%';
        """,
        (decay_factor,),
    )
    wb.conn.commit()
    cap_state = wb.enforce_working_memory_cap()
    return {"status": "consolidated", "decay_factor": decay_factor, **cap_state}

