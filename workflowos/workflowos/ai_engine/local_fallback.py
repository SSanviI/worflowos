# workflowos/ai_engine/local_fallback.py
"""Compositional Fallback AI Provider for Workflow Understanding.

Generates semantic interpretations, intent titles, descriptions, triggers,
variables, conditions, and failure policies for ANY arbitrary action sequence
using compositional rule-based semantic analysis.
"""

from typing import List, Dict, Any, Optional
import re
from .provider import AIProvider

# Semantic verb vocabulary
VERB_MEANINGS = {
    "CREATE": "Create new",
    "READ": "Read and parse",
    "DOWNLOAD": "Download incoming",
    "RENAME": "Rename",
    "MOVE": "Organize and move",
    "DELETE": "Clean up or delete",
    "MODIFY": "Modify content of",
    "FIND": "Look up",
    "SEARCH": "Search for",
    "UPDATE": "Update record for",
    "SEND": "Send outgoing",
    "OPEN": "Open",
    "TRANSFORM": "Transform and process",
    "EXPORT": "Export generated",
    "UPLOAD": "Upload",
    "ACTIVE": "Switch focus to",
    "COPY": "Copy",
}

# Semantic noun vocabulary
NOUN_MEANINGS = {
    "FILE": "Files",
    "DIRECTORY": "Directories",
    "FOLDER": "Folders",
    "EMAIL": "Customer Emails",
    "ATTACHMENT": "File Attachments",
    "CUSTOMER": "Customer CRM Profiles",
    "NOTIFICATION": "Team Notifications",
    "SPREADSHEET": "Spreadsheets",
    "DATA": "Dataset Records",
    "REPORT": "Business Reports",
    "WINDOW": "Application Windows",
    "CLIPBOARD": "Clipboard Data",
}


