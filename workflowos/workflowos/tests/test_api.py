# workflowos/tests/test_api.py
from fastapi.testclient import TestClient
from workflowos.backend.main import app
from workflowos.backend import database, models

client = TestClient(app)


def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_api_events_and_discovery_flow():
    # 1. Clear database
    res = client.post("/api/demo/reset")
    assert res.status_code == 200

    # 2. Ingest 2 sessions of events
    for sid in ["session_1", "session_2"]:
        for act in ["CREATE_FILE", "RENAME_FILE", "MOVE_FILE"]:
            res = client.post("/api/events/", json={
                "session_id": sid,
                "application": "File Explorer",
                "action": act,
                "target": "invoice.pdf"
            })
            assert res.status_code == 200

    # 3. List events
    res = client.get("/api/events/")
    assert res.status_code == 200
    assert len(res.json()) >= 6

    # 4. Trigger discovery
    res = client.post("/api/workflows/discover")
    assert res.status_code == 200
    workflows = res.json()
    assert len(workflows) >= 1

    wf_id = workflows[0]["id"]
    assert workflows[0]["approved"] is False

    # 5. Approve workflow
    res = client.post(f"/api/workflows/{wf_id}/approve")
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    # 6. Execute approved workflow
    res = client.post(f"/api/workflows/{wf_id}/execute")
    assert res.status_code == 200
    exec_id = res.json()["execution_id"]
    assert exec_id is not None

    # 7. Check execution steps
    res = client.get(f"/api/executions/{exec_id}/steps")
    assert res.status_code == 200
    steps = res.json()
    assert len(steps) >= 1
