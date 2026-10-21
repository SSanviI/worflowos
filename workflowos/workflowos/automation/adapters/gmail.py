# workflowos/automation/adapters/gmail.py
"""Real Gmail Adapter supporting API-First Automation with Browser Fallback.

Priority Order:
1. Gmail API (OAuth 2.0)
2. Playwright Browser Automation Fallback
"""

import os
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from .base import BaseAdapter
from .gmail_browser import browser_read_email as playwright_read_email
from .gmail_browser import browser_download_attachment as playwright_download_attachment

logger = logging.getLogger("workflowos.automation.gmail")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

_INNER_DIR = Path(__file__).resolve().parent.parent.parent
_ROOT_DIR = _INNER_DIR.parent

CONFIG_DIR = Path.home() / ".workflowos"
TOKEN_PATHS = [
    CONFIG_DIR / "gmail_token.json",
    Path("token.json"),
    Path("gmail_token.json"),
    _ROOT_DIR / "token.json",
    _ROOT_DIR / "gmail_token.json",
    _INNER_DIR / "token.json",
    _INNER_DIR / "gmail_token.json",
]
CREDENTIAL_PATHS = [
    CONFIG_DIR / "credentials.json",
    Path("credentials.json"),
    Path("credentials.json.json"),
    Path("client_secret.json"),
    _ROOT_DIR / "credentials.json",
    _ROOT_DIR / "credentials.json.json",
    _INNER_DIR / "credentials.json",
]
DOWNLOADS_DIR = Path.home() / "Downloads"


def get_gmail_credentials():
    """Retrieve or refresh valid Google OAuth 2.0 credentials."""
    creds = None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        return None

    # 1. Try existing token files
    for token_path in TOKEN_PATHS:
        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
                break
            except Exception as e:
                logger.warning(f"Failed to load token from {token_path}: {e}")

    # 2. Check environment variables
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")

    if not creds and client_id and client_secret and refresh_token:
        try:
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES,
            )
        except Exception as e:
            logger.warning(f"Failed to create credentials from environment: {e}")

    # 3. Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            for token_path in TOKEN_PATHS:
                if token_path.parent.exists():
                    token_path.write_text(creds.to_json())
                    break
        except Exception as e:
            logger.error(f"Failed refreshing Gmail OAuth token: {e}")
            creds = None

    if creds and creds.valid:
        return creds

    return None


def get_gmail_service():
    """Build authorized Gmail API service."""
    creds = get_gmail_credentials()
    if not creds:
        return None
    try:
        from googleapiclient.discovery import build
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.error(f"Failed building Gmail service: {e}")
        return None


def check_gmail_auth_status() -> Dict[str, Any]:
    """Check status of Gmail integration."""
    creds = get_gmail_credentials()
    if creds and creds.valid:
        return {
            "configured": True,
            "mode": "REAL_API",
            "status": "authenticated",
            "message": "Gmail OAuth 2.0 connected and authenticated.",
        }

    has_credentials_file = any(p.exists() for p in CREDENTIAL_PATHS)
    return {
        "configured": False,
        "mode": "CREDENTIALS_REQUIRED",
        "status": "unauthenticated",
        "has_credentials_file": has_credentials_file,
        "message": (
            "Gmail OAuth credentials not configured. "
            "Place credentials.json in project root or run setup_gmail_oauth.py."
        ),
    }


