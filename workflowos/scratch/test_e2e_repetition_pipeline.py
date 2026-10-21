import sys
import requests
import json
import time

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE = "http://127.0.0.1:8000"

print("=" * 80)
print("WORKFLOWOS CORE INTELLIGENCE: END-TO-END REPETITION DETECTION VERIFICATION")
print("=" * 80)

# STEP 1: RESET STATE
print("\n[STEP 1] Resetting system to clean state...")
r = requests.post(f"{BASE}/api/demo/reset")
print("Reset response:", r.json())

# Verify initial clean state: 0 events, 0 workflows
events = requests.get(f"{BASE}/api/events/").json()
wfs = requests.get(f"{BASE}/api/workflows/").json()
print(f"Verified initial state: {len(events)} events, {len(wfs)} workflows.")
assert len(events) == 0, f"Expected 0 events, found {len(events)}"
assert len(wfs) == 0, f"Expected 0 workflows, found {len(wfs)}"

# STEP 2: GENERATE REPEATED ACTIVITY HISTORY (OBSERVE)
print("\n[STEP 2] Generating repeated activity pattern across 3 independent sessions (OBSERVE)...")
r = requests.post(f"{BASE}/api/demo/generate_pattern").json()
print("Activity Generation Output:", json.dumps(r, indent=2))
assert r["events_count"] == 15, f"Expected 15 events, got {r['events_count']}"

# Verify events are stored, but NO workflows exist yet
events = requests.get(f"{BASE}/api/events/").json()
wfs = requests.get(f"{BASE}/api/workflows/").json()
print(f"Post-observation state: {len(events)} events recorded in DB, {len(wfs)} workflows created.")
assert len(events) == 15, f"Expected 15 events, found {len(events)}"
assert len(wfs) == 0, f"Workflows must be 0 before discovery! Found {len(wfs)}"
print("PROOF CONFIRMED: WorkFlowOS did not pre-bake any workflow. 15 events exist with 0 workflows.")

# STEP 3: RUN REPETITION DETECTION (DETECT & DISCOVER)
print("\n[STEP 3] Running Repetition Detector algorithm over activity event history...")
detect_res = requests.post(f"{BASE}/api/workflows/detect").json()
print("Repetition Detector Analysis Report:")
print(f"  • Events Observed:      {detect_res['events_observed']}")
print(f"  • Sessions Analyzed:    {detect_res['sessions_analyzed']}")
print(f"  • Repeated Occurrences: {detect_res['occurrences']}")
print(f"  • Detected Sequence:    {' -> '.join(detect_res['detected_pattern'])}")
print(f"  • Confidence Score:     {detect_res['confidence_percent']}")
print(f"  • Repetition Reason:    {detect_res['repetition_reason']}")

assert detect_res["status"] == "repetition_detected"
assert detect_res["occurrences"] == 3
assert len(detect_res["detected_pattern"]) == 5
assert len(detect_res["workflows"]) >= 1

discovered_wf = detect_res["workflows"][0]
wf_id = discovered_wf["id"]
print(f"\nDiscovered Workflow #{wf_id}: '{discovered_wf['name']}'")
print(f"Initial Approval State: approved={discovered_wf['approved']} (PENDING APPROVAL)")
assert discovered_wf["approved"] is False, "Workflow must initially be PENDING APPROVAL (approved=False)"

# STEP 4: VERIFY EXECUTION IS BLOCKED BEFORE APPROVAL
print("\n[STEP 4] Verifying execution is blocked prior to user approval...")
exec_blocked = requests.post(f"{BASE}/api/workflows/{wf_id}/execute")
print(f"Pre-approval execution attempt HTTP Status: {exec_blocked.status_code}")
print(f"Pre-approval execution attempt Error Detail: {exec_blocked.json().get('detail')}")
assert exec_blocked.status_code == 400, "Unapproved execution must return HTTP 400"

# STEP 5: HUMAN APPROVAL
print(f"\n[STEP 5] Human User reviews and APPROVES Workflow #{wf_id}...")
appr_res = requests.post(f"{BASE}/api/workflows/{wf_id}/approve").json()
print("Approval response:", json.dumps(appr_res, indent=2))
assert appr_res["approved"] is True

# STEP 6: EXECUTE WITH REAL CONNECTORS
print(f"\n[STEP 6] Executing approved Workflow #{wf_id} with REAL live connectors...")
exec_res = requests.post(f"{BASE}/api/workflows/{wf_id}/execute").json()
print("Execution response:", exec_res)
exec_id = exec_res["execution_id"]

# STEP 7: FETCH AND VERIFY EVERY STEP TELEMETRY
print(f"\n[STEP 7] Fetching step telemetry for run ID: {exec_id}...")
steps = requests.get(f"{BASE}/api/executions/{exec_id}/steps").json()

for idx, s in enumerate(steps, 1):
    action = s.get("action_id")
    connector = s.get("connector")
    mode = s.get("mode")
    status = (s.get("status") or "").upper()
    print(f"  [STEP {idx}] Action: {action} | Connector: {connector} | Mode: {mode} | Status: {status}")
    print(f"           Result: {json.dumps(s.get('result'))}")
    assert status == "SUCCESS", f"Step {idx} failed with error: {s.get('error')}"
    # Verify authentic modes
    if idx in (1, 2):
        assert mode == "REAL_API", f"Step {idx} expected REAL_API, got {mode}"
    elif idx in (3, 4):
        assert mode == "REAL_DATABASE", f"Step {idx} expected REAL_DATABASE, got {mode}"
    elif idx == 5:
        assert mode == "REAL_SLACK", f"Step {idx} expected REAL_SLACK, got {mode}"

ex_final = requests.get(f"{BASE}/api/executions/{exec_id}").json()
print(f"\n[FINAL STATUS] Overall Execution: {ex_final.get('status', '').upper()}")
assert ex_final.get("status") == "success"

# STEP 8: VERIFY FINAL DATABASE MUTATIONS (CRM DB)
print("\n[STEP 8] Verifying final SQLite database mutations...")
custs = requests.get(f"{BASE}/api/integrations/crm/customers").json()
sanvi_record = next((c for c in custs if c["email"] == "sas23aiml@cmrit.ac.in"), None)
print("Sanvi S record in SQLite database:", sanvi_record)
assert sanvi_record is not None
assert sanvi_record["status"] == "REQUEST_PROCESSED"

print("\n" + "=" * 80)
print("ALL 12 REQUIREMENTS VERIFIED AND CONFIRMED 100% SUCCESSFUL!")
print("=" * 80)
