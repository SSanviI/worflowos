# workflowos/backend/api/agent.py
"""API endpoints for controlling the Desktop Activity Agent."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from ...activity_agent.manager import agent_manager

router = APIRouter()


class StartAgentRequest(BaseModel):
    monitored_paths: Optional[List[str]] = None


class AddPathRequest(BaseModel):
    path: str


@router.post("/start")
def start_agent(payload: Optional[StartAgentRequest] = None):
    """Start the background Windows activity observer."""
    paths = payload.monitored_paths if payload else None
    return agent_manager.start(paths)


@router.post("/stop")
def stop_agent():
    """Stop the background Windows activity observer."""
    return agent_manager.stop()


@router.get("/status")
def get_agent_status():
    """Get current observation status and monitored directories."""
    return agent_manager.get_status()


@router.post("/paths")
def add_monitored_path(payload: AddPathRequest):
    """Add a directory to the live watcher."""
    agent_manager.add_path(payload.path)
    return agent_manager.get_status()
