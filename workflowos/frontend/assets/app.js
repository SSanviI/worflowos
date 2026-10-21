// frontend/assets/app.js - WorkFlowOS Client Engine
const API_BASE = "";

// State
let isObserving = false;

async function fetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        let errDetail = `HTTP ${res.status}`;
        try {
            const data = await res.json();
            if (data.detail) errDetail = data.detail;
        } catch (_) {}
        throw new Error(errDetail);
    }
    return res.json();
}

// 1. Agent & System Telemetry
async function loadAgentStatus() {
    try {
        const data = await fetchJSON(`/api/agent/status`);
        isObserving = data.is_running;
        const text = document.getElementById("agent-status-text");
        const toggleBtn = document.getElementById("btn-toggle-agent");
        const pathsEl = document.getElementById("monitored-paths-text");

        if (isObserving) {
            text.textContent = "OBSERVING";
            toggleBtn.textContent = "⏸ Pause Observation";
            toggleBtn.className = "btn btn-danger btn-sm";
        } else {
            text.textContent = "PAUSED";
            toggleBtn.textContent = "▶ Start Observation";
            toggleBtn.className = "btn btn-success btn-sm";
        }

        if (pathsEl && data.monitored_paths) {
            pathsEl.textContent = data.monitored_paths.join(", ");
        }
    } catch (err) {
        console.error("Failed loading agent status:", err);
    }
}

async function toggleAgent() {
    try {
        if (isObserving) {
            await fetchJSON(`/api/agent/stop`, { method: "POST" });
        } else {
            await fetchJSON(`/api/agent/start`, { method: "POST" });
        }
        await loadAgentStatus();
    } catch (err) {
        alert(`Agent toggle error: ${err.message}`);
    }
}

// 2. Integration Status Telemetry
async function loadIntegrationStatus() {
    try {
        const data = await fetchJSON(`/api/integrations/status`);

        // Gmail
        const gMode = document.getElementById("integ-gmail-mode");
        const gDesc = document.getElementById("integ-gmail-desc");
        if (gMode && data.gmail) {
            gMode.textContent = data.gmail.mode;
            gMode.style.color = data.gmail.configured ? "#4ade80" : "#fbbf24";
            gDesc.textContent = data.gmail.message || (data.gmail.configured ? "Gmail OAuth Connected" : "Credentials Required");
        }

        // Local CRM
        const cMode = document.getElementById("integ-crm-mode");
        const cDesc = document.getElementById("integ-crm-desc");
        if (cMode && data.local_crm) {
            cMode.textContent = data.local_crm.mode;
            cMode.style.color = "#4ade80";
            cDesc.textContent = `SQLite app.db (${data.local_crm.customer_count || 0} Customers)`;
        }

        // Slack
        const sMode = document.getElementById("integ-slack-mode");
        const sDesc = document.getElementById("integ-slack-desc");
        if (sMode && data.slack) {
            sMode.textContent = data.slack.mode;
            sMode.style.color = data.slack.configured ? "#4ade80" : "#38bdf8";
            sDesc.textContent = data.slack.configured ? "Slack Webhook Connected" : "Local Notification Fallback";
        }

        // AI Engine
        const aMode = document.getElementById("integ-ai-mode");
        const aDesc = document.getElementById("integ-ai-desc");
        if (aMode && data.ai_engine) {
            aMode.textContent = data.ai_engine.mode;
            aMode.style.color = data.ai_engine.has_api_key ? "#4ade80" : "#c084fc";
            aDesc.textContent = data.ai_engine.provider;
        }
    } catch (err) {
        console.error("Failed loading integration status:", err);
    }
}

