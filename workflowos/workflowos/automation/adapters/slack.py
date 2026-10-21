# workflowos/automation/adapters/slack.py
"""Slack Adapter for WorkFlowOS.

Supports two automation modes:
1. REAL_SLACK: Posts live rich notifications to configured Slack Webhook.
2. LOCAL_FALLBACK: Logs and dispatches local notification when Slack is unconfigured.

Configuration (via environment variables or .env file):
  SLACK_WEBHOOK_URL  - Slack Incoming Webhook URL (required for REAL_SLACK mode).
                       Obtain from: https://api.slack.com/messaging/webhooks
  SLACK_STRICT_MODE  - Set to "true" to FAIL instead of silently falling back when
                       the webhook is not configured. Use in integration tests.

Example .env entry:
  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
"""

import os
import logging
import requests
from typing import Dict, Any, Tuple, Optional
from .base import BaseAdapter

logger = logging.getLogger("workflowos.automation.slack")


class SlackAdapter(BaseAdapter):
    """Executes Slack notifications via Webhook or Local Fallback."""

    @classmethod
    def send_notification(
        cls,
        db: Any,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str]]:
        resolved = cls.resolve_params(params, context)

        # Read from environment at call-time (supports runtime .env loading)
        webhook_url = os.getenv("SLACK_WEBHOOK_URL") or resolved.get("webhook_url")
        strict_mode = os.getenv("SLACK_STRICT_MODE", "").lower() in ("1", "true", "yes")

        # Build informative workflow notification message
        customer = context.get("customer_name", "Test Customer")
        email = context.get("customer_email", "")
        customer_str = f"{customer} ({email})" if email else customer
        request_sub = context.get("email_subject", "WorkFlowOS Customer Request")
        attachment = context.get("attachment_path", context.get("attachment_filename", "customer_request.txt"))
        exec_id = context.get("execution_id", "exec_local")
        wf_name = context.get("workflow_name", "Process Customer Request & CRM Update")

        notification_text = (
            f"\u26a1 *WorkFlowOS Workflow Execution Complete*\n"
            f"\u2022 *Workflow:* {wf_name}\n"
            f"\u2022 *Execution ID:* `{exec_id}`\n"
            f"\u2022 *Customer:* {customer_str}\n"
            f"\u2022 *Request:* {request_sub}\n"
            f"\u2022 *Attachment:* `{attachment}`\n"
            f"\u2022 *Status:* SUCCESS"
        )

        # ── REAL_SLACK MODE ──────────────────────────────────────────────────
        if webhook_url:
            try:
                logger.info("[REAL_SLACK] Posting notification to Slack webhook ...")
                resp = requests.post(
                    webhook_url,
                    json={"text": notification_text},
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )
                if resp.status_code in (200, 201):
                    logger.info("[REAL_SLACK] Slack notification delivered successfully.")
                    return True, {
                        "action": "SEND_NOTIFICATION",
                        "connector": "Slack Webhook",
                        "mode": "REAL_SLACK",
                        "status": "SUCCESS",
                        "delivered_to": "Slack Channel",
                        "http_status": resp.status_code,
                        "message": notification_text,
                    }, None
                else:
                    err_msg = f"Slack webhook returned HTTP {resp.status_code}: {resp.text}"
                    logger.error(f"[REAL_SLACK] {err_msg}")
                    return False, {
                        "action": "SEND_NOTIFICATION",
                        "connector": "Slack Webhook",
                        "mode": "REAL_SLACK",
                        "status": "webhook_error",
                        "http_status": resp.status_code,
                        "response_body": resp.text,
                    }, err_msg

            except requests.exceptions.ConnectionError as e:
                err_msg = f"Cannot reach Slack: Connection refused or DNS failure. Details: {e}"
                logger.error(f"[REAL_SLACK] {err_msg}")
                return False, {
                    "action": "SEND_NOTIFICATION",
                    "connector": "Slack Webhook",
                    "mode": "REAL_SLACK",
                    "status": "connection_error",
                }, err_msg

            except requests.exceptions.Timeout as e:
                err_msg = f"Slack webhook request timed out after 10s. Details: {e}"
                logger.error(f"[REAL_SLACK] {err_msg}")
                return False, {
                    "action": "SEND_NOTIFICATION",
                    "connector": "Slack Webhook",
                    "mode": "REAL_SLACK",
                    "status": "timeout_error",
                }, err_msg

            except Exception as e:
                err_msg = f"Unexpected error posting to Slack: {e}"
                logger.error(f"[REAL_SLACK] {err_msg}")
                return False, {
                    "action": "SEND_NOTIFICATION",
                    "connector": "Slack Webhook",
                    "mode": "REAL_SLACK",
                    "status": "unexpected_error",
                }, err_msg

        # ── STRICT MODE: No webhook → FAIL immediately ───────────────────────
        if strict_mode:
            err_msg = (
                "SLACK_STRICT_MODE is enabled but SLACK_WEBHOOK_URL is not configured. "
                "Set SLACK_WEBHOOK_URL in your .env file to use real Slack integration."
            )
            logger.error(f"[SLACK_STRICT] {err_msg}")
            return False, {
                "action": "SEND_NOTIFICATION",
                "connector": "Slack Adapter",
                "mode": "STRICT_FAIL",
                "status": "not_configured",
            }, err_msg

        # ── LOCAL_FALLBACK: Log the notification locally ─────────────────────
        context["last_local_notification"] = notification_text
        logger.info(f"[LOCAL_FALLBACK] Slack not configured. Notification logged locally:\n{notification_text}")

        return True, {
            "action": "SEND_NOTIFICATION",
            "connector": "Slack Adapter",
            "mode": "LOCAL_FALLBACK",
            "status": "slack_not_configured",
            "note": (
                "SLACK_WEBHOOK_URL is not set. Notification dispatched to local log only. "
                "To enable real Slack delivery, set SLACK_WEBHOOK_URL in your .env file."
            ),
            "message": notification_text,
        }, None
