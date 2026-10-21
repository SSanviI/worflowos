# workflowos/backend/api/demo.py
"""Demo Mode API endpoints.

Feeds controlled activity events into the real WorkFlowOS ingestion and discovery pipeline.
Does NOT inject pre-baked workflows or fake execution records directly into the database.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import database, models
from ...demo.simulator import (
    simulate_file_organization_sessions,
    simulate_customer_request_sessions,
    run_pipeline_discovery,
)

router = APIRouter()


@router.post("/reset")
@router.post("/reset_demo")
def reset_demo(db: Session = Depends(database.get_db)):
    """Reset database tables for a fresh demonstration run and re-seed legitimate test customer."""
    db.close()
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)

    # Re-seed legitimate test customer in Local SQLite CRM Database
    new_db = database.SessionLocal()
    try:
        sanvi = models.demo_customer.DemoCustomer(
            name="Sanvi S",
            email="sas23aiml@cmrit.ac.in",
            company="CMR Institute of Technology",
            status="ACTIVE",
        )
        test_cust = models.demo_customer.DemoCustomer(
            name="Test Customer",
            email="testcustomer@example.com",
            company="ACME Corp",
            status="NEW",
        )
        new_db.add(sanvi)
        new_db.add(test_cust)
        new_db.commit()
    finally:
        new_db.close()

    return {
        "status": "reset_complete",
        "message": "Activity events, workflows, and execution history cleared. Schema re-initialized with legitimate CRM customer Sanvi S ready.",
    }


@router.post("/generate_pattern")
def generate_repeated_activity_pattern(db: Session = Depends(database.get_db)):
    """Generate multiple genuine activity events representing repeated customer request tasks.

    CRITICAL: This endpoint ONLY generates the raw activity event history.
    It does NOT discover or create any workflow.
    """
    events = simulate_customer_request_sessions(db, num_sessions=3)
    return {
        "status": "activity_events_recorded",
        "events_count": len(events),
        "sessions_count": 3,
        "pattern_preview": "READ_EMAIL -> DOWNLOAD_ATTACHMENT -> FIND_CUSTOMER -> UPDATE_CUSTOMER -> SEND_NOTIFICATION",
        "message": (
            f"Successfully recorded {len(events)} activity events across 3 independent sessions into database. "
            "No workflow has been discovered yet. "
            "Click 'Scan for Repetitions' to let the repetition detection algorithm analyze the history."
        ),
    }


@router.post("/run")
@router.post("/run_demo")
def run_demo(db: Session = Depends(database.get_db)):
    """Simulate file organization activity events and run genuine workflow discovery pipeline."""
    # 1. Ingest events
    events = simulate_file_organization_sessions(db, num_sessions=3)
    # 2. Run discovery & AI understanding through the real pipeline
    candidates = run_pipeline_discovery(db)
    return {
        "status": "pipeline_executed",
        "events_generated": len(events),
        "discovered_workflows": len(candidates),
        "workflows": [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "confidence": wf.confidence,
                "occurrences": wf.occurrences,
                "approved": wf.approved,
            }
            for wf in candidates
        ]
    }


@router.post("/run_crm")
def run_crm_demo(db: Session = Depends(database.get_db)):
    """Simulate customer service request events and run discovery."""
    events = simulate_customer_request_sessions(db, num_sessions=3)
    candidates = run_pipeline_discovery(db)
    return {
        "status": "crm_pipeline_executed",
        "events_generated": len(events),
        "discovered_workflows": len(candidates),
        "workflows": [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "confidence": wf.confidence,
                "occurrences": wf.occurrences,
                "approved": wf.approved,
            }
            for wf in candidates
        ]
    }
