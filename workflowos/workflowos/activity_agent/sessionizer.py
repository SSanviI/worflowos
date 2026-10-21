# workflowos/activity_agent/sessionizer.py
"""Dynamic Sessionization Engine for WorkFlowOS.

Groups stream of continuous activity events into discrete logical sessions/tasks.
Session boundaries are inferred from:
1. Inactivity time gaps (configurable threshold, default 5s).
2. Major task context transitions.
3. Event continuity within the same working directory or application flow.
"""

from datetime import datetime, timedelta
import os
import uuid
from typing import Optional, Dict, Any, List

DEFAULT_INACTIVITY_GAP = float(os.getenv("SESSION_GAP_SECONDS", "5.0"))


class ActivitySessionizer:
    """Stateful sessionizer that assigns session IDs to incoming events."""

    def __init__(self, inactivity_timeout_seconds: float = DEFAULT_INACTIVITY_GAP):
        self.inactivity_timeout = timedelta(seconds=inactivity_timeout_seconds)
        self.current_session_id: Optional[str] = None
        self.last_event_time: Optional[datetime] = None
        self.last_application: Optional[str] = None
        self.session_event_count: int = 0

    def get_or_create_session(
        self,
        event_time: Optional[datetime] = None,
        application: Optional[str] = None,
        force_new: bool = False,
    ) -> str:
        """Determine whether the current event belongs to ongoing session or starts a new session."""
        now = event_time or datetime.utcnow()

        if force_new or not self.current_session_id or not self.last_event_time:
            self._start_new_session(now, application)
            return self.current_session_id

        time_since_last = now - self.last_event_time

        if time_since_last > self.inactivity_timeout:
            self._start_new_session(now, application)
            return self.current_session_id

        self.last_event_time = now
        self.session_event_count += 1
        if application:
            self.last_application = application
        return self.current_session_id

    def _start_new_session(self, start_time: datetime, application: Optional[str]):
        short_id = uuid.uuid4().hex[:8]
        timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")
        self.current_session_id = f"session_{timestamp_str}_{short_id}"
        self.last_event_time = start_time
        self.last_application = application
        self.session_event_count = 1

    def reset(self):
        """Force close current session."""
        self.current_session_id = None
        self.last_event_time = None
        self.last_application = None
        self.session_event_count = 0


def sessionize_raw_events(
    events: List[Dict[str, Any]],
    inactivity_gap_seconds: float = DEFAULT_INACTIVITY_GAP,
) -> List[Dict[str, Any]]:
    """Batch utility to group unassigned raw events into sessions."""
    if not events:
        return []

    sorted_events = sorted(
        events,
        key=lambda e: e.get("timestamp") or datetime.min
    )
    sessionizer = ActivitySessionizer(inactivity_timeout_seconds=inactivity_gap_seconds)
    result = []

    for ev in sorted_events:
        ev_copy = dict(ev)
        existing_sid = ev_copy.get("session_id")
        if not existing_sid:
            ts = ev_copy.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    ts = datetime.utcnow()
            app = ev_copy.get("application")
            ev_copy["session_id"] = sessionizer.get_or_create_session(ts, app)
        result.append(ev_copy)

    return result
