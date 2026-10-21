# workflowos/tests/test_gmail_adapter.py
"""Tests for Gmail Adapter and Auth Status."""

import pytest
from workflowos.automation.adapters.gmail import check_gmail_auth_status, GmailAdapter


def test_check_gmail_auth_status():
    status = check_gmail_auth_status()
    assert "configured" in status
    assert "mode" in status
    assert "message" in status


def test_gmail_read_email_unconfigured_credentials():
    # When credentials.json / token.json are not present, should report credentials_required
    context = {}
    success, result, err = GmailAdapter.read_email(
        db=None,
        params={"subject": "WorkFlowOS Test Customer Request"},
        context=context,
    )

    # Result dict must contain connector and mode
    assert isinstance(result, dict)
    assert "connector" in result
    assert "mode" in result
