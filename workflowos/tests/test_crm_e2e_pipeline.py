# workflowos/tests/test_crm_e2e_pipeline.py
"""End-to-end test for CRM observation, discovery, approval, failure handling, and execution pipeline."""

import pytest
from fastapi.testclient import TestClient
from workflowos.backend.main import app
from workflowos.backend import database, models
from workflowos.backend.models.workflow import Workflow
from workflowos.backend.models.demo_customer import DemoCustomer, CustomerRequest

client = TestClient(app)


def test_full_crm_pipeline_e2e_honest_failure_and_execution():
    # 1. Reset database
    res = client.post("/api/demo/reset")
    assert res.status_code == 200

    # 2. Seed test customer in Local CRM database
    res = client.post("/api/integrations/crm/seed")
    assert res.status_code == 200
    assert res.json()["status"] == "customer_ready"

    # 3. Simulate CRM Activity Stream for observation
    res = client.post("/api/demo/run_crm")
    assert res.status_code == 200
    demo_data = res.json()
    assert demo_data["events_generated"] >= 5

    # 4. Inspect discovered candidate workflow
    res = client.get("/api/workflows/")
    assert res.status_code == 200
    workflows = res.json()
    assert len(workflows) >= 1

    target_wf = workflows[0]
    wf_id = target_wf["id"]

    # 5. Approve workflow
    res = client.post(f"/api/workflows/{wf_id}/approve")
    assert res.status_code == 200

    # 6. Execute workflow - with real Gmail OAuth it may succeed or fail gracefully
    res = client.post(f"/api/workflows/{wf_id}/execute")
    assert res.status_code == 200
    exec_id = res.json()["execution_id"]

    res = client.get(f"/api/executions/{exec_id}/steps")
    assert res.status_code == 200
    steps = res.json()
    # At least 1 step must have been attempted
    assert len(steps) >= 1
    # First step must be a Gmail API step
    assert steps[0]["connector"] == "Gmail API"
    assert steps[0]["mode"] == "REAL_API"
    # Step status is either success (OAuth live) or failure (honest error)
    assert steps[0]["status"] in ("success", "failure")

    # 7. Create and approve direct Local CRM execution workflow (FIND_CUSTOMER -> UPDATE_CUSTOMER -> SEND_NOTIFICATION)
    db = next(database.get_db())
    crm_wf = Workflow(
        name="Local CRM Direct Customer Request Flow",
        description="Processes customer request directly against Local SQLite CRM database and Slack.",
        trigger={"type": "event", "source": "crm"},
        actions=[
            {"id": "a1", "type": "FIND_CUSTOMER", "parameters": {"name": "Test Customer"}},
            {"id": "a2", "type": "UPDATE_CUSTOMER", "parameters": {"status": "REQUEST_PROCESSED"}},
            {"id": "a3", "type": "SEND_NOTIFICATION", "parameters": {}},
        ],
        approved=True,
        confidence=0.98,
        occurrences=5,
    )
    db.add(crm_wf)
    db.commit()
    db.refresh(crm_wf)

    # 8. Execute Local CRM workflow
    res = client.post(f"/api/workflows/{crm_wf.id}/execute")
    assert res.status_code == 200
    crm_exec_id = res.json()["execution_id"]

    res = client.get(f"/api/executions/{crm_exec_id}/steps")
    assert res.status_code == 200
    crm_steps = res.json()
    assert len(crm_steps) == 3

    # Step 1: FIND_CUSTOMER
    assert crm_steps[0]["connector"] == "Local CRM DB"
    assert crm_steps[0]["mode"] == "REAL_DATABASE"
    assert crm_steps[0]["status"] == "success"

    # Step 2: UPDATE_CUSTOMER
    assert crm_steps[1]["connector"] == "Local CRM DB"
    assert crm_steps[1]["mode"] == "REAL_DATABASE"
    assert crm_steps[1]["status"] == "success"

    # Step 3: SEND_NOTIFICATION
    # Connector name is "Slack Webhook" in REAL_SLACK mode, "Slack Adapter" in LOCAL_FALLBACK
    assert crm_steps[2]["connector"] in ("Slack Webhook", "Slack Adapter")
    assert crm_steps[2]["mode"] in ("LOCAL_FALLBACK", "REAL_SLACK")
    assert crm_steps[2]["status"] == "success"


    # 9. Verify database mutation in SQLite
    cust = db.query(DemoCustomer).filter(DemoCustomer.name == "Test Customer").first()
    assert cust.status == "REQUEST_PROCESSED"
    reqs = db.query(CustomerRequest).filter(CustomerRequest.customer_id == cust.id).all()
    assert len(reqs) >= 1
