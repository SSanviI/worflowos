# workflowos/tests/test_engine_execution.py
import os
import tempfile
import pytest
from workflowos.backend.models.workflow import Workflow
from workflowos.backend.models.workflow_execution import WorkflowExecution, ExecutionStep
from workflowos.automation.engine import execute_workflow
from workflowos.workflow_engine.learning import FeedbackLearningEngine


def test_execute_approved_file_workflow(db_session):
    with tempfile.TemporaryDirectory() as temp_dir:
        in_dir = os.path.join(temp_dir, "Input")
        out_dir = os.path.join(temp_dir, "Output")
        os.makedirs(in_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        wf = Workflow(
            name="Organize Files",
            actions=[
                {"id": "a1", "type": "create_file", "parameters": {"input_dir": in_dir, "content": "Sample file data"}},
                {"id": "a2", "type": "rename_file", "parameters": {"new_name": "processed_data.txt"}},
                {"id": "a3", "type": "move_file", "parameters": {"destination_dir": out_dir}},
            ],
            confidence=0.85,
            occurrences=3,
            approved=True,
        )
        db_session.add(wf)
        db_session.commit()

        exec_id = execute_workflow(db_session, wf)
        assert exec_id is not None

        # Verify DB execution record
        exec_rec = db_session.query(WorkflowExecution).filter(WorkflowExecution.execution_id == exec_id).first()
        assert exec_rec is not None
        assert exec_rec.status == "success"

        # Verify execution steps
        steps = db_session.query(ExecutionStep).filter(ExecutionStep.execution_id == exec_rec.id).all()
        assert len(steps) == 3
        assert all(s.status == "success" for s in steps)

        # Verify actual disk file exists in out_dir
        expected_file = os.path.join(out_dir, "processed_data.txt")
        assert os.path.exists(expected_file)


def test_unapproved_workflow_execution_rejected(db_session):
    wf = Workflow(
        name="Unapproved Workflow",
        actions=[{"id": "a1", "type": "create_file", "parameters": {}}],
        confidence=0.85,
        occurrences=2,
        approved=False,  # Unapproved
    )
    db_session.add(wf)
    db_session.commit()

    with pytest.raises(ValueError) as exc:
        execute_workflow(db_session, wf)
    assert "must be approved" in str(exc.value)
