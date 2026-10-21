# workflowos/tests/test_normalizer.py
from workflowos.activity_agent.normalizer import EventNormalizer


def test_action_normalization():
    assert EventNormalizer.normalize_action("created") == "CREATE_FILE"
    assert EventNormalizer.normalize_action("file_created") == "CREATE_FILE"
    assert EventNormalizer.normalize_action("moved") == "MOVE_FILE"
    assert EventNormalizer.normalize_action("renamed") == "RENAME_FILE"
    assert EventNormalizer.normalize_action("window_focus") == "ACTIVE_WINDOW"
    assert EventNormalizer.normalize_action("READ_EMAIL") == "READ_EMAIL"


def test_privacy_sanitization():
    raw_data = {
        "user": "alice",
        "password": "secret_password_123",
        "api_token": "bearer_abc",
        "normal_key": "normal_val"
    }
    sanitized = EventNormalizer.sanitize_metadata(raw_data)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_token"] == "[REDACTED]"
    assert sanitized["normal_key"] == "normal_val"


def test_create_event_dict():
    ev = EventNormalizer.create_event_dict(
        application="File Explorer",
        action="created",
        target="test.txt",
        session_id="s1",
        raw_data={"path": "C:\\test.txt"}
    )
    assert ev["application"] == "File Explorer"
    assert ev["action"] == "CREATE_FILE"
    assert ev["target"] == "test.txt"
    assert ev["session_id"] == "s1"
