# workflowos/backend/main.py
"""WorkFlowOS FastAPI Application Entry Point."""

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import BASE_DIR
from .database import engine, Base
from .api import events, agent, workflows, executions, learning, demo, integrations

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="WorkFlowOS",
    description="AI-Powered OS-Level Workflow Automation",
    version="2.0.0",
)

# Enable CORS for local development & browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root redirect to frontend dashboard
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")

# Register API Routers
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.include_router(executions.router, prefix="/api/executions", tags=["executions"])
app.include_router(learning.router, prefix="/api/learning", tags=["learning"])
app.include_router(demo.router, prefix="/api/demo", tags=["demo"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])

# Mount static frontend
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": "WorkFlowOS", "version": "2.0.0"}


if __name__ == "__main__":
    uvicorn.run("workflowos.backend.main:app", host="0.0.0.0", port=8000, reload=False)
