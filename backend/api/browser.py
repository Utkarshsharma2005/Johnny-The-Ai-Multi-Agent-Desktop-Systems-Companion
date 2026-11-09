from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.tools.browser_automation import browser_controller
from backend.core.api_security import audit_log

router = APIRouter(prefix="/api/v1/browser", tags=["Browser"])

class NavigateRequest(BaseModel):
    url: str = Field(..., description="Web page URL starting with http:// or https://")

class BrowserActionRequest(BaseModel):
    action: str = Field(..., description="click | type | screenshot")
    selector: Optional[str] = Field(None, description="CSS selector or element text matcher")
    text: Optional[str] = Field(None, description="Text content for typing action")
    output_path: Optional[str] = Field(None, description="Output destination path for screenshot action")

@router.post("/navigate")
async def browser_navigate_endpoint(req: NavigateRequest, request: Request):
    """
    Navigates browser controller to specified URL and extracts page summary.
    """
    res = browser_controller.navigate(req.url)
    audit_log("browser_navigate", req.url, "success" if res.get("success") else "blocked_or_failed",
              request=request, severity="warn")
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error") or "Navigation failed")
    return res

@router.post("/action")
async def browser_action_endpoint(req: BrowserActionRequest, request: Request):
    """
    Performs browser interaction action (click, type, screenshot).
    """
    audit_log("browser_action", req.action, "performed", request=request, severity="info")
    act_clean = req.action.lower().strip()
    if act_clean == "click":
        if not req.selector:
            raise HTTPException(status_code=400, detail="Selector is required for click action.")
        return browser_controller.click_element(req.selector)
    elif act_clean == "type":
        if not req.selector or req.text is None:
            raise HTTPException(status_code=400, detail="Selector and text are required for type action.")
        return browser_controller.type_text(req.selector, req.text)
    elif act_clean == "screenshot":
        return browser_controller.take_screenshot(req.output_path)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown browser action '{req.action}'. Supported: click, type, screenshot.")

@router.get("/status")
async def browser_status_endpoint():
    """
    Returns active browser automation controller status.
    """
    return browser_controller.get_status()
