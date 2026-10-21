# workflowos/demo/simulator.py
"""Controlled Demo Simulator for WorkFlowOS.

Drives the REAL end-to-end discovery pipeline (Events -> Sessionizer -> Discovery -> AI -> Generator).
Marks observation activity events clearly as SIMULATED OBSERVATION while real execution executes live adapters.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from ..backend.models.activity import ActivityEvent
from ..backend.models.demo_customer import DemoCustomer
from ..workflow_engine.discovery import discover_workflows
from ..workflow_engine.generator import enrich_workflow


def simulate_file_organization_sessions(db: Session, num_sessions: int = 3) -> List[Dict[str, Any]]:
    """Simulate repeated user file-organization activity events across distinct sessions.

    Sequence: CREATE_FILE -> RENAME_FILE -> MOVE_FILE
    """
    now = datetime.utcnow()
    events_created = []

    for s_idx in range(1, num_sessions + 1):
        session_id = f"sim_files_session_{s_idx}_{int(now.timestamp())}"
        base_time = now - timedelta(minutes=(num_sessions - s_idx) * 10)

        file_raw_name = f"invoice_2026_q{s_idx}.pdf"
        renamed_name = f"approved_invoice_q{s_idx}.pdf"

        actions = [
            ("CREATE_FILE", "File Explorer", file_raw_name, {"path": f"C:\\WorkFlowOS_Test\\Input\\{file_raw_name}", "simulated": True}),
            ("RENAME_FILE", "File Explorer", f"{file_raw_name} -> {renamed_name}", {"old_name": file_raw_name, "new_name": renamed_name, "simulated": True}),
            ("MOVE_FILE", "File Explorer", renamed_name, {"source": f"C:\\WorkFlowOS_Test\\Input\\{renamed_name}", "destination": f"C:\\WorkFlowOS_Test\\Output\\{renamed_name}", "simulated": True}),
        ]

        for step_idx, (act, app, target, raw) in enumerate(actions):
            ev = ActivityEvent(
                session_id=session_id,
                application=app,
                action=act,
                target=target,
                timestamp=base_time + timedelta(seconds=step_idx * 5),
                raw_data=raw,
            )
            db.add(ev)
            events_created.append({"action": act, "target": target, "session": session_id, "simulated": True})

    db.commit()
    return events_created


def simulate_customer_request_sessions(db: Session, num_sessions: int = 3) -> List[Dict[str, Any]]:
    """Simulate repeated customer request workflows for observation.

    Sequence: READ_EMAIL -> DOWNLOAD_ATTACHMENT -> FIND_CUSTOMER -> UPDATE_CUSTOMER -> SEND_NOTIFICATION
    """
    # Ensure legitimate test customer exists in Local SQLite CRM Database
    cust = db.query(DemoCustomer).filter(DemoCustomer.email == "sas23aiml@cmrit.ac.in").first()
    if not cust:
        cust = DemoCustomer(
            name="Sanvi S",
            email="sas23aiml@cmrit.ac.in",
            company="CMR Institute of Technology",
            status="ACTIVE",
        )
        db.add(cust)
        db.commit()

    test_cust = db.query(DemoCustomer).filter(DemoCustomer.name == "Test Customer").first()
    if not test_cust:
        db.add(DemoCustomer(name="Test Customer", email="testcustomer@example.com", company="ACME Corp", status="NEW"))
        db.commit()

    now = datetime.utcnow()
    events_created = []

    session_data = [
        {
            "subject": "Fwd: SAP Labs Assessment Test – Lab Allotment & Important Instructions for Tomorrow",
            "attachment": "Job Description_2Y AI ML.docx",
            "customer": "Sanvi S <sas23aiml@cmrit.ac.in>",
            "update": "Customer Sanvi S Status -> REQUEST_PROCESSED",
            "slack_channel": "#customer-requests",
        },
        {
            "subject": "Customer Inquiry: Followup on Assessment Lab Allotment Instructions",
            "attachment": "Assessment_Instructions_v2.docx",
            "customer": "Sanvi S <sas23aiml@cmrit.ac.in>",
            "update": "Customer Sanvi S Status -> REQUEST_PROCESSED",
            "slack_channel": "#customer-requests",
        },
        {
            "subject": "Urgent Student Submission - 2026-2027 Batch Confirmation",
            "attachment": "Student_Batch_Allotment.docx",
            "customer": "Sanvi S <sas23aiml@cmrit.ac.in>",
            "update": "Customer Sanvi S Status -> REQUEST_PROCESSED",
            "slack_channel": "#customer-requests",
        },
    ]

    for s_idx in range(1, num_sessions + 1):
        session_id = f"crm_observed_session_{s_idx}_{int(now.timestamp())}"
        base_time = now - timedelta(minutes=(num_sessions - s_idx + 1) * 12)
        info = session_data[(s_idx - 1) % len(session_data)]

        actions = [
            ("READ_EMAIL", "Gmail", info["subject"], {"subject": info["subject"], "sender": info["customer"]}),
            ("DOWNLOAD_ATTACHMENT", "Gmail", info["attachment"], {"filename": info["attachment"]}),
            ("FIND_CUSTOMER", "Local CRM", info["customer"], {"customer_name": info["customer"], "email": "sas23aiml@cmrit.ac.in"}),
            ("UPDATE_CUSTOMER", "Local CRM", info["update"], {"customer_name": "Sanvi S", "status": "REQUEST_PROCESSED"}),
            ("SEND_NOTIFICATION", "Slack", info["slack_channel"], {"channel": info["slack_channel"]}),
        ]

        for step_idx, (act, app, target, raw) in enumerate(actions):
            ev = ActivityEvent(
                session_id=session_id,
                application=app,
                action=act,
                target=target,
                timestamp=base_time + timedelta(seconds=step_idx * 7),
                raw_data=raw,
            )
            db.add(ev)
            events_created.append({"action": act, "target": target, "session": session_id, "app": app})

    db.commit()
    return events_created


def run_pipeline_discovery(db: Session):
    """Run real discovery and AI understanding over all accumulated events."""
    candidates = discover_workflows(db)
    for wf in candidates:
        enrich_workflow(db, wf)
    return candidates
