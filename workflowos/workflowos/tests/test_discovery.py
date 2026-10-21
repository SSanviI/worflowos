# workflowos/tests/test_discovery.py
from datetime import datetime, timedelta
from workflowos.backend.models.activity import ActivityEvent
from workflowos.workflow_engine.discovery import discover_workflows


def test_discover_file_workflow_from_sessions(db_session):
    # Create 2 sessions of: CREATE_FILE -> RENAME_FILE -> MOVE_FILE
    now = datetime.utcnow()
    for s_idx in range(1, 3):
        sid = f"session_file_{s_idx}"
        actions = ["CREATE_FILE", "RENAME_FILE", "MOVE_FILE"]
        for i, act in enumerate(actions):
            db_session.add(ActivityEvent(
                session_id=sid,
                application="File Explorer",
                action=act,
                target=f"doc_{s_idx}.txt",
                timestamp=now + timedelta(minutes=s_idx * 5, seconds=i * 2)
            ))
    db_session.commit()

    candidates = discover_workflows(db_session)
    assert len(candidates) >= 1
    wf = candidates[0]
    action_types = [a["type"].upper() for a in wf.actions]
    assert action_types == ["CREATE_FILE", "RENAME_FILE", "MOVE_FILE"]
    assert wf.occurrences >= 2
    assert wf.approved is False


def test_discover_multiple_distinct_workflows(db_session):
    # Session 1 & 2: Pattern A (File workflow)
    now = datetime.utcnow()
    for s_idx in range(1, 3):
        sid = f"session_a_{s_idx}"
        for i, act in enumerate(["CREATE_FILE", "RENAME_FILE", "MOVE_FILE"]):
            db_session.add(ActivityEvent(
                session_id=sid,
                application="File Explorer",
                action=act,
                timestamp=now + timedelta(minutes=s_idx * 5, seconds=i)
            ))

    # Session 3 & 4: Pattern B (Spreadsheet workflow)
    for s_idx in range(3, 5):
        sid = f"session_b_{s_idx}"
        for i, act in enumerate(["OPEN_SPREADSHEET", "TRANSFORM_DATA", "EXPORT_DATA"]):
            db_session.add(ActivityEvent(
                session_id=sid,
                application="Excel",
                action=act,
                timestamp=now + timedelta(minutes=s_idx * 5, seconds=i)
            ))
    db_session.commit()

    candidates = discover_workflows(db_session)
    assert len(candidates) == 2
    # Verify both distinct patterns were identified
    discovered_actions = [[a["type"].upper() for a in wf.actions] for wf in candidates]
    assert ["CREATE_FILE", "RENAME_FILE", "MOVE_FILE"] in discovered_actions
    assert ["OPEN_SPREADSHEET", "TRANSFORM_DATA", "EXPORT_DATA"] in discovered_actions