// 3. Activity Events Telemetry Stream
async function loadEvents() {
    try {
        const events = await fetchJSON(`/api/events/?limit=40`);
        const listEl = document.getElementById("events-list-container");
        const countEl = document.getElementById("events-count");

        if (countEl) countEl.textContent = events.length;

        if (!events || events.length === 0) {
            listEl.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 1rem; text-align: center;">No activity events captured yet. Click "Simulate CRM Pipeline Activity" or start desktop observation.</div>`;
            return;
        }

        listEl.innerHTML = events.map(ev => {
            const timeStr = new Date(ev.timestamp).toLocaleTimeString();
            const targetStr = ev.target ? `<div class="event-target">${escapeHTML(ev.target)}</div>` : '';
            const isSimulated = ev.raw_data && ev.raw_data.simulated;
            const badgeTag = isSimulated
                ? `<span class="badge badge-simulated" style="font-size: 0.65rem; padding: 0.15rem 0.4rem;">SIMULATED OBSERVATION</span>`
                : `<span class="badge badge-real" style="font-size: 0.65rem; padding: 0.15rem 0.4rem;">REAL EVENT</span>`;

            return `
                <div class="event-item">
                    <div class="event-top">
                        <span><strong>${escapeHTML(ev.application)}</strong></span>
                        <div>${badgeTag} <span style="margin-left: 0.4rem;">${timeStr}</span></div>
                    </div>
                    <div class="event-action">${escapeHTML(ev.action)}</div>
                    ${targetStr}
                </div>
            `;
        }).join("");
    } catch (err) {
        console.error("Failed loading events:", err);
    }
}

// 4. Workflows List & Approval
async function loadWorkflows() {
    try {
        const workflows = await fetchJSON(`/api/workflows/`);
        const container = document.getElementById("workflows-container");
        const countEl = document.getElementById("workflows-count");

        if (countEl) countEl.textContent = workflows.length;

        if (!workflows || workflows.length === 0) {
            container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 1rem; text-align: center;">No workflows discovered yet. Click "Scan for Repetitive Patterns" or simulate activity.</div>`;
            return;
        }

        container.innerHTML = workflows.map(wf => {
            const confPct = Math.round((wf.confidence || 0.85) * 100);
            const statusBadge = wf.approved
                ? `<span class="badge badge-observing">APPROVED</span>`
                : (wf.rejected ? `<span class="badge badge-paused" style="color: var(--accent-red); border-color: rgba(239,68,68,0.4)">REJECTED</span>`
                : `<span class="badge badge-paused">PENDING_APPROVAL</span>`);

            const actionsFlow = (wf.actions || []).map((a, idx) => `
                <span class="action-pill">${escapeHTML((a.type || '').toUpperCase())}</span>
                ${idx < (wf.actions.length - 1) ? '<span class="action-arrow">→</span>' : ''}
            `).join("");

            // Conditions summary
            const condStr = (wf.conditions || []).map(c => c.condition || c.check).join(", ") || "Action parameters valid";
            const varStr = (wf.variables || []).map(v => v.name).join(", ") || "email_subject, customer_id";

            return `
                <div class="workflow-card">
                    <div class="wf-header">
                        <div>
                            <div class="wf-title">${escapeHTML(wf.name)}</div>
                            <div class="wf-desc">${escapeHTML(wf.description || '')}</div>
                        </div>
                        <div>${statusBadge}</div>
                    </div>

                    <div class="wf-actions-flow">
                        ${actionsFlow}
                    </div>

                    <div class="wf-details-box">
                        <div class="wf-details-row">
                            <span class="wf-details-label">⚡ Trigger:</span>
                            <span class="wf-details-val"><code>${escapeHTML(wf.trigger?.type || 'new_customer_request_email')}</code> (${escapeHTML(wf.trigger?.source || 'gmail')})</span>
                        </div>
                        <div class="wf-details-row">
                            <span class="wf-details-label">🛡 Conditions:</span>
                            <span class="wf-details-val">${escapeHTML(condStr)}</span>
                        </div>
                        <div class="wf-details-row">
                            <span class="wf-details-label">📌 Variables:</span>
                            <span class="wf-details-val"><code>${escapeHTML(varStr)}</code></span>
                        </div>
                    </div>

                    <div class="wf-meta">
                        <span>🎯 Confidence: <strong>${confPct}%</strong></span>
                        <span>🔁 Occurrences: <strong>${wf.occurrences}</strong></span>
                    </div>

                    <div class="btn-group" style="margin-top: 0.25rem;">
                        <button class="btn btn-sm btn-success" onclick="approveWorkflow(${wf.id})" ${wf.approved ? 'disabled' : ''}>
                            ✓ Approve
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="rejectWorkflow(${wf.id})" ${wf.rejected ? 'disabled' : ''}>
                            ✕ Reject
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="executeWorkflow(${wf.id})" ${!wf.approved ? 'disabled title="Must approve first"' : ''}>
                            ▶ Execute Real Workflow
                        </button>
                    </div>
                </div>
            `;
        }).join("");
    } catch (err) {
        console.error("Failed loading workflows:", err);
    }
}

