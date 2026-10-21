# workflowos/backend/schemas/activity.py
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Any


class ActivityEventCreate(BaseModel):
    application: str = Field(..., description="Name of the application, e.g., File Explorer, Chrome")
    action: str = Field(..., description="Action name, e.g., CREATE_FILE, RENAME_FILE, MOVE_FILE")
    target: Optional[str] = Field(None, description="Target resource or identifier")
    session_id: Optional[str] = Field(None, description="Optional session id. If omitted, assigned automatically.")
    raw_data: Optional[Any] = Field(None, description="Raw event data/metadata")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class ActivityEventRead(BaseModel):
    id: int
    session_id: Optional[str]
    application: str
    action: str
    target: Optional[str]
    raw_data: Optional[Any]
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
