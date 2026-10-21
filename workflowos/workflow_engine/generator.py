# workflowos/workflow_engine/generator.py
"""Workflow generator – enriches discovered candidates with AI intent,
dynamic variables, derived conditions, and failure policies.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from ..backend.models.workflow import Workflow
from ..ai_engine.local_fallback import LocalFallbackProvider
from ..ai_engine.gemini_provider import GeminiProvider
from ..backend.config import GEMINI_API_KEY


def _select_ai_provider():
    if GEMINI_API_KEY:
        try:
            return GeminiProvider()
        except Exception:
            pass
    return LocalFallbackProvider()


def enrich_workflow(db: Session, workflow: Workflow) -> Workflow:
    """Enrich a candidate Workflow record with AI-derived metadata.

    Fills: name (intent), description, trigger, variables, conditions, failure_policy.
    Maintains approval state (starts False).
    """
    if not workflow.actions:
        raise ValueError("Workflow has no actions to enrich")

    # Extract canonical action names
    action_types = [a.get("type", "").upper() for a in workflow.actions]

    provider = _select_ai_provider()
    try:
        ai_result = provider.understand_workflow(action_types)
    except Exception:
        fallback = LocalFallbackProvider()
        ai_result = fallback.understand_workflow(action_types)

    # Populate fields dynamically derived from the specific workflow
    workflow.name = ai_result.get("intent") or workflow.name or "Discovered Workflow"
    workflow.description = ai_result.get("description") or workflow.description
    workflow.trigger = ai_result.get("trigger") or {"type": "manual_or_event", "source": "system"}
    workflow.variables = ai_result.get("variables") or []
    workflow.conditions = ai_result.get("conditions") or []
    workflow.failure_policy = ai_result.get("failure_policy") or {
        "retry_count": 2,
        "on_final_failure": "stop_and_notify",
        "require_manual_intervention": True,
    }

    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow
