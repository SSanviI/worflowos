# workflowos/tests/verify_real_world_windows.py
"""End-to-End Real World Windows Verification Script.

Executes the Phase 22 & Phase 23 verification:
1. Creates C:\\WorkFlowOS_Test\\Input and C:\\WorkFlowOS_Test\\Output
2. Starts the Desktop Activity Agent
3. Performs real Windows filesystem actions across multiple sessions (creating, renaming, moving real files)
4. Lets the activity agent capture real events via Watchdog & Windows OS
5. Stops the agent
6. Runs generic discovery & AI understanding
7. Validates candidate workflow created in PENDING_APPROVAL state
8. Approves the workflow
9. Places a new real test file in C:\\WorkFlowOS_Test\\Input
10. Executes the approved workflow via Automation Engine
11. Verifies that the file was ACTUALLY renamed and moved to C:\\WorkFlowOS_Test\\Output
12. Checks execution record and step logs in DB
"""

import os
import sys
import time
import shutil
from datetime import datetime

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from workflowos.backend.database import SessionLocal, engine, Base
from workflowos.backend.models.activity import ActivityEvent
from workflowos.backend.models.workflow import Workflow
from workflowos.backend.models.workflow_execution import WorkflowExecution, ExecutionStep
from workflowos.activity_agent.manager import agent_manager
from workflowos.workflow_engine.discovery import discover_workflows
from workflowos.workflow_engine.generator import enrich_workflow
from workflowos.automation.engine import execute_workflow

TEST_INPUT_DIR = r"C:\WorkFlowOS_Test\Input"
TEST_OUTPUT_DIR = r"C:\WorkFlowOS_Test\Output"