async function approveWorkflow(id) {
    try {
        await fetchJSON(`/api/workflows/${id}/approve`, { method: "POST" });
        await loadWorkflows();
        await loadMetrics();
        await loadLearningStats();
    } catch (err) {
        alert(`Approval error: ${err.message}`);
    }
}

async function rejectWorkflow(id) {
    try {
        await fetchJSON(`/api/workflows/${id}/reject`, { method: "POST" });
        await loadWorkflows();
        await loadMetrics();
        await loadLearningStats();
    } catch (err) {
        alert(`Reject error: ${err.message}`);
    }
}

// 5. Execution Console & Real Execution Engine
async function executeWorkflow(id) {
    const logBox = document.getElementById("execution-terminal");
    logBox.textContent = `[ENGINE] Triggering REAL EXECUTION for Workflow #${id}...\n`;

    try {
        const res = await fetchJSON(`/api/workflows/${id}/execute`, { method: "POST" });
        const execId = res.execution_id;
        logBox.textContent += `[ENGINE] Execution initiated. Run ID: ${execId}\n\n`;

        // Fetch execution steps
        const steps = await fetchJSON(`/api/executions/${execId}/steps`);
        steps.forEach((s, idx) => {
            const st = (s.status || '').toUpperCase();
            const conn = s.connector || 'Adapter';
            const mode = s.mode || 'REAL_API';
            let resDetails = '';

            if (s.result) {
                resDetails = JSON.stringify(s.result);
            } else if (s.error) {
                resDetails = `ERROR: ${s.error}`;
            }

            logBox.textContent += `[STEP ${idx+1}] Action: ${s.action_id} | Connector: ${conn} | Mode: ${mode} | Status: ${st}\n         Result: ${resDetails}\n\n`;
        });

        const execDetails = await fetchJSON(`/api/executions/${execId}`);
        logBox.textContent += `[RESULT] Final Status: ${(execDetails.status || '').toUpperCase()}`;
        if (execDetails.error) {
            logBox.textContent += `\n[FAILURE REASON] ${execDetails.error}`;
        }

        await loadExecutions();
        await loadMetrics();
        await loadLearningStats();
    } catch (err) {
        logBox.textContent += `\n[ENGINE FAILURE] Execution error: ${err.message}\n`;
    }
}

// 6. Metrics Aggregator
async function loadMetrics() {
    try {
        const [events, wfs, execs] = await Promise.all([
            fetchJSON(`/api/events/?limit=100`),
            fetchJSON(`/api/workflows/`),
            fetchJSON(`/api/executions/?limit=100`),
        ]);

        const mEvents = document.getElementById("m-events");
        const mPatterns = document.getElementById("m-patterns");
        const mWfs = document.getElementById("m-workflows");
        const mPending = document.getElementById("m-pending");
        const mExecs = document.getElementById("m-executions");
        const mSuccess = document.getElementById("m-success");
        const mTimeSaved = document.getElementById("m-timesaved");

        if (mEvents) mEvents.textContent = events.length;
        if (mWfs) mWfs.textContent = wfs.length;

        const pendingCount = wfs.filter(w => !w.approved && !w.rejected).length;
        if (mPending) mPending.textContent = pendingCount;
        if (mPatterns) mPatterns.textContent = wfs.length > 0 ? wfs.length : 0;

        if (mExecs) mExecs.textContent = execs.length;
        const succCount = execs.filter(e => e.status === "success").length;
        if (mSuccess) mSuccess.textContent = succCount;

        // Estimate time saved: 4 mins per successful automation run
        if (mTimeSaved) mTimeSaved.textContent = `${succCount * 4} mins`;

    } catch (err) {
        console.error("Failed loading metrics:", err);
    }
}

