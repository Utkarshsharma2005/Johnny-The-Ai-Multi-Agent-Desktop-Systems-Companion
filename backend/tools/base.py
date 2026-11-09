import time
from abc import ABC, abstractmethod
from typing import Dict, Any
from backend.security.permissions import PermissionManager, SecurityLevel

class BaseTool(ABC):
    """
    Abstract Base Class for all Johnny Controlled Workspace Tools.
    Enforces security sandboxing and performance measurement for all tool executions.
    """

    def __init__(self, name: str, description: str, security_level: SecurityLevel):
        self.name = name
        self.description = description
        self.security_level = security_level

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """Returns JSON schema for tool argument validation."""
        pass

    def execute(self, arguments: Dict[str, Any], user_approved: bool = False) -> Dict[str, Any]:
        """
        Validates security permission and executes the tool with latency measurement.
        """
        # Validate permissions
        granted, reason = PermissionManager.validate_tool_call(
            tool_name=self.name,
            arguments=arguments,
            required_level=self.security_level,
            user_approved=user_approved
        )

        if not granted:
            return {
                "success": False,
                "tool_name": self.name,
                "error": reason,
                "security_level": self.security_level.value,
                "latency_ms": 0.0
            }

        start_time = time.perf_counter()
        try:
            result = self._run_tool(arguments)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            
            return {
                "success": True,
                "tool_name": self.name,
                "result": result,
                "security_level": self.security_level.value,
                "latency_ms": elapsed_ms
            }
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return {
                "success": False,
                "tool_name": self.name,
                "error": f"Tool execution failed: {str(e)}",
                "security_level": self.security_level.value,
                "latency_ms": elapsed_ms
            }

    @abstractmethod
    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        """Core tool logic implemented by subclass tools."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Returns full tool metadata schema for LLM tool selection."""
        return {
            "name": self.name,
            "description": self.description,
            "security_level": self.security_level.value,
            "parameters": self.parameters_schema
        }