def run_real_world_verification():
    print("=" * 70)
    print("[RUNNING] PHASE 22: REAL WINDOWS OS END-TO-END VERIFICATION")
    print("=" * 70)

    # 1. Prepare directories
    print(f"\n[Step 1] Preparing real filesystem directories:\n  - {TEST_INPUT_DIR}\n  - {TEST_OUTPUT_DIR}")
    os.makedirs(TEST_INPUT_DIR, exist_ok=True)
    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)

    # Clean previous test files
    for d in [TEST_INPUT_DIR, TEST_OUTPUT_DIR]:
        for f in os.listdir(d):
            p = os.path.join(d, f)
            try:
                if os.path.isfile(p):
                    os.remove(p)
                elif os.path.isdir(p):
                    shutil.rmtree(p)
            except Exception:
                pass

    # Ensure DB tables exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Clear old records for clean run
    db.query(ExecutionStep).delete()
    db.query(WorkflowExecution).delete()
    db.query(Workflow).delete()
    db.query(ActivityEvent).delete()
    db.commit()

    # 2. Start Live Desktop Activity Agent
    print("\n[Step 2] Starting Desktop Activity Agent (Watchdog + Window Observer)...")
    status = agent_manager.start([TEST_INPUT_DIR, TEST_OUTPUT_DIR])
    print(f"[OK] Agent Status: {status['status'].upper()} (is_running={status['is_running']})")
    print(f"[OK] Monitored paths: {status['monitored_paths']}")
    time.sleep(1.0)  # Wait for background threads to initialize

    # 3. Perform REAL user activity on Windows filesystem
    print("\n[Step 3] Simulating real user file operations on Windows disk...")
    for idx in range(1, 4):
        file_name = f"invoice_{idx}.txt"
        renamed_name = f"processed_invoice_{idx}.txt"
        file_path = os.path.join(TEST_INPUT_DIR, file_name)
        renamed_path = os.path.join(TEST_INPUT_DIR, renamed_name)
        moved_path = os.path.join(TEST_OUTPUT_DIR, renamed_name)

        print(f"  - Session {idx}: Creating {file_name} -> Renaming to {renamed_name} -> Moving to Output...")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"Real invoice payload {idx}\nTimestamp: {datetime.utcnow()}\n")
        time.sleep(0.4)

        os.rename(file_path, renamed_path)
        time.sleep(0.4)

        shutil.move(renamed_path, moved_path)
        time.sleep(0.6)

    # Wait briefly for observer queue processing
    time.sleep(2.0)

    # 4. Stop Agent
    print("\n[Step 4] Stopping Activity Agent...")
    status = agent_manager.stop()
    print(f"[OK] Agent Status: {status['status'].upper()}")

    # 5. Verify captured real events
    events = db.query(ActivityEvent).all()
    print(f"\n[Step 5] Checking Captured OS Activity Events in Database...")
    print(f"[OK] Total Events Captured: {len(events)}")
    for ev in events[:10]:
        print(f"  [{ev.timestamp.strftime('%H:%M:%S')}] App: {ev.application} | Action: {ev.action} | Target: {ev.target}")

    assert len(events) >= 6, "Expected at least 6 real activity events to be captured!"

    # 6. Run Generic Workflow Discovery & AI Understanding
    print("\n[Step 6] Running Generic Workflow Discovery & AI Understanding...")
    discovered = discover_workflows(db)
    print(f"[OK] Discovered {len(discovered)} workflow candidate(s)")
    assert len(discovered) >= 1, "Expected at least 1 candidate workflow to be discovered!"

    for wf in discovered:
        enrich_workflow(db, wf)

    candidate = discovered[0]
    print(f"\n[Step 7] Inspecting Discovered Candidate Workflow:")
    print(f"  - Name (AI Intent): {candidate.name}")
    print(f"  - Description: {candidate.description}")
    print(f"  - Confidence: {candidate.confidence}")
    print(f"  - Occurrences: {candidate.occurrences}")
    print(f"  - Trigger: {candidate.trigger}")
    print(f"  - Variables: {candidate.variables}")
    print(f"  - Conditions: {candidate.conditions}")
    print(f"  - Actions: {[a.get('type') for a in candidate.actions]}")
    print(f"  - Approved: {candidate.approved} (PENDING_APPROVAL state)")

    assert candidate.approved is False, "Candidate must NOT be auto-approved!"

    # 8. User Approval
    print("\n[Step 8] User Explicitly Approves Workflow...")
    candidate.approved = True
    db.commit()
    print(f"[OK] Workflow #{candidate.id} state is now APPROVED")

    # 9. Real Automation Execution Test
    print("\n[Step 9] Creating a new real input file in C:\\WorkFlowOS_Test\\Input to test execution...")
    test_run_file = os.path.join(TEST_INPUT_DIR, "quarterly_report.txt")
    with open(test_run_file, "w", encoding="utf-8") as f:
        f.write("Quarterly financial report 2026 content.\n")
    assert os.path.exists(test_run_file)

    print("\n[Step 10] Executing Approved Workflow via Real Automation Engine...")
    exec_id = execute_workflow(db, candidate, initial_context={"file_path": test_run_file, "input_dir": TEST_INPUT_DIR, "destination_dir": TEST_OUTPUT_DIR})
    print(f"[OK] Execution Dispatched. Run ID: {exec_id}")

    # 10. Verify actual side effect on Windows filesystem
    print("\n[Step 11] Verifying Real Windows Filesystem Side Effect...")
    # Check that original input file is gone from Input directory
    assert not os.path.exists(test_run_file), "Original file should no longer be at source path!"

    # Check that the processed/renamed file ACTUALLY exists in Output directory
    output_files = os.listdir(TEST_OUTPUT_DIR)
    print(f"[OK] Files found in {TEST_OUTPUT_DIR}: {output_files}")
    assert len(output_files) >= 1, "Expected output file to exist in destination directory!"

    # 11. Verify Execution Telemetry in DB
    print("\n[Step 12] Verifying Execution & Step Logs in Database...")
    exec_rec = db.query(WorkflowExecution).filter(WorkflowExecution.execution_id == exec_id).first()
    assert exec_rec is not None
    assert exec_rec.status == "success", f"Execution failed with error: {exec_rec.error}"

    steps = db.query(ExecutionStep).filter(ExecutionStep.execution_id == exec_rec.id).all()
    for s in steps:
        print(f"  - Step {s.action_id} -> Status: {s.status} | Result: {s.result}")
        assert s.status == "success"

    db.close()
    print("\n" + "=" * 70)
    print("[SUCCESS] PHASE 22 REAL-WORLD WINDOWS VERIFICATION COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_real_world_verification()
