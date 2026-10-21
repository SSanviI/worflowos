# workflowos/automation/adapters/base.py
"""Base adapter class for WorkFlowOS automation actions."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
import re


class BaseAdapter(ABC):
    """Abstract base adapter for automation modules."""

    @classmethod
    def resolve_params(cls, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve variable placeholders in parameters using execution context.

        Example:
            params = {"source": "{file_path}", "target_dir": "{destination_dir}"}
            context = {"file_path": "C:\\temp\\data.txt", "destination_dir": "C:\\out"}
            returns: {"source": "C:\\temp\\data.txt", "target_dir": "C:\\out"}
        """
        resolved: Dict[str, Any] = {}
        for k, v in params.items():
            if isinstance(v, str):
                # Check for {var_name} placeholder
                match = re.match(r"^\{([a-zA-Z0-9_]+)\}$", v.strip())
                if match:
                    var_name = match.group(1)
                    resolved[k] = context.get(var_name, v)
                else:
                    # String template interpolation
                    def replace_var(m):
                        vn = m.group(1)
                        return str(context.get(vn, m.group(0)))
                    resolved[k] = re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_var, v)
            else:
                resolved[k] = v
        return resolved
