# workflowos/automation/adapters/__init__.py
from .base import BaseAdapter
from .filesystem import FileSystemAdapter
from .windows import WindowsAdapter
from .browser import BrowserAdapter
from .gmail import GmailAdapter
from .slack import SlackAdapter
from .crm import CRMAdapter

__all__ = [
    "BaseAdapter",
    "FileSystemAdapter",
    "WindowsAdapter",
    "BrowserAdapter",
    "GmailAdapter",
    "SlackAdapter",
    "CRMAdapter",
]
