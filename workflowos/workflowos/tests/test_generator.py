# workflowos/tests/test_generator.py
from workflowos.backend.models.workflow import Workflow
from workflowos.workflow_engine.generator import enrich_workflow


def test_enrich_workflow(db_session):
    wf = Workflow(
        name="Detected Workflow",
        description="",
        actions=[
            {"id": "a1", "type": "create_file", "parameters": {}},
            {"id": "a2", "type": "rename_file", "parameters": {}},
            {"id": "a3", "type": "move_file", "parameters": {}},
        ],
        confidence=0.9,
        occurrences=3,
        approved=False,
    )
    db_session.add(wf)
    db_session.commit()

    enriched = enrich_workflow(db_session, wf)
    assert enriched.name != "Detected Workflow"
    assert "File" in enriched.name or "Rename" in enriched.name or "Organize" in enriched.name
    assert len(enriched.variables) > 0
    assert len(enriched.conditions) > 0
    # Must NOT have hardcoded customer conditions
    assert not any(c.get("condition") == "customer_record_valid" for c in enriched.conditions)
    # Must remain in unapproved state until user approves
    assert enriched.approved is False
