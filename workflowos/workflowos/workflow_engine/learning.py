# workflowos/workflow_engine/learning.py
"""Feedback-Based Workflow Refinement and Learning Engine.

Records execution telemetry and user decisions (approval / rejection) to
dynamically refine workflow confidence, compute action reliability metrics,
and flag unreliable integration points.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..backend.models.learning import WorkflowFeedback
from ..backend.models.workflow import Workflow


class FeedbackLearningEngine:
    """Calculates heuristic feedback and adjusts workflow reliability."""

    @staticmethod
    def record_execution_feedback(
        db: Session,
        workflow_id: int,
        success: bool,
        duration_seconds: float,
        failed_action_id: Optional[str] = None,
        failed_action_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Record an execution result and update workflow confidence."""
        event_type = "execution_success" if success else "execution_failure"
        entry = WorkflowFeedback(
            workflow_id=workflow_id,
            event_type=event_type,
            action_id=failed_action_id,
            action_type=failed_action_type,
            duration_seconds=duration_seconds,
            error_message=error_message,
        )
        db.add(entry)

        # Refine workflow confidence
        wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if wf:
            current_conf = wf.confidence or 0.8
            if success:
                # Slight positive boost up to 0.99
                wf.confidence = min(0.99, round(current_conf + 0.02, 4))
            else:
                # Penalty on failure
                wf.confidence = max(0.20, round(current_conf - 0.10, 4))
            db.add(wf)

        db.commit()

    @staticmethod
    def record_user_approval(db: Session, workflow_id: int, approved: bool):
        """Record user approval or rejection."""
        event_type = "approval" if approved else "rejection"
        entry = WorkflowFeedback(
            workflow_id=workflow_id,
            event_type=event_type,
        )
        db.add(entry)

        wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if wf:
            current_conf = wf.confidence or 0.8
            if approved:
                wf.confidence = min(0.99, round(current_conf + 0.05, 4))
            else:
                # Rejection reduces confidence significantly
                wf.confidence = max(0.10, round(current_conf - 0.25, 4))
            db.add(wf)

        db.commit()

    @staticmethod
    def get_workflow_learning_summary(db: Session, workflow_id: int) -> Dict[str, Any]:
        """Compute aggregated reliability statistics for a workflow."""
        feedbacks = (
            db.query(WorkflowFeedback)
            .filter(WorkflowFeedback.workflow_id == workflow_id)
            .all()
        )

        total_execs = 0
        success_execs = 0
        failures_by_action: Dict[str, int] = {}

        for f in feedbacks:
            if f.event_type == "execution_success":
                total_execs += 1
                success_execs += 1
            elif f.event_type == "execution_failure":
                total_execs += 1
                act = f.action_type or f.action_id or "unknown"
                failures_by_action[act] = failures_by_action.get(act, 0) + 1

        success_rate = (success_execs / total_execs) if total_execs > 0 else 1.0
        unreliable_actions = [act for act, count in failures_by_action.items() if count >= 2]

        return {
            "workflow_id": workflow_id,
            "total_executions": total_execs,
            "success_count": success_execs,
            "failure_count": total_execs - success_execs,
            "reliability_rate": round(success_rate * 100, 1),
            "unreliable_actions": unreliable_actions,
            "failures_by_action": failures_by_action,
        }
