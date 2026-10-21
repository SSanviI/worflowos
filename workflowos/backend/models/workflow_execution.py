# workflowos/backend/models/workflow_execution.py
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from ..database import Base
import datetime

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    execution_id = Column(String, unique=True, index=True, default=lambda: f"exec_{int(datetime.datetime.utcnow().timestamp())}")
    status = Column(String, default="pending")  # pending, running, success, failure
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    finish_time = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(String, nullable=True)

    workflow = relationship("Workflow", backref="executions")

class ExecutionStep(Base):
    __tablename__ = "execution_steps"
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("workflow_executions.id"), nullable=False)
    action_id = Column(String, nullable=False)
    connector = Column(String, nullable=True)  # Gmail API, Local CRM DB, Slack Webhook, Playwright Browser, FileSystem
    mode = Column(String, nullable=True)       # REAL_API, REAL_DATABASE, REAL_SLACK, LOCAL_FALLBACK, BROWSER_FALLBACK
    status = Column(String, default="pending")  # pending, success, failure
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    finish_time = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(String, nullable=True)

    execution = relationship("WorkflowExecution", backref="steps")