def extract_email_payload(payload: Dict[str, Any]) -> Tuple[str, bool, Optional[str], Optional[str], Optional[str], int]:
    """Recursively traverse MIME parts to extract plain text body and attachment details.

    Returns:
        (body_text, has_attachment, attachment_filename, attachment_id, attachment_inline_data, attachment_size)
    """
    body_text_parts = []
    html_text_parts = []
    attachments = []

    def _walk(part):
        mime = part.get("mimeType", "")
        filename = part.get("filename", "")
        body = part.get("body", {})

        att_id = body.get("attachmentId")
        inline_data = body.get("data")
        size = body.get("size", 0)

        if filename:
            attachments.append({
                "filename": filename,
                "attachment_id": att_id,
                "inline_data": inline_data,
                "mime_type": mime,
                "size": size,
            })

        if mime == "text/plain" and inline_data and not filename:
            try:
                decoded = base64.urlsafe_b64decode(inline_data).decode("utf-8", errors="replace")
                body_text_parts.append(decoded)
            except Exception:
                pass
        elif mime == "text/html" and inline_data and not filename:
            try:
                decoded = base64.urlsafe_b64decode(inline_data).decode("utf-8", errors="replace")
                html_text_parts.append(decoded)
            except Exception:
                pass

        for sub in part.get("parts", []):
            _walk(sub)

    _walk(payload)

    body_text = "\n".join(body_text_parts).strip()
    if not body_text and html_text_parts:
        body_text = "\n".join(html_text_parts).strip()

    has_attachment = len(attachments) > 0
    att_filename = attachments[0]["filename"] if has_attachment else None
    att_id = attachments[0]["attachment_id"] if has_attachment else None
    att_inline = attachments[0]["inline_data"] if has_attachment else None
    att_size = attachments[0]["size"] if has_attachment else 0

    return body_text, has_attachment, att_filename, att_id, att_inline, att_size


