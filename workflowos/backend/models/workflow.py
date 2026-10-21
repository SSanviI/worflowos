# workflowos/backend/models/workflow.py
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, Float
from sqlalchemy.orm import relationship
from ..database import Base
import datetime

class Workflow(Base):
    __tablename__ = "workflows"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    trigger = Column(JSON, nullable=True)
    variables = Column(JSON, nullable=True)
    actions = Column(JSON, nullable=False)
    conditions = Column(JSON, nullable=True)
    failure_policy = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    occurrences = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    approved = Column(Boolean, default=False)
    rejected = Column(Boolean, default=False)
