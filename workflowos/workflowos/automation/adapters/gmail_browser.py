# workflowos/automation/adapters/gmail_browser.py
"""Real Gmail Browser Automation using Playwright.

This adapter launches a dedicated Chromium automation browser with a persistent
profile. The user logs into Gmail ONCE manually, and the session is reused for
all subsequent automation runs.

WorkFlowOS NEVER stores passwords. The user authenticates in the visible browser.

Key capabilities:
  - open_gmail()            → Navigate to Gmail inbox
  - find_email(subject)     → Locate an email by subject line
  - open_email(subject)     → Click into an email
  - read_email(subject)     → Extract visible email body text
  - download_attachment()   → Click attachment download, verify file on disk
  - close()                 → Clean shutdown of the browser
"""

import os
import time
import glob
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("workflowos.automation.gmail_browser")

# Persistent browser profile so Gmail stays logged in between runs
PROFILE_DIR = os.path.join(
    os.path.expanduser("~"), ".workflowos", "browser_profile"
)
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")


class GmailBrowserSession:
    """Manages a single Playwright browser session for Gmail automation."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started and self.page is not None

    def start(self, headless: bool = False) -> Dict[str, Any]:
        """Launch the automation browser with persistent profile.

        Args:
            headless: If True, run without visible window (for CI). Default False
                      so the user can see the browser and log in manually.
        """
        if self._started:
            return {"status": "already_running"}

        try:
            from playwright.sync_api import sync_playwright

            os.makedirs(PROFILE_DIR, exist_ok=True)
            os.makedirs(DOWNLOADS_DIR, exist_ok=True)

            self.playwright = sync_playwright().start()

            # Launch with persistent context — preserves cookies/sessions
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=headless,
                accept_downloads=True,
                viewport={"width": 1280, "height": 900},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )

            # Use existing or open new page
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = self.context.new_page()

            self._started = True
            logger.info("Gmail automation browser started with persistent profile")
            return {
                "status": "started",
                "profile_dir": PROFILE_DIR,
                "headless": headless,
            }

        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            self._cleanup()
            raise RuntimeError(f"Browser launch failed: {e}")

    def _cleanup(self):
        """Internal cleanup of browser resources."""
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        self.page = None
        self.context = None
        self.playwright = None
        self._started = False

    def close(self):
        """Shut down the browser cleanly."""
        self._cleanup()
        logger.info("Gmail automation browser closed")

    # ──────────────────────────────────────────────
    # Gmail Navigation
    # ──────────────────────────────────────────────

    def open_gmail(self) -> Dict[str, Any]:
        """Navigate to Gmail inbox. Returns status dict."""
        if not self.is_running:
            raise RuntimeError("Browser not started. Call start() first.")

        self.page.goto("https://mail.google.com/mail/u/0/#inbox", timeout=30000)
        self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(2)  # Allow Gmail JS to render

        current_url = self.page.url

        # Check if we landed on a login page
        if "accounts.google.com" in current_url:
            return {
                "status": "login_required",
                "message": "Please log into Gmail in the automation browser. "
                           "WorkFlowOS never stores your password.",
                "url": current_url,
            }

        # Check if we're in the inbox
        if "mail.google.com" in current_url:
            return {
                "status": "inbox_loaded",
                "url": current_url,
            }

        return {
            "status": "unknown_page",
            "url": current_url,
        }

    def check_login_status(self) -> Dict[str, Any]:
        """Check whether the user is currently logged into Gmail."""
        if not self.is_running:
            return {"logged_in": False, "reason": "browser_not_running"}

        current_url = self.page.url
        if "mail.google.com" in current_url and "accounts.google.com" not in current_url:
            return {"logged_in": True, "url": current_url}

        return {"logged_in": False, "url": current_url}

    def wait_for_login(self, timeout_seconds: int = 120) -> Dict[str, Any]:
        """Wait for the user to manually log in. Polls every 3 seconds."""
        if not self.is_running:
            raise RuntimeError("Browser not started.")

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            status = self.check_login_status()
            if status["logged_in"]:
                return {"status": "logged_in", "url": status["url"]}
            time.sleep(3)

        return {"status": "timeout", "message": f"Login not detected within {timeout_seconds}s"}

    # ──────────────────────────────────────────────
    # Email Search & Read
    # ──────────────────────────────────────────────

    def find_email(self, subject: str) -> Dict[str, Any]:
        """Find an email by subject line in Gmail using the search bar.

        Uses Gmail's built-in search to locate the email, which is the most
        robust approach against UI layout changes.
        """
        if not self.is_running:
            raise RuntimeError("Browser not started.")

        try:
            # Click the Gmail search bar
            search_input = self.page.locator('input[aria-label="Search mail"]')
            if not search_input.is_visible(timeout=5000):
                # Fallback: try other selectors
                search_input = self.page.locator('input[name="q"]')

            search_input.click()
            search_input.fill(f"subject:{subject}")
            search_input.press("Enter")

            # Wait for search results to load
            self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(2)

            # Look for email rows in the results
            # Gmail uses table rows with role="row" or <tr> elements
            email_rows = self.page.locator('tr.zA')  # Gmail's email row class
            count = email_rows.count()

            if count == 0:
                # Fallback: try finding by text content
                email_rows = self.page.locator(f'span:has-text("{subject}")')
                count = email_rows.count()

            if count > 0:
                return {
                    "status": "found",
                    "subject": subject,
                    "matches": count,
                }
            else:
                return {
                    "status": "not_found",
                    "subject": subject,
                    "matches": 0,
                }

        except Exception as e:
            return {
                "status": "error",
                "subject": subject,
                "error": str(e),
            }

    def open_email(self, subject: str) -> Dict[str, Any]:
        """Open the first email matching the subject."""
        if not self.is_running:
            raise RuntimeError("Browser not started.")

        try:
            # First search for the email
            find_result = self.find_email(subject)
            if find_result["status"] != "found":
                return {
                    "status": "not_found",
                    "subject": subject,
                    "error": f"Email with subject '{subject}' not found in inbox.",
                }

            # Click the first matching email row
            # Try multiple selectors for robustness
            clicked = False

            # Strategy 1: Click the email row by subject text span
            subject_spans = self.page.locator(f'span:has-text("{subject}")')
            if subject_spans.count() > 0:
                subject_spans.first.click()
                clicked = True

            if not clicked:
                # Strategy 2: Click first result row
                rows = self.page.locator('tr.zA')
                if rows.count() > 0:
                    rows.first.click()
                    clicked = True

            if not clicked:
                return {
                    "status": "click_failed",
                    "subject": subject,
                    "error": "Could not click on the email. Gmail UI may have changed.",
                }

            # Wait for email content to load
            self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(2)

            return {
                "status": "opened",
                "subject": subject,
                "url": self.page.url,
            }

        except Exception as e:
            return {
                "status": "error",
                "subject": subject,
                "error": str(e),
            }

    def read_email(self, subject: str) -> Dict[str, Any]:
        """Read the content of an email. Opens it first if necessary.

        Returns the visible email body text, sender, and attachment info.
        """
        if not self.is_running:
            raise RuntimeError("Browser not started.")

        try:
            # Open the email first
            open_result = self.open_email(subject)
            if open_result["status"] not in ("opened",):
                return {
                    "status": "cannot_read",
                    "error": open_result.get("error", "Failed to open email"),
                }

            time.sleep(1)

            # Extract email body text
            body_text = ""

            # Gmail email body selectors (multiple fallbacks)
            body_selectors = [
                'div[data-message-id] div.a3s',     # Standard Gmail body
                'div.a3s.aiL',                        # Gmail body variant
                'div[role="listitem"] div.a3s',       # Conversation view
                'div.ii.gt',                          # Another common Gmail body wrapper
            ]

            for selector in body_selectors:
                body_el = self.page.locator(selector)
                if body_el.count() > 0:
                    body_text = body_el.first.inner_text(timeout=5000)
                    if body_text.strip():
                        break

            if not body_text.strip():
                # Last resort: grab all visible text in the email view
                body_text = self.page.locator('div[role="main"]').inner_text(timeout=5000)

            # Check for attachments
            has_attachment = False
            attachment_selectors = [
                'div.aZo',                    # Attachment chip
                'span.aZo',                   # Attachment area
                'div[data-tooltip*="Download"]',
                'div.aQH',                    # Attachment container
                'a[download]',                # Download links
            ]

            for sel in attachment_selectors:
                if self.page.locator(sel).count() > 0:
                    has_attachment = True
                    break

            # Extract sender
            sender = ""
            sender_selectors = [
                'span.gD',           # Sender name
                'span[email]',       # Sender with email attribute
                'h3.iw span',        # Header sender
            ]
            for sel in sender_selectors:
                el = self.page.locator(sel)
                if el.count() > 0:
                    sender = el.first.inner_text(timeout=3000)
                    if sender.strip():
                        break

            return {
                "status": "read",
                "subject": subject,
                "sender": sender.strip(),
                "body_preview": body_text.strip()[:500],  # First 500 chars
                "body_length": len(body_text.strip()),
                "has_attachment": has_attachment,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    def download_attachment(self, subject: Optional[str] = None) -> Dict[str, Any]:
        """Download the first attachment from the currently open email.

        If subject is provided, opens that email first.
        Verifies the downloaded file actually exists on disk with non-zero size.
        """
        if not self.is_running:
            raise RuntimeError("Browser not started.")

        try:
            # If subject given, make sure that email is open
            if subject:
                read_result = self.read_email(subject)
                if read_result["status"] != "read":
                    return {
                        "status": "cannot_download",
                        "error": f"Could not read email: {read_result.get('error', 'unknown')}",
                    }
                if not read_result.get("has_attachment"):
                    return {
                        "status": "no_attachment",
                        "error": "Email does not appear to contain any attachments.",
                    }

            # Record existing downloads to detect new files
            existing_files = set(glob.glob(os.path.join(DOWNLOADS_DIR, "*")))

            # Try clicking the download button on the attachment
            download_clicked = False
            download_selectors = [
                'div[data-tooltip*="Download"]',      # Download tooltip button
                'div.aQH span[data-tooltip*="Download"]',
                'div.aZo a',                           # Attachment chip link
                'a[download]',                          # Generic download link
                'div[aria-label*="Download"]',          # ARIA labeled download
            ]

            for sel in download_selectors:
                els = self.page.locator(sel)
                if els.count() > 0:
                    # Use Playwright's download event listener
                    with self.page.expect_download(timeout=15000) as download_info:
                        els.first.click()
                    download = download_info.value

                    # Save the download to the Downloads folder
                    filename = download.suggested_filename or "attachment"
                    save_path = os.path.join(DOWNLOADS_DIR, filename)
                    download.save_as(save_path)
                    download_clicked = True

                    # Verify the file
                    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                        return {
                            "status": "downloaded",
                            "filename": filename,
                            "attachment_path": save_path,
                            "file_size_bytes": os.path.getsize(save_path),
                        }
                    else:
                        return {
                            "status": "download_failed",
                            "error": f"File was saved but is empty or missing: {save_path}",
                            "attachment_path": save_path,
                        }

            if not download_clicked:
                # Fallback: check if any new file appeared in Downloads
                time.sleep(3)
                new_files = set(glob.glob(os.path.join(DOWNLOADS_DIR, "*"))) - existing_files
                if new_files:
                    newest = max(new_files, key=os.path.getmtime)
                    return {
                        "status": "downloaded",
                        "filename": os.path.basename(newest),
                        "attachment_path": newest,
                        "file_size_bytes": os.path.getsize(newest),
                        "note": "Detected via filesystem monitoring",
                    }

                return {
                    "status": "no_download_button",
                    "error": "Could not find a clickable download button for the attachment.",
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }


# ──────────────────────────────────────────────────────────────
# Module-level singleton session
# ──────────────────────────────────────────────────────────────
_session: Optional[GmailBrowserSession] = None


def get_session() -> GmailBrowserSession:
    """Get or create the singleton browser session."""
    global _session
    if _session is None:
        _session = GmailBrowserSession()
    return _session


def close_session():
    """Close the singleton browser session."""
    global _session
    if _session is not None:
        _session.close()
        _session = None


# ──────────────────────────────────────────────────────────────
# Adapter functions matching BaseAdapter signature
# (db, params, context) -> (bool, result_data, error_msg)
# ──────────────────────────────────────────────────────────────

def browser_read_email(
    db: Any, params: Dict[str, Any], context: Dict[str, Any]
) -> Tuple[bool, Any, Optional[str]]:
    """READ_EMAIL via real Playwright browser automation.

    This is the adapter function registered in the action registry.
    It actually navigates Gmail, finds the email, opens it, and reads it.
    Returns FAILURE if the email cannot be found/read.
    """
    session = get_session()

    # Start browser if not running
    if not session.is_running:
        try:
            session.start(headless=False)
        except Exception as e:
            return False, {
                "action": "READ_EMAIL",
                "tier": "browser_automation",
                "status": "browser_launch_failed",
            }, f"Failed to launch automation browser: {e}"

    # Navigate to Gmail
    gmail_status = session.open_gmail()
    if gmail_status["status"] == "login_required":
        return False, {
            "action": "READ_EMAIL",
            "tier": "browser_automation",
            "status": "login_required",
            "message": gmail_status["message"],
        }, ("Gmail login required. Open the automation browser and log in manually. "
            "Then re-execute the workflow.")

    if gmail_status["status"] != "inbox_loaded":
        return False, {
            "action": "READ_EMAIL",
            "tier": "browser_automation",
            "status": gmail_status["status"],
        }, f"Gmail navigation failed: {gmail_status}"

    # Search for the email
    subject = (
        params.get("subject")
        or params.get("email_subject")
        or context.get("email_subject")
        or "WorkFlowOS Test Customer Request"
    )

    read_result = session.read_email(subject)

    if read_result["status"] != "read":
        return False, {
            "action": "READ_EMAIL",
            "tier": "browser_automation",
            "status": read_result["status"],
        }, f"Could not read email '{subject}': {read_result.get('error', 'unknown')}"

    # Store extracted data in execution context
    context["email_subject"] = subject
    context["email_sender"] = read_result.get("sender", "")
    context["email_body"] = read_result.get("body_preview", "")
    context["email_has_attachment"] = read_result.get("has_attachment", False)
    context["current_app"] = "Gmail (Browser Automation)"

    return True, {
        "action": "READ_EMAIL",
        "tier": "browser_automation",
        "status": "read",
        "subject": subject,
        "sender": read_result.get("sender", ""),
        "body_preview": read_result.get("body_preview", "")[:200],
        "has_attachment": read_result.get("has_attachment", False),
        "note": "REAL browser automation — email was actually read",
    }, None


def browser_download_attachment(
    db: Any, params: Dict[str, Any], context: Dict[str, Any]
) -> Tuple[bool, Any, Optional[str]]:
    """DOWNLOAD_ATTACHMENT via real Playwright browser automation.

    Actually clicks the download button in Gmail UI and verifies the file
    exists on disk with non-zero size.
    Returns FAILURE if the file is not found after download.
    """
    session = get_session()

    if not session.is_running:
        return False, {
            "action": "DOWNLOAD_ATTACHMENT",
            "tier": "browser_automation",
            "status": "browser_not_running",
        }, "Browser session is not running. Execute READ_EMAIL first."

    subject = (
        params.get("subject")
        or context.get("email_subject")
        or "WorkFlowOS Test Customer Request"
    )

    dl_result = session.download_attachment(subject=subject)

    if dl_result["status"] != "downloaded":
        return False, {
            "action": "DOWNLOAD_ATTACHMENT",
            "tier": "browser_automation",
            "status": dl_result["status"],
        }, f"Download failed: {dl_result.get('error', 'unknown')}"

    # Verify the file ACTUALLY exists
    attachment_path = dl_result.get("attachment_path", "")
    if not os.path.exists(attachment_path):
        return False, {
            "action": "DOWNLOAD_ATTACHMENT",
            "tier": "browser_automation",
            "status": "file_missing",
        }, f"Downloaded file does not exist on disk: {attachment_path}"

    file_size = os.path.getsize(attachment_path)
    if file_size == 0:
        return False, {
            "action": "DOWNLOAD_ATTACHMENT",
            "tier": "browser_automation",
            "status": "empty_file",
        }, f"Downloaded file is empty (0 bytes): {attachment_path}"

    # Store verified path in context for downstream steps
    context["attachment_path"] = attachment_path
    context["attachment_filename"] = dl_result.get("filename", "")
    context["attachment_size"] = file_size
    context["downloads_dir"] = DOWNLOADS_DIR

    return True, {
        "action": "DOWNLOAD_ATTACHMENT",
        "tier": "browser_automation",
        "status": "downloaded",
        "attachment_path": attachment_path,
        "filename": dl_result.get("filename", ""),
        "file_size_bytes": file_size,
        "note": "REAL download — file verified on disk",
    }, None
