# workflowos/ai_engine/gemini_provider.py
"""Gemini LLM provider for deep semantic workflow analysis."""

import os
import json
import requests
from typing import List, Dict, Any

from .provider import AIProvider
from .local_fallback import LocalFallbackProvider
from ..backend.config import GEMINI_API_KEY


class GeminiProvider(AIProvider):
    def __init__(self):
        self.api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("Gemini API key not configured")
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        self.headers = {"Content-Type": "application/json"}
        self._fallback = LocalFallbackProvider()

    def _build_prompt(self, actions: List[str]) -> str:
        actions_str = ", ".join(actions)
        return (
            f"Analyze this sequence of user OS activity actions: [{actions_str}].\n"
            "Generate a structured workflow understanding in valid JSON format with the following keys:\n"
            "- 'intent': Concise, professional title of what the user is accomplishing (e.g. 'Organize and Archive Files', 'Customer Onboarding Flow').\n"
            "- 'description': Step-by-step clear summary of the workflow purpose.\n"
            "- 'trigger': JSON object with 'type' and 'source' describing how this workflow is triggered.\n"
            "- 'variables': List of variable objects with 'name', 'type', and 'description'.\n"
            "- 'conditions': List of condition objects with 'condition', 'check', and 'on_failure'.\n"
            "- 'failure_policy': JSON object with 'retry_count' and 'on_final_failure'.\n"
            "Return ONLY raw JSON."
        )

    def understand_workflow(self, actions: List[str]) -> Dict[str, Any]:
        payload = {
            "contents": [{"parts": [{"text": self._build_prompt(actions)}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        params = {"key": self.api_key}
        try:
            resp = requests.post(self.endpoint, params=params, headers=self.headers, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            
            # Clean markdown formatting if present
            clean_text = text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            
            result = json.loads(clean_text.strip())
            if isinstance(result, dict) and "intent" in result and "description" in result:
                # Merge with fallback defaults for missing fields
                fallback_val = self._fallback.understand_workflow(actions)
                return {
                    "intent": result.get("intent", fallback_val["intent"]),
                    "description": result.get("description", fallback_val["description"]),
                    "trigger": result.get("trigger", fallback_val["trigger"]),
                    "variables": result.get("variables", fallback_val["variables"]),
                    "conditions": result.get("conditions", fallback_val["conditions"]),
                    "failure_policy": result.get("failure_policy", fallback_val["failure_policy"]),
                }
        except Exception as exc:
            pass

        # If Gemini API call fails or key is invalid, use compositional local provider
        return self._fallback.understand_workflow(actions)
