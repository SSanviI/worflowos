# workflowos/backend/api/workflows.py
"""API endpoints for Workflow discovery, inspection, approval, and execution."""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from .. import models, database
from ..schemas import workflow
from ...workflow_engine.discovery import discover_workflows, analyze_and_discover_workflows
from ...workflow_engine.generator import enrich_workflow
from ...workflow_engine.learning import FeedbackLearningEngine
from ...automation.engine import execute_workflow

router = APIRouter()


class ExecuteWorkflowRequest(BaseModel):
    context: Optional[Dict[str, Any]] = None


@router.post("/detect")
def detect_repetition(db: Session = Depends(database.get_db)):
    """Run genuine repetition detection algorithm over recorded activity events and generate candidate workflows.

    Returns full diagnostic breakdown:
    - events_observed: total events observed
    - sessions_analyzed: total sessions analyzed
    - occurrences: number of repeated occurrences detected
    - detected_pattern: sequence of canonical actions
    - confidence: float score [0.0 - 1.0]
    - repetition_reason: why the system considers it repetitive
    - candidate_workflows: list of generated workflows in PENDING_APPROVAL state
    """
    analysis = analyze_and_discover_workflows(db)
    candidates = analysis.get("candidate_workflows", [])
    for wf in candidates:
        if not wf.name or wf.name == "Discovered Candidate Workflow" or wf.name == "Detected Workflow":
            enrich_workflow(db, wf)

    return {
        "status": "repetition_detected" if candidates else "no_repetition_detected",
        "events_observed": analysis.get("events_observed", 0),
        "sessions_analyzed": analysis.get("sessions_analyzed", 0),
        "occurrences": analysis.get("occurrences", 0),
        "detected_pattern": analysis.get("detected_pattern", []),
        "confidence_score": analysis.get("confidence", 0.0),
        "confidence_percent": f"{analysis.get('confidence', 0.0) * 100:.1f}%",
        "repetition_reason": analysis.get("repetition_reason", ""),
        "workflows": [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "confidence": wf.confidence,
                "occurrences": wf.occurrences,
                "approved": wf.approved,
                "actions": wf.actions,
            }
            for wf in candidates
        ],
    }


@router.post("/discover")
def discover(db: Session = Depends(database.get_db)):
    """Run generic repetition detection and AI understanding over recorded sessions."""
    analysis = analyze_and_discover_workflows(db)
    candidates = analysis.get("candidate_workflows", [])
    for wf in candidates:
        if not wf.name or wf.name == "Discovered Candidate Workflow" or wf.name == "Detected Workflow":
            enrich_workflow(db, wf)
    return candidates


@router.get("/", response_model=List[workflow.WorkflowRead])
def list_workflows(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    """List all discovered workflows."""
    return db.query(models.workflow.Workflow).order_by(models.workflow.Workflow.id.desc()).offset(skip).limit(limit).all()


@router.get("/{workflow_id}", response_model=workflow.WorkflowRead)
def get_workflow(workflow_id: int, db: Session = Depends(database.get_db)):
    """Retrieve details of a specific workflow."""
    wf = db.query(models.workflow.Workflow).filter(models.workflow.Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow #{workflow_id} not found.")
    return wf


@router.post("/{workflow_id}/approve")
def approve_workflow(workflow_id: int, db: Session = Depends(database.get_db)):
    """Approve a discovered workflow candidate."""
    wf = db.query(models.workflow.Workflow).filter(models.workflow.Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow #{workflow_id} not found.")

    wf.approved = True
    wf.rejected = False
    db.commit()

    # Record approval feedback
    FeedbackLearningEngine.record_user_approval(db, workflow_id, approved=True)

    return {
        "status": "approved",
        "workflow_id": workflow_id,
        "name": wf.name,
        "approved": True
    }


@router.post("/{workflow_id}/reject")
def reject_workflow(workflow_id: int, db: Session = Depends(database.get_db)):
    """Reject a discovered workflow candidate."""
    wf = db.query(models.workflow.Workflow).filter(models.workflow.Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow #{workflow_id} not found.")

    wf.approved = False
    wf.rejected = True
    db.commit()

    # Record rejection feedback
    FeedbackLearningEngine.record_user_approval(db, workflow_id, approved=False)

    return {
        "status": "rejected",
        "workflow_id": workflow_id,
        "name": wf.name,
        "rejected": True
    }


@router.post("/{workflow_id}/execute")
def trigger_workflow_execution(
    workflow_id: int,
    payload: Optional[ExecuteWorkflowRequest] = None,
    db: Session = Depends(database.get_db)
):
    """Execute an approved workflow with optional starting context."""
    wf = db.query(models.workflow.Workflow).filter(models.workflow.Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow #{workflow_id} not found.")
    if not wf.approved:
        raise HTTPException(status_code=400, detail=f"Workflow #{workflow_id} is in PENDING_APPROVAL state. Must be approved before execution.")

    init_context = payload.context if payload else None
    try:
        exec_id = execute_workflow(db, wf, initial_context=init_context)
        return {"execution_id": exec_id, "workflow_id": workflow_id, "status": "executed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")