class LocalFallbackProvider(AIProvider):
    """Understands and generates structured semantics for arbitrary workflows."""

    def _parse_action_parts(self, action: str) -> (str, str):
        """Split canonical action into (verb, noun). e.g. CREATE_FILE -> (CREATE, FILE)."""
        clean = action.upper().strip()
        parts = clean.split("_", 1)
        verb = parts[0]
        noun = parts[1] if len(parts) > 1 else ""
        return verb, noun

    def _infer_intent_title(self, actions: List[str]) -> str:
        """Compose human-readable intent title from action sequence."""
        if not actions:
            return "Custom Workflow"

        verbs_nouns = [self._parse_action_parts(a) for a in actions]
        verbs = [v for v, _ in verbs_nouns]
        nouns = [n for _, n in verbs_nouns if n]

        # Domain checks
        if all(n in ("FILE", "DIRECTORY", "FOLDER") for n in nouns if n):
            if "RENAME" in verbs and "MOVE" in verbs:
                return "Organize and Rename Files"
            elif "MOVE" in verbs:
                return "Move and Organize Files"
            elif "CREATE" in verbs:
                return "File Creation and Storage Workflow"
            return "File Management Workflow"

        if "CUSTOMER" in nouns or "EMAIL" in nouns:
            if "UPDATE" in verbs or "FIND" in verbs:
                return "Process Customer Request & CRM Update"
            elif "SEND" in verbs:
                return "Customer Support Communication Flow"
            return "Customer Operations Workflow"

        if "SPREADSHEET" in nouns or "DATA" in nouns:
            if "EXPORT" in verbs or "TRANSFORM" in verbs:
                return "Data Processing & Report Export"
            return "Data Analysis Workflow"

        if "NOTIFICATION" in nouns:
            return "Automated Alert and Notification Workflow"

        # General composition
        primary_verb = VERB_MEANINGS.get(verbs[0], verbs[0].capitalize())
        primary_noun = NOUN_MEANINGS.get(nouns[0], nouns[0].capitalize()) if nouns else "Items"
        last_verb = VERB_MEANINGS.get(verbs[-1], verbs[-1].capitalize())

        if len(actions) > 2:
            return f"{primary_verb} {primary_noun} and Complete Automated Pipeline"
        return f"{primary_verb} {primary_noun}"

    def _infer_description(self, actions: List[str]) -> str:
        """Compose human-readable step-by-step description."""
        steps_desc = []
        for i, act in enumerate(actions, 1):
            verb, noun = self._parse_action_parts(act)
            v_desc = VERB_MEANINGS.get(verb, verb.capitalize())
            n_desc = NOUN_MEANINGS.get(noun, noun.lower() if noun else "item")
            steps_desc.append(f"({i}) {v_desc} {n_desc}")

        steps_text = ", then ".join(steps_desc)
        return f"Automated workflow that reliably executes the following sequence: {steps_text}."

    def _infer_trigger(self, first_action: str) -> Dict[str, Any]:
        """Infer trigger mechanism from the initial action."""
        clean = first_action.upper()
        if "FILE" in clean or "DOWNLOAD" in clean:
            return {
                "type": "file_event",
                "source": "filesystem",
                "event": "file_created_or_dropped",
                "description": "Triggered when a new file is detected in the input workspace.",
            }
        elif "EMAIL" in clean:
            return {
                "type": "email_event",
                "source": "gmail",
                "event": "new_email_received",
                "description": "Triggered when a new email matching customer criteria arrives.",
            }
        elif "SPREADSHEET" in clean or "DATA" in clean:
            return {
                "type": "schedule_or_event",
                "source": "data_pipeline",
                "event": "data_ready",
                "description": "Triggered on scheduled interval or when new dataset is ready.",
            }
        return {
            "type": "manual_or_event",
            "source": "system",
            "event": "user_trigger",
            "description": "Triggered manually by user or on matching system activity.",
        }

    def _infer_variables(self, actions: List[str]) -> List[Dict[str, str]]:
        """Infer required input and contextual variables."""
        variables = []
        seen = set()

        for act in actions:
            clean = act.upper()
            if "FILE" in clean or "DOWNLOAD" in clean:
                if "file_path" not in seen:
                    variables.append({"name": "file_path", "type": "string", "description": "Path to target file"})
                    seen.add("file_path")
            if "RENAME" in clean:
                if "new_name" not in seen:
                    variables.append({"name": "new_name", "type": "string", "description": "New name for target file"})
                    seen.add("new_name")
            if "MOVE" in clean:
                if "destination_dir" not in seen:
                    variables.append({"name": "destination_dir", "type": "string", "description": "Destination directory path"})
                    seen.add("destination_dir")
            if "CUSTOMER" in clean:
                if "customer_id" not in seen:
                    variables.append({"name": "customer_id", "type": "string", "description": "Customer identifier"})
                    seen.add("customer_id")
            if "NOTIFICATION" in clean or "EMAIL" in clean:
                if "recipient" not in seen:
                    variables.append({"name": "recipient", "type": "string", "description": "Notification destination or channel"})
                    seen.add("recipient")

        return variables

    def _infer_conditions(self, actions: List[str]) -> List[Dict[str, str]]:
        """Derive meaningful preconditions and safety assertions from action sequence."""
        conditions = []
        verbs_nouns = [self._parse_action_parts(a) for a in actions]
        nouns = [n for _, n in verbs_nouns if n]
        verbs = [v for v, _ in verbs_nouns]

        if "FILE" in nouns or "DIRECTORY" in nouns:
            conditions.append({
                "condition": "source_file_exists",
                "check": "Verify target file exists before processing",
                "on_failure": "stop_and_notify",
            })
            if "MOVE" in verbs:
                conditions.append({
                    "condition": "destination_accessible",
                    "check": "Verify destination directory is writable",
                    "on_failure": "create_dest_directory",
                })

        if "CUSTOMER" in nouns:
            conditions.append({
                "condition": "customer_record_valid",
                "check": "Verify customer identifier is resolved",
                "on_failure": "request_human_intervention",
            })

        if not conditions:
            conditions.append({
                "condition": "action_preconditions_met",
                "check": "Verify all action parameters and inputs are valid",
                "on_failure": "stop_and_notify",
            })

        return conditions

    def _infer_failure_policy(self, actions: List[str]) -> Dict[str, Any]:
        """Derive failure recovery and escalation policy."""
        return {
            "retry_count": 2,
            "backoff_seconds": 1.0,
            "on_final_failure": "record_error_and_notify_user",
            "require_manual_intervention": True,
        }

    def understand_workflow(self, actions: List[str]) -> Dict[str, Any]:
        """Return comprehensive semantic understanding of workflow."""
        if not actions:
            return {
                "intent": "Empty Workflow",
                "description": "No actions detected.",
                "trigger": {"type": "manual"},
                "variables": [],
                "conditions": [],
                "failure_policy": {"type": "stop"},
            }

        intent = self._infer_intent_title(actions)
        description = self._infer_description(actions)
        trigger = self._infer_trigger(actions[0])
        variables = self._infer_variables(actions)
        conditions = self._infer_conditions(actions)
        failure_policy = self._infer_failure_policy(actions)

        return {
            "intent": intent,
            "description": description,
            "trigger": trigger,
            "variables": variables,
            "conditions": conditions,
            "failure_policy": failure_policy,
        }
