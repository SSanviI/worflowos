# workflowos/automation/adapters/windows.py
"""Windows OS Automation Adapter.

Executes real desktop-level operations on Windows:
- Application launch
- System notifications
"""

import os
import subprocess
import logging
from typing import Dict, Any, Tuple, Optional
from .base import BaseAdapter
import win32gui
import win32process
try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("workflowos.automation.windows")


class WindowsAdapter(BaseAdapter):
    """Executes Windows system-level automation actions."""

    @classmethod
    def launch_application(
        cls,
        db: Any,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str]]:
        """Launch an application or process on Windows."""
        resolved = cls.resolve_params(params, context)
        app_name = resolved.get("app") or resolved.get("application") or resolved.get("command")
        if not app_name:
            return False, None, "No application or command specified"

        try:
            # Safe process spawn
            proc = subprocess.Popen(app_name, shell=True)
            context["launched_pid"] = proc.pid
            return True, {
                "action": "APP_LAUNCH",
                "application": app_name,
                "pid": proc.pid,
                "status": "launched"
            }, None
        except Exception as e:
            return False, None, f"Failed to launch {app_name}: {str(e)}"

    @classmethod
    def send_system_notification(
        cls,
        db: Any,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str]]:
        """Send a Windows notification or console log."""
        resolved = cls.resolve_params(params, context)
        message = resolved.get("message") or resolved.get("text") or "WorkFlowOS Action Completed"
        title = resolved.get("title", "WorkFlowOS")

        logger.info(f"[Windows Notification] {title}: {message}")
        context["last_notification"] = message
        return True, {
            "action": "SYSTEM_NOTIFICATION",
            "title": title,
            "message": message,
            "status": "dispatched"
        }, None
    @classmethod
    def focus_window(
        cls,
        db: Any,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str]]:
        """Bring a window to the foreground based on title or app name.

        Parameters:
            params may include:
                - title: partial or full window title to match.
                - app_name: process name (without .exe) if title not provided.
        """
        resolved = cls.resolve_params(params, context)
        target_title = resolved.get("title")
        target_app = resolved.get("app_name") or resolved.get("application")

        if not win32gui:
            return False, None, "win32gui not available"

        # If no explicit target is provided, attempt to use previously captured window info from context
        if not target_title and not target_app:
            target_title = context.get("active_window_title")
            target_app = context.get("active_window_app")
            if not target_title and not target_app:
                logger.debug("ACTIVE_WINDOW: No target or context provided, skipping window focus.")
                return True, {"action": "ACTIVE_WINDOW", "title": None}, None
        else:
            matched_hwnd = None
            matched_info: Dict[str, str] = {}

        def enum_handler(hwnd, _):
            nonlocal matched_hwnd, matched_info
            if not win32gui.IsWindowVisible(hwnd):
                return
            win_title = win32gui.GetWindowText(hwnd)
            if not win_title:
                return
            # Title match takes precedence
            if target_title and target_title.lower() in win_title.lower():
                matched_hwnd = hwnd
                matched_info = {"title": win_title}
                return
            # Fallback to process name match
            if target_app and psutil:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid)
                    proc_name = proc.name().replace('.exe', '')
                    if target_app.lower() == proc_name.lower():
                        matched_hwnd = hwnd
                        matched_info = {"title": win_title, "app_name": proc_name}
                except Exception:
                    pass

        # If we still haven't found a matching window after enumeration, return failure.
        if matched_hwnd is None:
            return False, None, f"No window matching title='{target_title}' or app_name='{target_app}'"
        try:
            win32gui.SetForegroundWindow(matched_hwnd)
            # Store context for later steps
            context["active_window_title"] = matched_info.get("title")
            if "app_name" in matched_info:
                context["active_window_app"] = matched_info["app_name"]
            return True, {"action": "ACTIVE_WINDOW", **matched_info}, None
        except Exception as e:
            return False, None, f"Failed to focus window: {str(e)}"

