# workflowos/tests/test_sessionizer.py
from datetime import datetime, timedelta
from workflowos.activity_agent.sessionizer import ActivitySessionizer, sessionize_raw_events


def test_sessionizer_continuity_and_gap():
    sessionizer = ActivitySessionizer(inactivity_timeout_seconds=5.0)
    t0 = datetime(2026, 1, 1, 10, 0, 0)

    # Event 1
    s1 = sessionizer.get_or_create_session(t0, "File Explorer")
    assert s1 is not None

    # Event 2 within 2 seconds -> same session
    t1 = t0 + timedelta(seconds=2)
    s2 = sessionizer.get_or_create_session(t1, "File Explorer")
    assert s2 == s1

    # Event 3 after 10 seconds (exceeds 5.0s gap) -> new session
    t2 = t1 + timedelta(seconds=10)
    s3 = sessionizer.get_or_create_session(t2, "File Explorer")
    assert s3 != s1


def test_batch_sessionize_raw_events():
    events = [
        {"action": "CREATE_FILE", "timestamp": datetime(2026, 1, 1, 10, 0, 0), "application": "Explorer"},
        {"action": "RENAME_FILE", "timestamp": datetime(2026, 1, 1, 10, 0, 2), "application": "Explorer"},
        {"action": "CREATE_FILE", "timestamp": datetime(2026, 1, 1, 10, 5, 0), "application": "Explorer"},
    ]
    res = sessionize_raw_events(events, inactivity_gap_seconds=10.0)
    assert len(res) == 3
    # First two should have same session_id
    assert res[0]["session_id"] == res[1]["session_id"]
    # Third should have a different session_id
    assert res[2]["session_id"] != res[0]["session_id"]
