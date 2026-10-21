# workflowos/demo/demo.py
"""Demo CLI runner for WorkFlowOS.

Drives the full pipeline against a running backend server:
1. Resets demonstration database.
2. Ingests simulated activity events through the pipeline.
3. Triggers workflow discovery.
4. Approves discovered candidate.
5. Executes approved workflow and displays real execution telemetry.
"""

import time
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"


def run_demo():
    print("=" * 60)
    print("[RUNNING] Starting WorkFlowOS End-to-End Pipeline Demonstration")
    print("=" * 60)

    # 1. Health check
    try:
        health = requests.get(f"{BASE_URL}/api/health", timeout=5).json()
        print(f"[OK] Backend online: {health}")
    except Exception as e:
        print(f"[ERROR] Backend not reachable at {BASE_URL}. Ensure server is running: {e}")
        sys.exit(1)

    # 2. Reset database for clean run
    print("\n[1/5] Resetting database...")
    res = requests.post(f"{BASE_URL}/api/demo/reset").json()
    print(f"[OK] {res.get('status')}")

    # 3. Simulate file organization events & trigger discovery
    print("\n[2/5] Simulating repeated desktop activity & running discovery...")
    run_res = requests.post(f"{BASE_URL}/api/demo/run").json()
    print(f"[OK] Generated {run_res.get('events_generated')} events")
    print(f"[OK] Discovered {run_res.get('discovered_workflows')} workflow candidate(s)")

    # 4. Fetch discovered workflows
    workflows = requests.get(f"{BASE_URL}/api/workflows/").json()
    if not workflows:
        print("[ERROR] No workflows discovered.")
        return

    candidate = workflows[0]
    wf_id = candidate["id"]
    print(f"\n[3/5] Candidate Workflow Discovered:")
    print(f"  - ID: {candidate['id']}")
    print(f"  - Name (AI Intent): {candidate['name']}")
    print(f"  - Description: {candidate['description']}")
    print(f"  - Confidence: {candidate['confidence']}")
    print(f"  - Status: PENDING_APPROVAL (approved={candidate['approved']})")
    print(f"  - Actions: {[a.get('type') for a in candidate.get('actions', [])]}")

    # 5. User approval
    print(f"\n[4/5] Simulating User Approval...")
    app_res = requests.post(f"{BASE_URL}/api/workflows/{wf_id}/approve").json()
    print(f"[OK] Workflow #{wf_id} status: {app_res.get('status')}")

    # 6. Execute approved workflow
    print(f"\n[5/5] Executing Workflow #{wf_id}...")
    exec_res = requests.post(f"{BASE_URL}/api/workflows/{wf_id}/execute").json()
    exec_id = exec_res.get("execution_id")
    print(f"[OK] Execution dispatched. Run ID: {exec_id}")

    # Fetch execution steps
    steps = requests.get(f"{BASE_URL}/api/executions/{exec_id}/steps").json()
    print("\n--- EXECUTION STEP LOGS ---")
    for idx, s in enumerate(steps, 1):
        status_sym = "[SUCCESS]" if s["status"] == "success" else "[FAILED]"
        print(f"[{idx}] {status_sym} Action: {s['action_id']} | Status: {s['status']} | Result: {s.get('result') or s.get('error')}")

    # Learning stats
    stats = requests.get(f"{BASE_URL}/api/learning/stats/{wf_id}").json()
    print(f"\n[LEARNING STATS] Reliability: {stats.get('reliability_rate')}% | Total Executions: {stats.get('total_executions')}")
    print("\n[SUCCESS] Demonstration complete!")


if __name__ == "__main__":
    run_demo()
