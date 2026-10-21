# workflowos/activity_agent/normalizer.py
"""Event normalizer for WorkFlowOS.

Converts raw OS telemetry (filesystem events, window focus changes, clipboard
activity) into canonical, structured ActivityEvent objects.

Ensures:
1. Canonical action naming (e.g. CREATE_FILE, RENAME_FILE, MOVE_FILE, ACTIVE_WINDOW).
2. Privacy filtering (no passwords, tokens, or raw sensitive contents).
3. Consistent metadata schema.
"""

from datetime import datetime
from typing import Dict, Any, Optional
import os
import re

# Action normalization mapping
ACTION_ALIASES = {
    # Filesystem
    "created": "CREATE_FILE",
    "file_created": "CREATE_FILE",
    "create_file": "CREATE_FILE",
    "directory_created": "CREATE_DIRECTORY",
    "create_directory": "CREATE_DIRECTORY",
    "moved": "MOVE_FILE",
    "file_moved": "MOVE_FILE",
    "move_file": "MOVE_FILE",
    "renamed": "RENAME_FILE",
    "file_renamed": "RENAME_FILE",
    "rename_file": "RENAME_FILE",
    "deleted": "DELETE_FILE",
    "file_deleted": "DELETE_FILE",
    "delete_file": "DELETE_FILE",
    "modified": "MODIFY_FILE",
    "file_modified": "MODIFY_FILE",
    "modify_file": "MODIFY_FILE",
    # Windows/Apps
    "active_window": "ACTIVE_WINDOW",
    "window_focus": "ACTIVE_WINDOW",
    "app_focus": "ACTIVE_WINDOW",
    "app_launch": "APP_LAUNCH",
    # Clipboard
    "clipboard_copy": "CLIPBOARD_COPY",
    "copy": "CLIPBOARD_COPY",
    # Generic Business Actions
    "read_email": "READ_EMAIL",
    "download_file": "DOWNLOAD_FILE",
    "download_attachment": "DOWNLOAD_ATTACHMENT",
    "find_customer": "FIND_CUSTOMER",
    "update_customer": "UPDATE_CUSTOMER",
    "send_notification": "SEND_NOTIFICATION",
    "open_spreadsheet": "OPEN_SPREADSHEET",
    "read_data": "READ_DATA",
    "transform_data": "TRANSFORM_DATA",
    "export_data": "EXPORT_DATA",
}

# Sensitive keyword patterns to sanitize from targets or metadata
SENSITIVE_PATTERNS = [
    re.compile(r"password|passwd|secret|token|api[_-]?key|auth|bearer|credential", re.IGNORECASE),
]

class EventNormalizer:
    """Normalizes raw OS activity events into canonical schema."""

    @staticmethod
    def normalize_action(action: str) -> str:
        """Map raw action name to canonical uppercase action name."""
        clean = action.strip().lower()
        return ACTION_ALIASES.get(clean, action.strip().upper())

    @staticmethod
    def sanitize_metadata(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Strip sensitive information from raw data/metadata."""
        if not data:
            return {}
        sanitized: Dict[str, Any] = {}
        for k, v in data.items():
            # Filter sensitive keys
            if any(p.search(str(k)) for p in SENSITIVE_PATTERNS):
                sanitized[k] = "[REDACTED]"
                continue
            if isinstance(v, str):
                # If value is too long or looks like a secret, truncate/sanitize
                if any(p.search(v) for p in SENSITIVE_PATTERNS):
                    sanitized[k] = "[REDACTED]"
                elif len(v) > 500:
                    sanitized[k] = v[:500] + "... [truncated]"
                else:
                    sanitized[k] = v
            elif isinstance(v, (int, float, bool, list, dict)):
                sanitized[k] = v
            else:
                sanitized[k] = str(v)
        return sanitized

    @classmethod
    def create_event_dict(
        cls,
        application: str,
        action: str,
        target: Optional[str] = None,
        session_id: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Produce a normalized event dictionary."""
        norm_action = cls.normalize_action(action)
        clean_target = (target or "").strip()
        if len(clean_target) > 300:
            clean_target = clean_target[:300] + "..."

        # Sanitize target if it has passwords
        if any(p.search(clean_target) for p in SENSITIVE_PATTERNS):
            clean_target = "[REDACTED_TARGET]"

        return {
            "application": application.strip() if application else "System",
            "action": norm_action,
            "target": clean_target if clean_target else None,
            "session_id": session_id,
            "timestamp": timestamp or datetime.utcnow(),
            "raw_data": cls.sanitize_metadata(raw_data),
        }
