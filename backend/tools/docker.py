import subprocess
from typing import Dict, Any
from backend.tools.base import BaseTool
from backend.security.permissions import SecurityLevel

class DockerPsTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="docker_ps",
            description="Lists active Docker containers.",
            security_level=SecurityLevel.LEVEL_0_SAFE_READ
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "all": {"type": "boolean", "description": "If true, includes stopped containers"}
            }
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        cmd = ["docker", "ps", "--format", "json"]
        if arguments.get("all"):
            cmd.append("-a")
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode != 0:
                return {"docker_available": False, "error": res.stderr.strip()}
            return {"docker_available": True, "output": res.stdout.strip()}
        except Exception as e:
            return {"docker_available": False, "error": str(e)}

class DockerLogsTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="docker_logs",
            description="Fetches recent logs from a Docker container.",
            security_level=SecurityLevel.LEVEL_0_SAFE_READ
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "container_id": {"type": "string", "description": "Container ID or name"},
                "tail": {"type": "integer", "description": "Number of lines to tail (default: 50)"}
            },
            "required": ["container_id"]
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        container_id = arguments["container_id"]
        tail = arguments.get("tail", 50)

        cmd = ["docker", "logs", "--tail", str(tail), container_id]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return {
                "container_id": container_id,
                "logs": res.stdout.strip() or res.stderr.strip(),
                "success": res.returncode == 0
            }
        except Exception as e:
            return {"container_id": container_id, "logs": "", "error": str(e), "success": False}
