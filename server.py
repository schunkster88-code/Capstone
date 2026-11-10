from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from core.void_engine import init_empty_db, execute_raw, inspect_schema
from core.sim_telemetry import init_sim_db
from core.project_manager import init_default_project
from api.routes.workbench import router as workbench_router
from api.routes.sim import router as sim_router
from api.routes.projects import router as projects_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_default_project()
    init_empty_db()
    init_sim_db()
    yield


app = FastAPI(title="Void Substrate Raw IO", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(workbench_router)
app.include_router(sim_router)
app.include_router(projects_router)


class CommandPayload(BaseModel):
    sql: str


@app.get("/")
async def get_root():
    return FileResponse("static/index.html")


@app.get("/sim-viewer")
async def get_sim_viewer():
    return FileResponse("static/sim_viewer.html")


@app.get("/api/schema")
async def get_schema():
    try:
        schema = inspect_schema()
        return {"status": "success", "schema": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/execute")
async def run_command(payload: CommandPayload):
    try:
        result = execute_raw(payload.sql)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

