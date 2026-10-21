# workflowos/backend/api/events.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from .. import models, database
from ..schemas import activity
from ...activity_agent.normalizer import EventNormalizer
from ...activity_agent.sessionizer import ActivitySessionizer

router = APIRouter()
_api_sessionizer = ActivitySessionizer(inactivity_timeout_seconds=30.0)


@router.post("/", response_model=activity.ActivityEventRead)
def create_event(event: activity.ActivityEventCreate, db: Session = Depends(database.get_db)):
    """Ingest a single activity event. Automatically normalizes and sessionizes if needed."""
    norm_dict = EventNormalizer.create_event_dict(
        application=event.application,
        action=event.action,
        target=event.target,
        session_id=event.session_id,
        raw_data=event.raw_data,
        timestamp=event.timestamp or datetime.utcnow(),
    )

    # Auto-assign session_id if missing
    if not norm_dict.get("session_id"):
        norm_dict["session_id"] = _api_sessionizer.get_or_create_session(
            event_time=norm_dict["timestamp"],
            application=norm_dict["application"],
        )

    db_event = models.activity.ActivityEvent(
        session_id=norm_dict["session_id"],
        application=norm_dict["application"],
        action=norm_dict["action"],
        target=norm_dict["target"],
        raw_data=norm_dict["raw_data"],
        timestamp=norm_dict["timestamp"],
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@router.get("/", response_model=List[activity.ActivityEventRead])
def list_events(
    skip: int = 0,
    limit: int = 200,
    session_id: Optional[str] = None,
    db: Session = Depends(database.get_db)
):
    """List recorded activity events in chronological order."""
    query = db.query(models.activity.ActivityEvent)
    if session_id:
        query = query.filter(models.activity.ActivityEvent.session_id == session_id)
    return query.order_by(models.activity.ActivityEvent.timestamp.desc()).offset(skip).limit(limit).all()


@router.delete("/clear")
def clear_events(db: Session = Depends(database.get_db)):
    """Clear activity events."""
    db.query(models.activity.ActivityEvent).delete()
    db.commit()
    return {"status": "events cleared"}
