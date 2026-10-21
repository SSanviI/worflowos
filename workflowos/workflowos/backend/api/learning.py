# workflowos/backend/api/learning.py
"""API endpoints for Feedback-based Learning and Workflow Reliability statistics."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from .. import database, models
from ...workflow_engine.learning import FeedbackLearningEngine

router = APIRouter()


@router.get("/stats/{workflow_id}")
def get_workflow_stats(workflow_id: int, db: Session = Depends(database.get_db)):
    """Retrieve reliability and learning statistics for a specific workflow."""
    wf = db.query(models.workflow.Workflow).filter(models.workflow.Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    summary = FeedbackLearningEngine.get_workflow_learning_summary(db, workflow_id)
    summary["workflow_name"] = wf.name
    summary["confidence"] = wf.confidence
    return summary


@router.get("/stats")
def get_all_learning_stats(db: Session = Depends(database.get_db)):
    """Retrieve learning statistics across all workflows."""
    workflows = db.query(models.workflow.Workflow).all()
    results = []
    for wf in workflows:
        s = FeedbackLearningEngine.get_workflow_learning_summary(db, wf.id)
        s["workflow_name"] = wf.name
        s["confidence"] = wf.confidence
        results.append(s)
    return results
