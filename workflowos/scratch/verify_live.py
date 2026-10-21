# scratch/verify_live.py
import sys
import requests

# Fix Windows console UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

print("1. Health Check:")
r = requests.get(f"{BASE_URL}/api/health")
print("   ", r.json())

print("\n2. Integrations Status:")
r = requests.get(f"{BASE_URL}/api/integrations/status")
print("   ", r.json())

print("\n3. Reset Database:")
requests.post(f"{BASE_URL}/api/demo/reset")

print("\n4. Seed Test Customer:")
r = requests.post(f"{BASE_URL}/api/integrations/crm/seed")
print("   ", r.json())

print("\n5. Run CRM Demo Activity Simulation:")
r = requests.post(f"{BASE_URL}/api/demo/run_crm")
print("   ", r.json())

print("\n6. List Discovered Workflows:")
wfs = requests.get(f"{BASE_URL}/api/workflows/").json()
print(f"    Discovered {len(wfs)} workflows.")
for wf in wfs:
    print(f"    ID {wf['id']}: {wf['name']} (Approved: {wf['approved']})")

if wfs:
    wf_id = wfs[0]["id"]
    print(f"\n7. Approve Discovered Workflow #{wf_id}:")
    r = requests.post(f"{BASE_URL}/api/workflows/{wf_id}/approve")
    print("   ", r.json())

    print(f"\n8. Execute Discovered Workflow #{wf_id} (Honest Credential Check):")
    ex = requests.post(f"{BASE_URL}/api/workflows/{wf_id}/execute").json()
    print("   ", ex)

    exec_id = ex["execution_id"]
    print(f"\n9. Fetch Execution Step Log for {exec_id}:")
    steps = requests.get(f"{BASE_URL}/api/executions/{exec_id}/steps").json()
    for idx, s in enumerate(steps, 1):
        print(f"    Step {idx}: Action={s['action_id']} | Connector={s.get('connector')} | Mode={s.get('mode')} | Status={s['status']}")
        if s.get("error"):
            print(f"       Error: {s['error']}")

print("\n10. Testing Direct Local CRM + Slack Execution:")
slack_test = requests.post(f"{BASE_URL}/api/integrations/slack/test").json()
print("    Slack Test Result:", slack_test)

print("\nALL API DIAGNOSTICS & SYSTEM VERIFICATIONS COMPLETE!")
