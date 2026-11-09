from typing import Dict, Any, List, Optional
from backend.tools.base import BaseTool
from backend.tools.filesystem import ReadFileTool, ListDirTool, WriteFileTool, DeleteFileTool
from backend.tools.terminal import RunTerminalCommandTool
from backend.tools.git import GitStatusTool, GitDiffTool, GitCommitTool, GitBranchTool
from backend.tools.docker import DockerPsTool, DockerLogsTool
from backend.tools.browser_automation import (
    BrowserNavigateTool,
    BrowserClickTool,
    BrowserTypeTool,
    BrowserScreenshotTool
)

class ToolRegistry:
    """
    Central Tool Registry for Johnny Controlled Workspace Tools.
    Dispatches tool execution requests through permission validation.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._register_default_tools()

    def register_tool(self, tool: BaseTool):
        """Registers a tool instance in the registry."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieves a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns schemas for all registered tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    def execute_tool(self, name: str, arguments: Dict[str, Any], user_approved: bool = False) -> Dict[str, Any]:
        """
        Executes a registered tool by name after validating permissions.
        """
        tool = self.get_tool(name)
        if not tool:
            return {
                "success": False,
                "tool_name": name,
                "error": f"Tool '{name}' is not registered in ToolRegistry. Available tools: {list(self._tools.keys())}",
                "security_level": 0,
                "latency_ms": 0.0
            }

        return tool.execute(arguments, user_approved=user_approved)

    def _register_default_tools(self):
        """Instantiates and registers default V0.4/V0.9 workspace and browser tools."""
        defaults = [
            ReadFileTool(),
            ListDirTool(),
            WriteFileTool(),
            DeleteFileTool(),
            RunTerminalCommandTool(),
            GitStatusTool(),
            GitDiffTool(),
            GitCommitTool(),
            GitBranchTool(),
            DockerPsTool(),
            DockerLogsTool(),
            BrowserNavigateTool(),
            BrowserClickTool(),
            BrowserTypeTool(),
            BrowserScreenshotTool()
        ]
        for tool in defaults:
            self.register_tool(tool)

# Global singleton tool registry instance
tool_registry = ToolRegistry()