class GmailAdapter(BaseAdapter):
    """API-First Gmail Adapter with Browser Fallback."""

    @classmethod
    def read_email(
        cls,
        db: Any,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str]]:
        resolved = cls.resolve_params(params, context)
        service = get_gmail_service()

        subject = (
            resolved.get("subject")
            or resolved.get("email_subject")
            or context.get("email_subject")
            or ""
        )

        # 1. PRIORITY 1: REAL GMAIL API
        if service:
            try:
                messages = []
                # First try explicit subject query if a custom subject was provided
                if subject and subject.strip() and subject != "WorkFlowOS Test Customer Request":
                    query = f'subject:"{subject}"'
                    results = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
                    messages = results.get("messages", [])

                # If subject is "WorkFlowOS Test Customer Request" or exact subject match, search it
                if not messages and subject:
                    query = f'subject:"{subject}"'
                    results = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
                    messages = results.get("messages", [])

                # If no messages matched the query, search for any real email with attachments
                if not messages:
                    results = service.users().messages().list(userId="me", q="has:attachment", maxResults=5).execute()
                    messages = results.get("messages", [])

                # If still no messages with attachments, fetch the most recent inbox messages
                if not messages:
                    results = service.users().messages().list(userId="me", maxResults=5).execute()
                    messages = results.get("messages", [])

                if not messages:
                    # Gmail API is connected but inbox is empty
                    context["current_app"] = "Gmail API"
                    return True, {
                        "action": "READ_EMAIL",
                        "connector": "Gmail API",
                        "mode": "REAL_API",
                        "status": "no_messages_found",
                        "subject": subject,
                        "message": "Gmail API connected. No emails found in inbox.",
                        "inbox_accessible": True,
                    }, None

                msg_id = messages[0]["id"]
                message = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

                headers = message.get("payload", {}).get("headers", [])
                header_dict = {h["name"].lower(): h["value"] for h in headers}

                email_subject = header_dict.get("subject", subject or "No Subject")
                sender = header_dict.get("from", "Unknown Sender")
                snippet = message.get("snippet", "")

                payload = message.get("payload", {})
                body_text, has_attachment, att_filename, att_id, att_inline, att_size = extract_email_payload(payload)
                if not body_text:
                    body_text = snippet

                context["email_subject"] = email_subject
                context["email_sender"] = sender
                context["email_body"] = body_text
                context["gmail_message_id"] = msg_id
                context["has_attachment"] = has_attachment
                context["attachment_id"] = att_id
                context["attachment_filename"] = att_filename or "customer_request.txt"
                context["attachment_inline_data"] = att_inline
                context["attachment_size"] = att_size
                context["current_app"] = "Gmail API"

                return True, {
                    "action": "READ_EMAIL",
                    "connector": "Gmail API",
                    "mode": "REAL_API",
                    "status": "SUCCESS",
                    "message_id": msg_id,
                    "subject": email_subject,
                    "sender": sender,
                    "body_preview": body_text[:200],
                    "has_attachment": has_attachment,
                    "attachment_filename": att_filename,
                    "attachment_size_bytes": att_size,
                }, None

            except Exception as e:
                logger.warning(f"Gmail API read failed, attempting browser fallback: {e}")

        # 2. PRIORITY 2: PLAYWRIGHT BROWSER FALLBACK
        try:
            logger.info("Gmail API unconfigured or failed. Attempting Playwright browser fallback...")
            bw_success, bw_result, bw_err = playwright_read_email(db, params, context)
            if bw_success:
                if isinstance(bw_result, dict):
                    bw_result["mode"] = "BROWSER_FALLBACK"
                    bw_result["connector"] = "Playwright Browser"
                return True, bw_result, None
        except Exception as bw_e:
            logger.warning(f"Playwright browser fallback failed: {bw_e}")

        # If both primary API and browser fallback cannot proceed:
        auth_status = check_gmail_auth_status()
        error_status = "credentials_required" if not auth_status["configured"] else "read_failed"
        return False, {
            "action": "READ_EMAIL",
            "connector": "Gmail API",
            "mode": "REAL_API",
            "status": error_status,
            "message": auth_status["message"],
        }, auth_status["message"]

    @classmethod
    def download_attachment(
        cls,
        db: Any,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str]]:
        resolved = cls.resolve_params(params, context)
        service = get_gmail_service()

        msg_id = context.get("gmail_message_id")
        attachment_id = context.get("attachment_id")
        filename = context.get("attachment_filename") or "customer_request.txt"

        # 1. PRIORITY 1: REAL GMAIL API
        if service:
            # If msg_id is not in context or doesn't have an attachment, auto-discover the latest email with an attachment
            if not msg_id or not (attachment_id or context.get("attachment_inline_data")):
                try:
                    att_res = service.users().messages().list(userId="me", q="has:attachment", maxResults=1).execute()
                    att_msgs = att_res.get("messages", [])
                    if att_msgs:
                        msg_id = att_msgs[0]["id"]
                        msg_full = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
                        _, has_att, att_fn, att_i, att_inl, att_s = extract_email_payload(msg_full.get("payload", {}))
                        if has_att:
                            attachment_id = att_i
                            filename = att_fn or filename
                            context["attachment_inline_data"] = att_inl
                            context["gmail_message_id"] = msg_id
                            context["attachment_id"] = att_i
                            context["attachment_filename"] = filename
                            context["attachment_size"] = att_s
                except Exception as e:
                    logger.warning(f"Could not auto-discover email with attachment: {e}")

            if msg_id and (attachment_id or context.get("attachment_inline_data")):
                try:
                    if attachment_id:
                        attachment = (
                            service.users()
                            .messages()
                            .attachments()
                            .get(userId="me", messageId=msg_id, id=attachment_id)
                            .execute()
                        )
                        file_data = base64.urlsafe_b64decode(attachment["data"])
                    else:
                        file_data = base64.urlsafe_b64decode(context["attachment_inline_data"])

                    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
                    target_path = DOWNLOADS_DIR / filename
                    target_path.write_bytes(file_data)

                    if target_path.exists() and target_path.stat().st_size > 0:
                        context["attachment_path"] = str(target_path.resolve())
                        context["attachment_filename"] = filename
                        context["attachment_size"] = target_path.stat().st_size

                        return True, {
                            "action": "DOWNLOAD_ATTACHMENT",
                            "connector": "Gmail API",
                            "mode": "REAL_API",
                            "status": "SUCCESS",
                            "attachment_path": str(target_path.resolve()),
                            "filename": filename,
                            "file_size_bytes": target_path.stat().st_size,
                            "verified": True,
                        }, None

                except Exception as e:
                    logger.warning(f"Gmail API attachment download failed: {e}")

        # 2. PRIORITY 2: PLAYWRIGHT BROWSER FALLBACK
        try:
            bw_success, bw_result, bw_err = playwright_download_attachment(db, params, context)
            if bw_success:
                if isinstance(bw_result, dict):
                    bw_result["mode"] = "BROWSER_FALLBACK"
                    bw_result["connector"] = "Playwright Browser"
                return True, bw_result, None
        except Exception as bw_e:
            logger.warning(f"Browser attachment download fallback failed: {bw_e}")

        auth_status = check_gmail_auth_status()
        return False, {
            "action": "DOWNLOAD_ATTACHMENT",
            "connector": "Gmail API",
            "mode": "REAL_API",
            "status": "download_failed",
        }, f"Gmail attachment download failed. {auth_status['message']}"
