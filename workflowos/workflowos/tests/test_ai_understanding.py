# workflowos/tests/test_ai_understanding.py
from workflowos.ai_engine.local_fallback import LocalFallbackProvider


def test_compositional_fallback_file_workflow():
    provider = LocalFallbackProvider()
    actions = ["CREATE_FILE", "RENAME_FILE", "MOVE_FILE"]
    res = provider.understand_workflow(actions)

    assert "File" in res["intent"] or "Rename" in res["intent"]
    assert "Organize" in res["intent"] or "File" in res["intent"]
    assert res["trigger"]["type"] == "file_event"
    assert any(v["name"] == "file_path" for v in res["variables"])
    assert any(c["condition"] == "source_file_exists" for c in res["conditions"])


def test_compositional_fallback_customer_workflow():
    provider = LocalFallbackProvider()
    actions = ["READ_EMAIL", "DOWNLOAD_ATTACHMENT", "FIND_CUSTOMER", "UPDATE_CUSTOMER", "SEND_NOTIFICATION"]
    res = provider.understand_workflow(actions)

    assert "Customer" in res["intent"]
    assert res["trigger"]["type"] == "email_event"
    assert any(v["name"] == "customer_id" for v in res["variables"])
    assert any(c["condition"] == "customer_record_valid" for c in res["conditions"])


def test_compositional_fallback_arbitrary_workflow():
    provider = LocalFallbackProvider()
    actions = ["OPEN_SPREADSHEET", "TRANSFORM_DATA", "EXPORT_DATA"]
    res = provider.understand_workflow(actions)

    assert "Data" in res["intent"] or "Spreadsheet" in res["intent"] or "Transform" in res["intent"]
    assert len(res["description"]) > 10