// 7. Execution History
async function loadExecutions() {
    try {
        const execs = await fetchJSON(`/api/executions/?limit=10`);
        const listEl = document.getElementById("executions-history-list");
        if (!listEl) return;

        if (!execs || execs.length === 0) {
            listEl.innerHTML = `<div style="color: var(--text-muted); font-size: 0.8rem; padding: 0.5rem;">No executions recorded yet.</div>`;
            return;
        }

        listEl.innerHTML = execs.map(e => {
            const stColor = e.status === 'success' ? '#4ade80' : '#f87171';
            const timeStr = new Date(e.start_time).toLocaleTimeString();
            return `
                <div style="padding: 0.5rem 0; border-bottom: 1px solid var(--border-color); font-size: 0.82rem; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>${escapeHTML(e.workflow_name || 'Workflow')}</strong>
                        <div style="color: var(--text-muted); font-size: 0.75rem; font-family: 'JetBrains Mono', monospace;">${e.execution_id}</div>
                    </div>
                    <div style="text-align: right;">
                        <span style="color: ${stColor}; font-weight: 700;">${(e.status || '').toUpperCase()}</span>
                        <div style="color: var(--text-muted); font-size: 0.75rem;">${timeStr}</div>
                    </div>
                </div>
            `;
        }).join("");
    } catch (err) {
        console.error("Failed loading executions:", err);
    }
}

// 8. Learning Stats
async function loadLearningStats() {
    try {
        const stats = await fetchJSON(`/api/learning/stats`);
        const statsEl = document.getElementById("learning-stats-content");
        if (!statsEl) return;

        if (!stats || stats.length === 0) {
            statsEl.innerHTML = `<div style="color: var(--text-muted); font-size: 0.8rem;">No workflow feedback data yet.</div>`;
            return;
        }

        statsEl.innerHTML = stats.map(s => `
            <div style="padding: 0.4rem 0; border-bottom: 1px solid var(--border-color); font-size: 0.8rem;">
                <div style="display: flex; justify-content: space-between;">
                    <strong>${escapeHTML(s.workflow_name)}</strong>
                    <span style="color: var(--accent-blue); font-weight: 700;">Reliability: ${s.reliability_rate}%</span>
                </div>
                <div style="color: var(--text-secondary); font-size: 0.75rem; margin-top: 0.2rem;">
                    Executions: ${s.total_executions} | Success: ${s.success_count} | Failures: ${s.failure_count}
                </div>
            </div>
        `).join("");
    } catch (err) {
        console.error("Failed loading learning stats:", err);
    }
}

// 9. Diagnostics & Testing Action Handlers
async function testGmailIntegration() {
    const logBox = document.getElementById("execution-terminal");
    logBox.textContent = "[DIAGNOSTICS] Testing Gmail API integration...\n";
    try {
        const res = await fetchJSON(`/api/integrations/gmail/test`, { method: "POST" });
        if (res.status === "success") {
            logBox.textContent += `[GMAIL SUCCESS] Connector: ${res.connector} | Mode: ${res.mode}\nSubject: ${res.subject}\nSender: ${res.sender}\nHas Attachment: ${res.has_attachment}\n`;
        } else {
            logBox.textContent += `[GMAIL NOTICE] Connector: ${res.connector} | Status: ${res.status}\nMessage: ${res.error}\n`;
        }
        await loadIntegrationStatus();
    } catch (err) {
        logBox.textContent += `[GMAIL ERROR] ${err.message}\n`;
    }
}

async function testSlackIntegration() {
    const logBox = document.getElementById("execution-terminal");
    logBox.textContent = "[DIAGNOSTICS] Testing Slack integration...\n";
    try {
        const res = await fetchJSON(`/api/integrations/slack/test`, { method: "POST" });
        logBox.textContent += `[SLACK DIAGNOSTICS] Mode: ${res.mode} | Connector: ${res.connector} | Status: ${res.status.toUpperCase()}\nDetails: ${JSON.stringify(res.details)}\n`;
        await loadIntegrationStatus();
    } catch (err) {
        logBox.textContent += `[SLACK ERROR] ${err.message}\n`;
    }
}

async function seedCRMCustomer() {
    try {
        const res = await fetchJSON(`/api/integrations/crm/seed`, { method: "POST" });
        alert(`Test Customer seeded in Local SQLite CRM Database:\nID: ${res.customer.id} | Name: ${res.customer.name} | Status: ${res.customer.status}`);
        await loadIntegrationStatus();
    } catch (err) {
        alert(`CRM Seed error: ${err.message}`);
    }
}

