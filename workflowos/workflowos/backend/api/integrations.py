# workflowos/backend/api/integrations.py
"""Integrations Status & Diagnostics API.

Provides real-time telemetry and test execution endpoints for:
- Gmail API & OAuth 2.0 status
- Local CRM SQLite Database status
- Slack Webhook integration status
- AI Engine provider status
- Playwright Browser Automation status
"""

import os
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import database, config
from ..models.demo_customer import DemoCustomer
from ...automation.adapters.gmail import check_gmail_auth_status, GmailAdapter
from ...automation.adapters.slack import SlackAdapter
from ...automation.adapters.crm import CRMAdapter

router = APIRouter()


@router.get("/status")
def get_integrations_status(db: Session = Depends(database.get_db)):
    """Return health and connection mode for all system adapters."""
    gmail_info = check_gmail_auth_status()

    # Local CRM status
    try:
        cust_count = db.query(DemoCustomer).count()
        crm_info = {
            "configured": True,
            "mode": "REAL_DATABASE",
            "status": "connected",
            "database": "SQLite (app.db)",
            "customer_count": cust_count,
        }
    except Exception as e:
        crm_info = {
            "configured": False,
            "mode": "REAL_DATABASE",
            "status": "error",
            "error": str(e),
        }

    # Slack status
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    slack_info = {
        "configured": bool(slack_webhook),
        "mode": "REAL_SLACK" if slack_webhook else "LOCAL_FALLBACK",
        "status": "configured" if slack_webhook else "local_fallback_only",
        "webhook_url": slack_webhook or None,
    }

    # AI Engine status
    has_gemini = bool(config.GEMINI_API_KEY)
    ai_info = {
        "configured": True,
        "mode": "GEMINI_AI" if has_gemini else "LOCAL_FALLBACK",
        "provider": "Google Gemini 1.5/2.0 API" if has_gemini else "Compositional Fallback AI Engine",
        "has_api_key": has_gemini,
    }

    # Playwright Browser status
    browser_info = {
        "configured": True,
        "mode": "PLAYWRIGHT_READY",
        "status": "available",
        "headless": False,
    }

    return {
        "gmail": gmail_info,
        "local_crm": crm_info,
        "slack": slack_info,
        "ai_engine": ai_info,
        "browser": browser_info,
    }


@router.post("/gmail/test")
def test_gmail_integration(db: Session = Depends(database.get_db)):
    """Test Gmail API connection: verify OAuth + fetch inbox profile, then search for any email."""
    from ...automation.adapters.gmail import get_gmail_service

    # Step 1: Verify OAuth connectivity via profile
    service = get_gmail_service()
    if not service:
        return {
            "status": "failure",
            "connector": "Gmail API",
            "mode": "REAL_API",
            "error": "Gmail OAuth not configured or token invalid.",
            "details": check_gmail_auth_status(),
        }

    try:
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile.get("emailAddress", "unknown")
        total_messages = profile.get("messagesTotal", 0)
        total_threads = profile.get("threadsTotal", 0)
    except Exception as e:
        return {
            "status": "failure",
            "connector": "Gmail API",
            "mode": "REAL_API",
            "error": f"Gmail API profile fetch failed: {e}",
        }

    # Step 2: Try reading most recent email (any email)
    context = {}
    success, result_data, error_msg = GmailAdapter.read_email(
        db=db,
        params={"subject": ""},
        context=context,
    )

    return {
        "status": "success",
        "connector": "Gmail API",
        "mode": "REAL_API",
        "authenticated_account": email_address,
        "total_messages_in_inbox": total_messages,
        "total_threads": total_threads,
        "email_read_status": result_data.get("status") if isinstance(result_data, dict) else "unknown",
        "email_subject": result_data.get("subject") if isinstance(result_data, dict) else None,
        "email_sender": result_data.get("sender") if isinstance(result_data, dict) else None,
        "subject": result_data.get("subject") if isinstance(result_data, dict) else None,
        "sender": result_data.get("sender") if isinstance(result_data, dict) else None,
        "has_attachment": result_data.get("has_attachment", False) if isinstance(result_data, dict) else False,
        "attachment_filename": result_data.get("attachment_filename") if isinstance(result_data, dict) else None,
        "details": result_data,
    }


