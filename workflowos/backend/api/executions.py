# workflowos/backend/api/executions.py
"""API endpoints for Workflow Execution History and Step Logs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from .. import database
from ..models import workflow_execution, workflow

router = APIRouter()


@router.get("/", response_model=List[Dict[str, Any]])
def list_executions(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    """List execution history ordered from newest to oldest."""
    execs = (
        db.query(workflow_execution.WorkflowExecution)
        .order_by(workflow_execution.WorkflowExecution.start_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    result = []
    for e in execs:
        wf = db.query(workflow.Workflow).filter(workflow.Workflow.id == e.workflow_id).first()
        result.append({
            "id": e.id,
            "execution_id": e.execution_id,
            "workflow_id": e.workflow_id,
            "workflow_name": wf.name if wf else "Unknown",
            "status": e.status,
            "start_time": e.start_time,
            "finish_time": e.finish_time,
            "result": e.result,
            "error": e.error,
        })
    return result


@router.get("/{execution_id}", response_model=Dict[str, Any])
def get_execution(execution_id: str, db: Session = Depends(database.get_db)):
    """Get single execution record by execution_id string."""
    exec_rec = (
        db.query(workflow_execution.WorkflowExecution)
        .filter(workflow_execution.WorkflowExecution.execution_id == execution_id)
        .first()
    )
    if not exec_rec:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found.")
    wf = db.query(workflow.Workflow).filter(workflow.Workflow.id == exec_rec.workflow_id).first()
    return {
        "id": exec_rec.id,
        "execution_id": exec_rec.execution_id,
        "workflow_id": exec_rec.workflow_id,
        "workflow_name": wf.name if wf else "Unknown",
        "status": exec_rec.status,
        "start_time": exec_rec.start_time,
        "finish_time": exec_rec.finish_time,
        "result": exec_rec.result,
        "error": exec_rec.error,
    }


@router.get("/{execution_id}/steps", response_model=List[Dict[str, Any]])
def get_steps(execution_id: str, db: Session = Depends(database.get_db)):
    """Retrieve detailed step logs for a given execution."""
    exec_rec = (
        db.query(workflow_execution.WorkflowExecution)
        .filter(workflow_execution.WorkflowExecution.execution_id == execution_id)
        .first()
    )
    if not exec_rec:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found.")

    steps = (
        db.query(workflow_execution.ExecutionStep)
        .filter(workflow_execution.ExecutionStep.execution_id == exec_rec.id)
        .order_by(workflow_execution.ExecutionStep.id.asc())
        .all()
    )
    return [
        {
            "id": s.id,
            "action_id": s.action_id,
            "connector": s.connector or (s.result.get("connector") if isinstance(s.result, dict) else "Adapter"),
            "mode": s.mode or (s.result.get("mode") if isinstance(s.result, dict) else "REAL_API"),
            "status": s.status,
            "start_time": s.start_time,
            "finish_time": s.finish_time,
            "error": s.error,
            "result": s.result,
        }
        for s in steps
    ]
