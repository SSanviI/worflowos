# workflowos/backend/models/notification.py
from sqlalchemy import Column, Integer, String, DateTime, JSON
from ..database import Base
import datetime

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, nullable=False)  # e.g., slack, email
    message = Column(String, nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
