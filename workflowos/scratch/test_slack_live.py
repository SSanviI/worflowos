import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env first (must happen before importing slack adapter)
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os
from workflowos.automation.adapters.slack import SlackAdapter

webhook_url = os.getenv("SLACK_WEBHOOK_URL")

print("=" * 60)
print("WorkFlowOS - Live Slack Integration Test")
print("=" * 60)

if not webhook_url:
    print("[FAIL] SLACK_WEBHOOK_URL is not set in .env")
    print("       Please add it to .env before running this test.")
    print("       See .env.example for setup instructions.")
    sys.exit(1)

print(f"[INFO] Webhook configured: {webhook_url[:50]}...")
print("[INFO] Sending live test notification to Slack...")

context = {
    "customer_name": "Test Customer (Live Test)",
    "customer_email": "testcustomer@example.com",
    "email_subject": "WorkFlowOS Live Slack Integration Test",
    "execution_id": "exec_live_slack_test",
    "workflow_name": "Real Slack Integration Verification",
    "attachment_path": "test_invoice.pdf",
}

success, result, err = SlackAdapter.send_notification(db=None, params={}, context=context)

print()
print(f"Result mode:    {result.get('mode')}")
print(f"Result status:  {result.get('status')}")
print(f"HTTP status:    {result.get('http_status', 'N/A')}")
print(f"Success:        {success}")
print(f"Error:          {err}")
print()

if success and result.get("mode") == "REAL_SLACK":
    print(">>> REAL_SLACK DELIVERY: SUCCESS <<<")
    print("Check your Slack channel for the notification!")
elif result.get("mode") == "LOCAL_FALLBACK":
    print("[FAIL] Fell back to LOCAL_FALLBACK — webhook may not be loading from .env")
else:
    print(f"[FAIL] Slack delivery failed: {err}")
    sys.exit(1)
