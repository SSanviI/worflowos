# workflowos/automation/adapters/browser.py
"""Browser Automation Adapter for WorkFlowOS."""

import os
import webbrowser
import requests
from typing import Dict, Any, Tuple, Optional
from .base import BaseAdapter


class BrowserAdapter(BaseAdapter):
    """Executes browser navigation and automated web queries."""

    @classmethod
    def open_url(
        cls,
        db: Any,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str]]:
        resolved = cls.resolve_params(params, context)
        url = resolved.get("url")
        if not url:
            return False, None, "No URL provided for browser open"

        try:
            webbrowser.open(url)
            context["current_url"] = url
            return True, {"action": "OPEN_URL", "url": url, "status": "opened"}, None
        except Exception as e:
            return False, None, f"Failed to open browser URL {url}: {str(e)}"

    @classmethod
    def http_request(
        cls,
        db: Any,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str]]:
        resolved = cls.resolve_params(params, context)
        url = resolved.get("url")
        method = resolved.get("method", "GET").upper()
        if not url:
            return False, None, "No URL specified for HTTP request"

        try:
            resp = requests.request(method, url, timeout=10)
            context["http_status"] = resp.status_code
            context["http_body"] = resp.text[:1000]
            return True, {
                "action": "HTTP_REQUEST",
                "status_code": resp.status_code,
                "url": url,
            }, None
        except Exception as e:
            return False, None, f"HTTP request failed: {str(e)}"
