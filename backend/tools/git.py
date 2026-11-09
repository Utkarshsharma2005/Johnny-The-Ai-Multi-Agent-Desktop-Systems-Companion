import subprocess
from typing import Dict, Any
from backend.tools.base import BaseTool
from backend.security.permissions import SecurityLevel

class GitStatusTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="git_status",
            description="Inspects git repository status.",
            security_level=SecurityLevel.LEVEL_0_SAFE_READ
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        res = subprocess.run(["git", "status", "--porcelain", "-b"], capture_output=True, text=True, timeout=5)
        return {"status": res.stdout.strip(), "raw_output": res.stdout, "is_git_repo": res.returncode == 0}

class GitDiffTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="git_diff",
            description="Inspects git repository changes/diff.",
            security_level=SecurityLevel.LEVEL_0_SAFE_READ
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "staged": {"type": "boolean", "description": "If true, shows staged diff"}
            }
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        cmd = ["git", "diff"]
        if arguments.get("staged"):
            cmd.append("--staged")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return {"diff": res.stdout.strip(), "has_changes": bool(res.stdout.strip())}

class GitCommitTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="git_commit",
            description="Stages files and creates a git commit.",
            security_level=SecurityLevel.LEVEL_1_LOW_RISK_MOD
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message string"}
            },
            "required": ["message"]
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        msg = arguments["message"]
        # Stage all changes
        subprocess.run(["git", "add", "."], check=True, timeout=5)
        res = subprocess.run(["git", "commit", "-m", msg], capture_output=True, text=True, timeout=5)
        return {"commit_message": msg, "output": res.stdout.strip(), "success": res.returncode == 0}

class GitBranchTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="git_branch",
            description="Lists git branches and current active branch.",
            security_level=SecurityLevel.LEVEL_0_SAFE_READ
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        res = subprocess.run(["git", "branch", "-a"], capture_output=True, text=True, timeout=5)
        return {"branches": res.stdout.strip().splitlines() if res.returncode == 0 else []}