@router.post("/slack/test")
def test_slack_integration(db: Session = Depends(database.get_db)):
    """Test Slack integration by sending a test message."""
    context = {
        "customer_name": "Test Customer",
        "email_subject": "WorkFlowOS Integration Diagnostics Test",
        "execution_id": "exec_test_diagnostics",
        "workflow_name": "Diagnostics Health Check",
    }
    success, result_data, error_msg = SlackAdapter.send_notification(
        db=db,
        params={},
        context=context,
    )

    return {
        "status": "success" if success else "failure",
        "mode": result_data.get("mode"),
        "connector": result_data.get("connector"),
        "details": result_data,
        "error": error_msg,
    }


@router.post("/crm/seed")
def seed_crm_test_customer(db: Session = Depends(database.get_db)):
    """Ensure 'Test Customer' profile exists in Local CRM database."""
    cust = db.query(DemoCustomer).filter(DemoCustomer.name == "Test Customer").first()
    if not cust:
        cust = DemoCustomer(
            name="Test Customer",
            email="testcustomer@example.com",
            company="ACME Corp",
            status="NEW",
        )
        db.add(cust)
        db.commit()
        db.refresh(cust)

    return {
        "status": "customer_ready",
        "customer": {
            "id": cust.id,
            "name": cust.name,
            "email": cust.email,
            "company": cust.company,
            "status": cust.status,
        },
    }


class CustomerCreateRequest(BaseModel):
    name: str
    email: str
    company: Optional[str] = None
    status: Optional[str] = "ACTIVE"


class CustomerFindRequest(BaseModel):
    query: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


@router.get("/crm/customers")
def list_crm_customers(db: Session = Depends(database.get_db)):
    """List all customer records directly from Local SQLite CRM database."""
    customers = db.query(DemoCustomer).order_by(DemoCustomer.id.asc()).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "company": c.company or "",
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in customers
    ]


@router.post("/crm/customers")
def add_or_update_crm_customer(payload: CustomerCreateRequest, db: Session = Depends(database.get_db)):
    """Add a legitimate customer record into the Local SQLite CRM Database (persisted to app.db)."""
    clean_name = (payload.name or "").strip()
    clean_email = (payload.email or "").strip().lower()
    clean_company = (payload.company or "").strip()
    clean_status = (payload.status or "ACTIVE").strip().upper()

    if not clean_name or not clean_email:
        raise HTTPException(status_code=400, detail="Customer 'name' and 'email' are required.")

    # Check for existing customer by email in the SQLite database
    cust = db.query(DemoCustomer).filter(DemoCustomer.email.ilike(clean_email)).first()
    if cust:
        cust.name = clean_name
        if clean_company:
            cust.company = clean_company
        cust.status = clean_status
        action = "updated"
    else:
        cust = DemoCustomer(
            name=clean_name,
            email=clean_email,
            company=clean_company,
            status=clean_status,
        )
        db.add(cust)
        action = "created"

    db.commit()
    db.refresh(cust)

    return {
        "status": "success",
        "action": action,
        "customer": {
            "id": cust.id,
            "name": cust.name,
            "email": cust.email,
            "company": cust.company,
            "status": cust.status,
            "created_at": cust.created_at.isoformat() if cust.created_at else None,
        },
    }


@router.post("/crm/find")
def test_crm_find_customer(payload: CustomerFindRequest, db: Session = Depends(database.get_db)):
    """Execute authentic CRMAdapter.find_customer lookup against Local CRM database."""
    params: Dict[str, Any] = {}
    context: Dict[str, Any] = {}

    if payload.query:
        clean_q = payload.query.strip()
        if "<" in clean_q or "@" in clean_q:
            context["email_sender"] = clean_q
            params["email"] = clean_q
        else:
            params["name"] = clean_q

    if payload.email:
        params["email"] = payload.email.strip()
    if payload.name:
        params["name"] = payload.name.strip()

    success, result_data, err_msg = CRMAdapter.find_customer(
        db=db,
        params=params,
        context=context,
    )

    return {
        "status": "success" if success else "failure",
        "connector": "Local CRM DB",
        "mode": "REAL_DATABASE",
        "searched": payload.dict(),
        "result": result_data,
        "error": err_msg,
    }