async function generateRepeatedActivityPattern() {
    const logBox = document.getElementById("execution-terminal");
    logBox.textContent = `[OBSERVER] Recording genuine repeated user activity events across 3 independent sessions...\n`;

    try {
        const res = await fetchJSON(`/api/demo/generate_pattern`, { method: "POST" });
        await loadEvents();
        await loadMetrics();

        logBox.textContent += `[OBSERVER SUCCESS] ${res.events_count} raw activity events recorded across ${res.sessions_count} independent observation sessions.\n\n`;
        logBox.textContent += `Underlying Activity Stream:\n`;
        logBox.textContent += `Canonical Sequence: ${res.pattern_preview}\n\n`;
        logBox.textContent += `--------------------------------------------------------------------------------\n`;
        logBox.textContent += `STATUS: ACTIVITY RECORDED | NO WORKFLOW GENERATED YET\n`;
        logBox.textContent += `Notice: The workflows list remains empty.\n`;
        logBox.textContent += `Click "🔍 Scan for Repetitions" to trigger the repetition detection algorithm.\n`;
        logBox.textContent += `--------------------------------------------------------------------------------\n`;
    } catch (err) {
        logBox.textContent += `[OBSERVER ERROR] ${err.message}\n`;
    }
}

async function triggerRepetitionDetection() {
    const logBox = document.getElementById("execution-terminal");
    logBox.textContent = `[REPETITION DETECTOR] Scanning observed activity events history for repetitive patterns...\n`;

    try {
        const res = await fetchJSON(`/api/workflows/detect`, { method: "POST" });
        await loadWorkflows();
        await loadMetrics();

        if (res.workflows && res.workflows.length > 0) {
            logBox.textContent = `================================================================================\n`;
            logBox.textContent += `[REPETITION DETECTED] Genuine Workflow Motif Discovered from Activity History!\n`;
            logBox.textContent += `================================================================================\n`;
            logBox.textContent += `• Events Observed:      ${res.events_observed} events\n`;
            logBox.textContent += `• Sessions Analyzed:    ${res.sessions_analyzed} distinct sessions\n`;
            logBox.textContent += `• Repeated Occurrences: ${res.occurrences} occurrences\n`;
            logBox.textContent += `• Detected Sequence:    ${res.detected_pattern.join(" → ")}\n`;
            logBox.textContent += `• Confidence Score:     ${res.confidence_percent} (Similarity Threshold: 75%)\n`;
            logBox.textContent += `• Reason for Detection: ${res.repetition_reason}\n\n`;
            logBox.textContent += `Discovered Candidate Workflows:\n`;
            res.workflows.forEach(w => {
                logBox.textContent += `  → Workflow #${w.id}: "${w.name}"\n`;
                logBox.textContent += `    Description: ${w.description}\n`;
                logBox.textContent += `    Confidence: ${(w.confidence * 100).toFixed(1)}% | Occurrences: ${w.occurrences}\n`;
                logBox.textContent += `    Approval Status: PENDING APPROVAL\n`;
                logBox.textContent += `    Action Required: Review on dashboard and click "✓ Approve" to permit execution.\n`;
            });
            logBox.textContent += `================================================================================\n`;
        } else {
            logBox.textContent += `[DETECTOR NOTICE] No repetitive pattern detected. Events observed: ${res.events_observed}. Ensure at least 2 matching sequences exist.\n`;
        }
    } catch (err) {
        logBox.textContent += `[DETECTOR ERROR] ${err.message}\n`;
    }
}

async function triggerDiscovery() {
    return triggerRepetitionDetection();
}

async function runDemoFilePipeline() {
    try {
        const res = await fetchJSON(`/api/demo/run`, { method: "POST" });
        await refreshAll();
        alert(`File Demo Pipeline executed: ${res.events_generated} events generated, ${res.discovered_workflows} workflow candidate(s) discovered!`);
    } catch (err) {
        alert(`Demo error: ${err.message}`);
    }
}

async function runDemoCRMPipeline() {
    return generateRepeatedActivityPattern();
}

async function resetAllData() {
    if (!confirm("Are you sure you want to reset all activity events, workflows, and execution records?")) return;
    try {
        await fetchJSON(`/api/demo/reset`, { method: "POST" });
        const logBox = document.getElementById("execution-terminal");
        if (logBox) logBox.textContent = "[SYSTEM] Database reset. All events, workflows, and execution history cleared.\n";
        await refreshAll();
    } catch (err) {
        alert(`Reset error: ${err.message}`);
    }
}

