# workflowos/activity_agent/manager.py
"""Activity Agent lifecycle manager and database ingestion coordinator.

Provides a unified interface for starting, stopping, configuring, and querying
the status of the Windows Activity Agent from the FastAPI backend or CLI.
"""

import os
import logging
from typing import Optional, List, Dict, Any

from .agent import DesktopActivityAgent
from ..backend.database import SessionLocal
from ..backend.models.activity import ActivityEvent

logger = logging.getLogger("workflowos.activity_agent.manager")

# Default test directory on Windows
DEFAULT_TEST_INPUT = os.path.abspath(r"C:\WorkFlowOS_Test\Input")
DEFAULT_TEST_OUTPUT = os.path.abspath(r"C:\WorkFlowOS_Test\Output")


class ActivityAgentManager:
    """Manages the lifecycle of the DesktopActivityAgent and persists events to the database."""

    def __init__(self):
        self._agent: Optional[DesktopActivityAgent] = None
        self._monitored_paths: List[str] = [DEFAULT_TEST_INPUT, DEFAULT_TEST_OUTPUT]

    def _on_event_received(self, event_data: Dict[str, Any]):
        """Persist normalized event to SQLite database."""
        try:
            db = SessionLocal()
            try:
                db_event = ActivityEvent(
                    session_id=event_data.get("session_id"),
                    application=event_data.get("application", "System"),
                    action=event_data.get("action", "UNKNOWN"),
                    target=event_data.get("target"),
                    raw_data=event_data.get("raw_data"),
                    timestamp=event_data.get("timestamp"),
                )
                db.add(db_event)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to persist event: {e}")

    def get_agent(self) -> DesktopActivityAgent:
        if self._agent is None:
            self._agent = DesktopActivityAgent(
                monitored_paths=list(self._monitored_paths),
                event_callback=self._on_event_received,
            )
        return self._agent

    def start(self, monitored_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Start activity observation."""
        if monitored_paths:
            for p in monitored_paths:
                if p not in self._monitored_paths:
                    self._monitored_paths.append(os.path.abspath(p))

        agent = self.get_agent()
        for p in self._monitored_paths:
            agent.add_monitored_path(p)

        if not agent.is_running:
            agent.start()

        return self.get_status()

    def stop(self) -> Dict[str, Any]:
        """Stop activity observation."""
        if self._agent and self._agent.is_running:
            self._agent.stop()
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Return current status of observation agent."""
        is_running = self._agent.is_running if self._agent else False
        return {
            "status": "observing" if is_running else "paused",
            "is_running": is_running,
            "monitored_paths": list(self._monitored_paths),
        }

    def add_path(self, path: str):
        abs_path = os.path.abspath(path)
        if abs_path not in self._monitored_paths:
            self._monitored_paths.append(abs_path)
            if self._agent:
                self._agent.add_monitored_path(abs_path)


# Global singleton instance
agent_manager = ActivityAgentManager()
