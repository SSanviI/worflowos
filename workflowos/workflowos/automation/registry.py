# workflowos/automation/registry.py
"""Action Registry for WorkFlowOS Automation Engine.

Routes action types to their corresponding adapter implementations.
Prioritizes real OS/Filesystem operations, followed by API, App, and Browser integrations.
"""

from typing import Callable, Any, Tuple, Dict, Optional
from .adapters.filesystem import FileSystemAdapter
from .adapters.windows import WindowsAdapter
from .adapters.browser import BrowserAdapter
from .adapters.gmail import GmailAdapter
from .adapters.gmail_browser import browser_read_email, browser_download_attachment
from .adapters.slack import SlackAdapter
from .adapters.crm import CRMAdapter

# Registry mapping canonical uppercase action types to callable adapter functions
ACTION_REGISTRY: Dict[str, Callable[[Any, Dict[str, Any], Dict[str, Any]], Tuple[bool, Any, Optional[str]]]] = {
    # Filesystem & OS (REAL Windows side effects)
    "CREATE_FILE": FileSystemAdapter.create_file,
    "RENAME_FILE": FileSystemAdapter.rename_file,
    "MOVE_FILE": FileSystemAdapter.move_file,
    "DELETE_FILE": FileSystemAdapter.delete_file,
    "CREATE_DIRECTORY": FileSystemAdapter.create_directory,
    # Windows Desktop
    "APP_LAUNCH": WindowsAdapter.launch_application,
    "SYSTEM_NOTIFICATION": WindowsAdapter.send_system_notification,
    "ACTIVE_WINDOW": WindowsAdapter.focus_window,
    # Browser
    "OPEN_URL": BrowserAdapter.open_url,
    "HTTP_REQUEST": BrowserAdapter.http_request,
    # Email / Gmail (API-First with Browser Fallback)
    "READ_EMAIL": GmailAdapter.read_email,
    "DOWNLOAD_ATTACHMENT": GmailAdapter.download_attachment,
    "BROWSER_READ_EMAIL": browser_read_email,
    "BROWSER_DOWNLOAD_ATTACHMENT": browser_download_attachment,
    "DOWNLOAD_FILE": FileSystemAdapter.create_file,  # Generates/downloads real file locally
    # CRM (Local SQLite Database)
    "FIND_CUSTOMER": CRMAdapter.find_customer,
    "UPDATE_CUSTOMER": CRMAdapter.update_customer,
    # Notifications / Slack
    "SEND_NOTIFICATION": SlackAdapter.send_notification,
}


def get_action(action_type: str) -> Optional[Callable]:
    """Retrieve executable action callable by type name (case-insensitive)."""
    if not action_type:
        return None
    clean = action_type.strip().upper()
    return ACTION_REGISTRY.get(clean)


def list_registered_actions() -> list[str]:
    """Return list of all registered action types."""
    return sorted(list(ACTION_REGISTRY.keys()))
