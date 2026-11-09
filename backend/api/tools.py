from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional

from backend.tools.registry import tool_registry
from backend.core.api_security import audit_log
from backend.core.approvals import approval_broker
from backend.security.permissions import SecurityLevel
from backend.core.agent_bus import agent_bus, AgentEvent, EventType

router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])

class ToolExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_name: str = Field(..., description="Target tool name to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments dictionary for the tool")
    approval_id: Optional[str] = Field(None, description="One-use server-issued approval ticket")

@router.get("")
async def list_registered_tools():
    """
    Returns list of all available workspace tools, descriptions, and security levels.
    """
    return {
        "total_tools": len(tool_registry._tools),
        "tools": tool_registry.list_tools()
    }

@router.post("/execute")
async def execute_tool(req: ToolExecuteRequest, request: Request):
    """
    Executes a workspace tool through permission sandbox validation.
    """
    tool = tool_registry.get_tool(req.tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{req.tool_name}' is not registered.")
    required = tool.required_security_level(req.arguments) if hasattr(tool, "required_security_level") else tool.security_level
    if required >= SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE:
        if not req.approval_id:
            approval = approval_broker.request(req.tool_name, req.arguments, risk_level=int(required))
            agent_bus.publish(AgentEvent(type=EventType.PERMISSION_REQ, agent="executor",
                content=f"Tool action {req.tool_name} requires explicit approval.",
                metadata=approval, severity="critical" if required == SecurityLevel.LEVEL_3_DANGEROUS_SYSTEM else "warn"))
            return {"success": False, "tool_name": req.tool_name, "security_level": int(required),
                    "latency_ms": 0.0, "approval_required": True, "approval": approval}
        if not approval_broker.consume(req.approval_id, req.tool_name, req.arguments):
            raise HTTPException(status_code=403, detail="Approval is missing, expired, denied, already used, or does not match this exact action.")
    result = tool_registry.execute_tool(name=req.tool_name, arguments=req.arguments,
                                        user_approved=required >= SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE)

    audit_log(
        "tool_execute",
        f"{req.tool_name}({str(req.arguments)[:120]})",
        "success" if result.get("success") else "failed",
        request=request,
        severity="warn" if required >= SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE else "info",
    )

    if not result["success"] and "not registered" in result.get("error", ""):
        raise HTTPException(status_code=404, detail=result["error"])

    return result
