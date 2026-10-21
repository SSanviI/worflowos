# workflowos/backend/models/activity.py
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base
import datetime

class ActivityEvent(Base):
    __tablename__ = "activity_events"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    session_id = Column(String, index=True)
    application = Column(String, index=True)
    action = Column(String, index=True)
    target = Column(String, nullable=True)
    raw_data = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<ActivityEvent {self.id} {self.application}:{self.action}>"