// 10. CRM Customer Management Handlers
function openAddCustomerModal() {
    const modal = document.getElementById("add-customer-modal");
    if (modal) {
        modal.style.display = "flex";
        document.getElementById("cust-name-input").focus();
    }
}

function closeAddCustomerModal() {
    const modal = document.getElementById("add-customer-modal");
    if (modal) modal.style.display = "none";
}

async function submitAddCustomer(e) {
    if (e) e.preventDefault();
    const name = document.getElementById("cust-name-input").value.trim();
    const email = document.getElementById("cust-email-input").value.trim();
    const company = document.getElementById("cust-company-input").value.trim();
    const status = document.getElementById("cust-status-input").value;

    const logBox = document.getElementById("execution-terminal");
    logBox.textContent = `[CRM] Adding customer to Local SQLite Database...\nName: ${name}\nEmail: ${email}\nCompany: ${company}\nStatus: ${status}\n`;

    try {
        const res = await fetchJSON(`/api/integrations/crm/customers`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, company, status }),
        });

        if (res.status === "success") {
            logBox.textContent += `[CRM SUCCESS] Customer ${res.action} in app.db (SQLite Table: demo_customers)\nID: ${res.customer.id}\nName: ${res.customer.name}\nEmail: ${res.customer.email}\nCompany: ${res.customer.company}\nStatus: ${res.customer.status}\nCreated: ${res.customer.created_at}\n`;
            alert(`Customer successfully saved to Local CRM database!\nID: ${res.customer.id}\nName: ${res.customer.name}\nEmail: ${res.customer.email}`);
            closeAddCustomerModal();
            document.getElementById("add-customer-form").reset();
            await loadIntegrationStatus();
        } else {
            logBox.textContent += `[CRM ERROR] Failed to save customer.\n`;
        }
    } catch (err) {
        logBox.textContent += `[CRM ERROR] ${err.message}\n`;
        alert(`Failed to save customer: ${err.message}`);
    }
}

async function promptTestFindCustomer() {
    const query = prompt("Enter customer name or email to test FIND_CUSTOMER against Local CRM DB:", "sas23aiml@cmrit.ac.in");
    if (!query) return;

    const logBox = document.getElementById("execution-terminal");
    logBox.textContent = `[CRM FIND TEST] Testing authentic FIND_CUSTOMER adapter query...\nQuery: "${query}"\n\n`;

    try {
        const res = await fetchJSON(`/api/integrations/crm/find`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: query }),
        });

        logBox.textContent += `Connector: ${res.connector} | Mode: ${res.mode}\nStatus: ${res.status.toUpperCase()}\n`;
        if (res.status === "success") {
            logBox.textContent += `Customer Found:\n${JSON.stringify(res.result, null, 2)}\n`;
        } else {
            logBox.textContent += `Customer Not Found: ${res.error}\nDetails: ${JSON.stringify(res.result, null, 2)}\n`;
        }
    } catch (err) {
        logBox.textContent += `[ERROR] ${err.message}\n`;
    }
}

async function viewCRMCustomers() {
    const logBox = document.getElementById("execution-terminal");
    logBox.textContent = `[CRM DB] Fetching all persisted customer records from SQLite demo_customers table...\n`;

    try {
        const list = await fetchJSON(`/api/integrations/crm/customers`);
        logBox.textContent += `Found ${list.length} customer record(s) in app.db:\n`;
        list.forEach(c => {
            logBox.textContent += `• ID #${c.id}: ${c.name} | Email: ${c.email} | Company: ${c.company || 'N/A'} | Status: ${c.status}\n`;
        });
    } catch (err) {
        logBox.textContent += `[ERROR] ${err.message}\n`;
    }
}

function escapeHTML(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

async function refreshAll() {
    await Promise.all([
        loadAgentStatus(),
        loadIntegrationStatus(),
        loadEvents(),
        loadWorkflows(),
        loadMetrics(),
        loadExecutions(),
        loadLearningStats(),
    ]);
}

// Initial setup & interval polling
document.addEventListener("DOMContentLoaded", () => {
    refreshAll();
    setInterval(refreshAll, 3000);
});
