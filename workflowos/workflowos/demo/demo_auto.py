# workflowos/demo/demo_auto.py
"""Automated demo script driving the genuine pipeline end-to-end.

1. Resets database.
2. Ingests simulated file organization events.
3. Discovers candidate workflow.
4. Approves the workflow candidate.
5. Executes the workflow and polls execution steps.
"""

import time
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"


def run_demo_auto():
    print("[1/4] Resetting and running file demo pipeline...")
    requests.post(f"{BASE_URL}/api/demo/reset")
    run_res = requests.post(f"{BASE_URL}/api/demo/run").json()
    print(f"Generated {run_res.get('events_generated')} events, discovered {run_res.get('discovered_workflows')} workflows.")

    # Retrieve candidate
    workflows = requests.get(f"{BASE_URL}/api/workflows/").json()
    if not workflows:
        print("No workflows discovered.")
        return

    wf = workflows[0]
    wf_id = wf["id"]
    print(f"[2/4] Discovered Workflow #{wf_id}: '{wf['name']}' (Approved: {wf['approved']})")

    # Approve
    print(f"[3/4] Approving Workflow #{wf_id}...")
    requests.post(f"{BASE_URL}/api/workflows/{wf_id}/approve")

    # Execute
    print(f"[4/4] Executing Workflow #{wf_id}...")
    exec_res = requests.post(f"{BASE_URL}/api/workflows/{wf_id}/execute").json()
    exec_id = exec_res["execution_id"]
    print(f"Execution run ID: {exec_id}")

    steps = requests.get(f"{BASE_URL}/api/executions/{exec_id}/steps").json()
    for s in steps:
        print(f"  Step {s['action_id']} -> Status: {s['status']} | Result: {s.get('result') or s.get('error')}")

    exec_detail = requests.get(f"{BASE_URL}/api/executions/{exec_id}").json()
    print(f"Final Execution Status: {exec_detail['status']}")


if __name__ == "__main__":
    run_demo_auto()
