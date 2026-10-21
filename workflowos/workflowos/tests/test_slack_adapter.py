# workflowos/tests/test_slack_adapter.py
"""Tests for Slack Adapter (REAL_SLACK vs LOCAL_FALLBACK vs STRICT_MODE).

Tests use mocking to avoid real network calls.
For live REAL_SLACK integration, set SLACK_WEBHOOK_URL in your .env and run:
  python scratch/test_slack_live.py
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from workflowos.automation.adapters.slack import SlackAdapter


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_context(**extra):
    ctx = {
        "customer_name": "Test Customer",
        "customer_email": "testcustomer@example.com",
        "email_subject": "WorkFlowOS Test Request",
        "execution_id": "exec_test_123",
        "workflow_name": "Process Customer Request",
    }
    ctx.update(extra)
    return ctx


# ── LOCAL_FALLBACK ────────────────────────────────────────────────────────────

def test_slack_local_fallback_mode():
    """When SLACK_WEBHOOK_URL is unset and strict mode off → LOCAL_FALLBACK."""
    env_backup = os.environ.pop("SLACK_WEBHOOK_URL", None)
    os.environ.pop("SLACK_STRICT_MODE", None)

    try:
        context = _make_context()
        success, result, err = SlackAdapter.send_notification(db=None, params={}, context=context)

        assert success is True
        assert err is None
        assert result["mode"] == "LOCAL_FALLBACK"
        assert result["connector"] == "Slack Adapter"
        assert result["status"] == "slack_not_configured"
        assert "WorkFlowOS Workflow Execution Complete" in result["message"]
        assert context["last_local_notification"] == result["message"]
    finally:
        if env_backup:
            os.environ["SLACK_WEBHOOK_URL"] = env_backup


# ── STRICT MODE ───────────────────────────────────────────────────────────────

def test_slack_strict_mode_fails_without_webhook():
    """When SLACK_STRICT_MODE=true and SLACK_WEBHOOK_URL unset → STRICT_FAIL."""
    env_backup = os.environ.pop("SLACK_WEBHOOK_URL", None)
    os.environ["SLACK_STRICT_MODE"] = "true"

    try:
        context = _make_context()
        success, result, err = SlackAdapter.send_notification(db=None, params={}, context=context)

        assert success is False
        assert result["mode"] == "STRICT_FAIL"
        assert result["status"] == "not_configured"
        assert "SLACK_STRICT_MODE" in err
        assert "SLACK_WEBHOOK_URL" in err
    finally:
        os.environ.pop("SLACK_STRICT_MODE", None)
        if env_backup:
            os.environ["SLACK_WEBHOOK_URL"] = env_backup


# ── REAL_SLACK (mocked) ───────────────────────────────────────────────────────

def test_slack_real_mode_success():
    """When webhook is configured and Slack returns 200 → REAL_SLACK SUCCESS."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "ok"

    with patch("workflowos.automation.adapters.slack.requests.post", return_value=mock_resp):
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/TEST/FAKE/URL"
        try:
            context = _make_context()
            success, result, err = SlackAdapter.send_notification(db=None, params={}, context=context)

            assert success is True
            assert err is None
            assert result["mode"] == "REAL_SLACK"
            assert result["status"] == "SUCCESS"
            assert result["http_status"] == 200
            assert result["connector"] == "Slack Webhook"
            assert "WorkFlowOS Workflow Execution Complete" in result["message"]
        finally:
            os.environ.pop("SLACK_WEBHOOK_URL", None)


def test_slack_real_mode_http_error():
    """When webhook returns non-200 status → REAL_SLACK webhook_error."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "invalid_token"

    with patch("workflowos.automation.adapters.slack.requests.post", return_value=mock_resp):
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/TEST/FAKE/URL"
        try:
            context = _make_context()
            success, result, err = SlackAdapter.send_notification(db=None, params={}, context=context)

            assert success is False
            assert result["mode"] == "REAL_SLACK"
            assert result["status"] == "webhook_error"
            assert result["http_status"] == 403
            assert "403" in err
        finally:
            os.environ.pop("SLACK_WEBHOOK_URL", None)


def test_slack_real_mode_connection_error():
    """When network fails → REAL_SLACK connection_error."""
    import requests as req_lib

    with patch(
        "workflowos.automation.adapters.slack.requests.post",
        side_effect=req_lib.exceptions.ConnectionError("Name resolution failed"),
    ):
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/TEST/FAKE/URL"
        try:
            context = _make_context()
            success, result, err = SlackAdapter.send_notification(db=None, params={}, context=context)

            assert success is False
            assert result["mode"] == "REAL_SLACK"
            assert result["status"] == "connection_error"
            assert "Connection refused" in err or "DNS" in err or "Name resolution" in err
        finally:
            os.environ.pop("SLACK_WEBHOOK_URL", None)


def test_slack_real_mode_timeout():
    """When webhook times out → REAL_SLACK timeout_error."""
    import requests as req_lib

    with patch(
        "workflowos.automation.adapters.slack.requests.post",
        side_effect=req_lib.exceptions.Timeout("Request timed out"),
    ):
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/TEST/FAKE/URL"
        try:
            context = _make_context()
            success, result, err = SlackAdapter.send_notification(db=None, params={}, context=context)

            assert success is False
            assert result["mode"] == "REAL_SLACK"
            assert result["status"] == "timeout_error"
            assert "timed out" in err
        finally:
            os.environ.pop("SLACK_WEBHOOK_URL", None)

