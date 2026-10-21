# workflowos/backend/models/learning.py
"""Feedback and learning persistence model for WorkFlowOS."""

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, JSON
from ..database import Base
import datetime


class WorkflowFeedback(Base):
    __tablename__ = "workflow_feedback"
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    event_type = Column(String, index=True)  # "execution_success", "execution_failure", "approval", "rejection"
    action_id = Column(String, nullable=True)
    action_type = Column(String, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
