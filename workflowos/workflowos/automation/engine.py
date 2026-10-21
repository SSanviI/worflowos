# workflowos/automation/engine.py
"""Automation Execution Engine.

Executes approved workflows step-by-step using registered action adapters.
Propagates shared execution context across steps, logs full telemetry to the
database, and feeds execution results into the learning engine.
"""

import time
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from ..backend.models.workflow import Workflow
from ..backend.models.workflow_execution import WorkflowExecution, ExecutionStep
from .registry import get_action
from ..workflow_engine.learning import FeedbackLearningEngine


def execute_workflow(
    db: Session,
    workflow: Workflow,
    initial_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Execute an approved workflow step-by-step.

    Returns the unique execution identifier (e.g. 'exec_1710000000').
    Raises ValueError if workflow is not approved.
    """
    if not workflow.approved:
        raise ValueError(f"Workflow #{workflow.id} must be approved before execution.")

    start_wall_time = time.time()
    start_dt = datetime.datetime.utcnow()

    # 1. Create execution record
    timestamp_id = int(start_dt.timestamp())
    exec_id_str = f"exec_{timestamp_id}_{workflow.id}"

    exec_record = WorkflowExecution(
        workflow_id=workflow.id,
        execution_id=exec_id_str,
        status="running",
        start_time=start_dt,
    )
    db.add(exec_record)
    db.flush()

    # 2. Initialize execution context
    context: Dict[str, Any] = dict(initial_context or {})
    context["execution_id"] = exec_id_str
    context["workflow_name"] = workflow.name
    overall_success = True
    first_error: Optional[str] = None
    failed_action_id: Optional[str] = None
    failed_action_type: Optional[str] = None

    # 3. Step execution loop
    for step_idx, action_def in enumerate(workflow.actions or []):
        action_id = action_def.get("id", f"a{step_idx+1}")
        action_type = action_def.get("type", "").upper()
        params = action_def.get("parameters", {})

        step_start_dt = datetime.datetime.utcnow()
        step = ExecutionStep(
            execution_id=exec_record.id,
            action_id=action_id,
            status="running",
            start_time=step_start_dt,
        )
        db.add(step)
        db.flush()

        fn = get_action(action_type)
        if not fn:
            step.status = "failure"
            step.finish_time = datetime.datetime.utcnow()
            step.error = f"Unsupported or unregistered action type: '{action_type}'"
            overall_success = False
            first_error = step.error
            failed_action_id = action_id
            failed_action_type = action_type
            db.commit()
            break

        try:
            success, result_data, err_msg = fn(db, params, context)
            step.finish_time = datetime.datetime.utcnow()

            # Extract connector and mode from step result payload if available
            if isinstance(result_data, dict):
                step.connector = result_data.get("connector")
                step.mode = result_data.get("mode")

            if success:
                step.status = "success"
                step.result = result_data
                step.error = None
            else:
                step.status = "failure"
                step.result = result_data
                step.error = err_msg or "Action returned failure"
                overall_success = False
                first_error = step.error
                failed_action_id = action_id
                failed_action_type = action_type
                db.commit()
                # Stop on failure immediately
                break
        except Exception as exc:
            step.finish_time = datetime.datetime.utcnow()
            step.status = "failure"
            step.error = f"Unhandled exception: {str(exc)}"
            overall_success = False
            first_error = step.error
            failed_action_id = action_id
            failed_action_type = action_type
            db.commit()
            break

        db.commit()

    # 4. Finalize execution record
    finish_dt = datetime.datetime.utcnow()
    exec_record.finish_time = finish_dt
    exec_record.status = "success" if overall_success else "failure"
    exec_record.error = first_error
    exec_record.result = {
        "final_context": {k: str(v) for k, v in context.items()},
        "steps_completed": len(workflow.actions) if overall_success else step_idx,
    }
    db.commit()

    # 5. Record feedback in learning engine
    duration = time.time() - start_wall_time
    FeedbackLearningEngine.record_execution_feedback(
        db=db,
        workflow_id=workflow.id,
        success=overall_success,
        duration_seconds=duration,
        failed_action_id=failed_action_id,
        failed_action_type=failed_action_type,
        error_message=first_error,
    )

    return exec_record.execution_id
