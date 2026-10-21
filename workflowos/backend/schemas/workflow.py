# workflowos/backend/schemas/workflow.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Any
from datetime import datetime


class WorkflowCreate(BaseModel):
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = None
    trigger: Optional[Any] = None
    variables: Optional[List[Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]]
    conditions: Optional[List[Any]] = None
    failure_policy: Optional[Dict[str, Any]] = None


class WorkflowRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    trigger: Optional[Any] = None
    variables: Optional[List[Any]] = None
    actions: List[Dict[str, Any]]
    conditions: Optional[List[Any]] = None
    failure_policy: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    occurrences: int = 0
    approved: bool = False
    rejected: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
