import requests
import json

BASE = "http://127.0.0.1:8000"

res = requests.post(f"{BASE}/api/workflows/1/execute").json()
print("Execute response:", res)

exec_id = res["execution_id"]
steps = requests.get(f"{BASE}/api/executions/{exec_id}/steps").json()

for idx, s in enumerate(steps, 1):
    action = s.get("action_id")
    connector = s.get("connector")
    mode = s.get("mode")
    status = (s.get("status") or "").upper()
    print(f"[STEP {idx}] Action: {action} | Connector: {connector} | Mode: {mode} | Status: {status}")
    print(f"         Result: {json.dumps(s.get('result'))}")

ex = requests.get(f"{BASE}/api/executions/{exec_id}").json()
print(f"[RESULT] Final Status: {(ex.get('status') or '').upper()}")
