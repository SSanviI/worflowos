# workflowos/ai_engine/provider.py
"""Abstract AI provider interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

class AIProvider(ABC):
    @abstractmethod
    def understand_workflow(self, actions: List[str]) -> Dict[str, Any]:
        """Return a high-level semantic interpretation of observed actions.

        Must return a dict containing:
        * intent: str
        * description: str
        * trigger: dict
        * variables: list
        * conditions: list
        * failure_policy: dict
        """
        raise NotImplementedError
