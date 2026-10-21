import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflowos.backend import database, models
from workflowos.backend.models.workflow import Workflow
from workflowos.backend.models.demo_customer import DemoCustomer, CustomerRequest
from workflowos.backend.models.workflow_execution import WorkflowExecution, ExecutionStep
from workflowos.automation.engine import execute_workflow

db = next(database.get_db())

# 1. Ensure test customer exists in DB
cust = db.query(DemoCustomer).filter(DemoCustomer.name == "Test Customer").first()
if not cust:
    cust = DemoCustomer(name="Test Customer", email="testcustomer@example.com", company="ACME Corp", status="NEW")
    db.add(cust)
    db.commit()
    db.refresh(cust)
else:
    cust.status = "NEW"
    db.commit()

# 2. Define complete CRM Workflow with real Gmail connector
crm_workflow = Workflow(
    name="Real Gmail CRM E2E Processing Flow",
    description="Fetches real email with attachment from Gmail API, downloads attachment, updates CRM record and sends notification.",
    trigger={"type": "event", "source": "gmail"},
    actions=[
        {"id": "a1", "type": "READ_EMAIL", "parameters": {}},
        {"id": "a2", "type": "DOWNLOAD_ATTACHMENT", "parameters": {}},
        {"id": "a3", "type": "FIND_CUSTOMER", "parameters": {"name": "Test Customer"}},
        {"id": "a4", "type": "UPDATE_CUSTOMER", "parameters": {"status": "REQUEST_PROCESSED"}},
        {"id": "a5", "type": "SEND_NOTIFICATION", "parameters": {}},
    ],
    approved=True,
    confidence=0.99,
    occurrences=1,
)
db.add(crm_workflow)
db.commit()
db.refresh(crm_workflow)

print(f"Workflow #{crm_workflow.id} created and approved.")

# 3. Execute workflow
exec_id = execute_workflow(db, crm_workflow)
print(f"Execution ID: {exec_id}")

# 4. Inspect execution results
exec_record = db.query(WorkflowExecution).filter(WorkflowExecution.execution_id == exec_id).first()
print(f"Execution Status: {exec_record.status}")
print(f"Execution Error: {exec_record.error}")

steps = db.query(ExecutionStep).filter(ExecutionStep.execution_id == exec_record.id).order_by(ExecutionStep.id).all()
print(f"\nTotal Steps Executed: {len(steps)}")
for idx, s in enumerate(steps, 1):
    action_type = crm_workflow.actions[idx-1]["type"]
    print(f"Step {idx} [{action_type}]: status={s.status}, connector={s.connector}, mode={s.mode}")
    if s.result and isinstance(s.result, dict):
        if "subject" in s.result:
            safe_subj = str(s.result.get("subject", "")).encode("ascii", errors="replace").decode()
            print(f"   Subject: {safe_subj}")
        if "attachment_path" in s.result:
            print(f"   Downloaded to: {s.result.get('attachment_path')}")
        if "name" in s.result:
            print(f"   Customer: {s.result.get('name')}")
        if "new_status" in s.result:
            print(f"   Updated Status: {s.result.get('new_status')}")
    if s.error:
        print(f"   Error: {s.error}")

# 5. Verify database mutation
db.refresh(cust)
print(f"\nCustomer final status in DB: {cust.status}")
reqs = db.query(CustomerRequest).filter(CustomerRequest.customer_id == cust.id).all()
print(f"Customer requests in DB: {len(reqs)}")
if reqs:
    latest_req = reqs[-1]
    safe_subj = str(latest_req.subject).encode("ascii", errors="replace").decode()
    print(f"Latest Request ID: {latest_req.id}, Subject: {safe_subj}, Attachment: {latest_req.attachment_path}")

assert exec_record.status == "success"
assert len(steps) == 5
assert cust.status == "REQUEST_PROCESSED"
print("\n>>> ALL 5 STEPS OF CRM WORKFLOW SUCCEEDED END-TO-END! <<<")
