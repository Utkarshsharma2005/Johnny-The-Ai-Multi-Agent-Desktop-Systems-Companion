
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.tools.browser_automation import BrowserAutomationController
from backend.tools.registry import tool_registry


def test_browser_controller_url_security_validation():
    controller = BrowserAutomationController()
    
    # Non-http/https schemes should be rejected in dict response
    res1 = controller.navigate("file:///etc/passwd")
    assert res1["success"] is False
    assert "Blocked scheme" in res1["error"]

    res2 = controller.navigate("ftp://example.com/file.txt")
    assert res2["success"] is False
    assert "Blocked scheme" in res2["error"]

    res3 = controller.navigate("javascript:alert(1)")
    assert res3["success"] is False
    assert "Blocked scheme" in res3["error"]


def test_browser_controller_navigation_and_action_flow():
    controller = BrowserAutomationController()

    nav_res = controller.navigate("https://example.com")
    assert nav_res["success"] is True
    assert nav_res["url"] == "https://example.com"
    assert "content_snippet" in nav_res

    status = controller.get_status()
    assert status["active_url"] == "https://example.com"
    assert status["active_title"] != ""

    click_res = controller.click_element("button#submit")
    assert click_res["success"] is True
    assert click_res["action"] == "CLICK"
    assert click_res["selector"] == "button#submit"

    type_res = controller.type_text("input#search", "Johnny AI")
    assert type_res["success"] is True
    assert type_res["action"] == "TYPE"
    assert type_res["selector"] == "input#search"
    assert type_res["text_entered"] == "Johnny AI"

    screenshot_res = controller.take_screenshot()
    assert screenshot_res["success"] is True
    assert "screenshot_path" in screenshot_res


def test_browser_tools_in_registry():
    nav_tool = tool_registry.get_tool("browser_navigate")
    assert nav_tool is not None

    click_tool = tool_registry.get_tool("browser_click")
    assert click_tool is not None

    type_tool = tool_registry.get_tool("browser_type")
    assert type_tool is not None

    screenshot_tool = tool_registry.get_tool("browser_screenshot")
    assert screenshot_tool is not None

    nav_result = tool_registry.execute_tool("browser_navigate", {"url": "https://example.org"})
    assert nav_result["success"] is True
    assert nav_result["result"]["url"] == "https://example.org"

    screenshot_result = tool_registry.execute_tool("browser_screenshot", {})
    assert screenshot_result["success"] is True
    assert "screenshot_path" in screenshot_result["result"]


@pytest.mark.asyncio
async def test_browser_api_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Test Status initial
        res_status = await ac.get("/api/v1/browser/status")
        assert res_status.status_code == 200
        assert "active_url" in res_status.json()

        # 2. Test Navigate valid URL
        res_nav = await ac.post("/api/v1/browser/navigate", json={"url": "https://python.org"})
        assert res_nav.status_code == 200
        nav_data = res_nav.json()
        assert nav_data["success"] is True
        assert nav_data["url"] == "https://python.org"

        # 3. Test Navigate invalid URL scheme (Security Check)
        res_invalid = await ac.post("/api/v1/browser/navigate", json={"url": "file:///etc/shadow"})
        assert res_invalid.status_code == 400
        assert "Blocked scheme" in res_invalid.json()["detail"]

        # 4. Test Browser Action - Click
        res_click = await ac.post("/api/v1/browser/action", json={"action": "click", "selector": "#login-btn"})
        assert res_click.status_code == 200
        assert res_click.json()["success"] is True

        # 5. Test Browser Action - Type
        res_type = await ac.post("/api/v1/browser/action", json={"action": "type", "selector": "#username", "text": "johnny_user"})
        assert res_type.status_code == 200
        assert res_type.json()["success"] is True

        # 6. Test Browser Action - Screenshot
        res_ss = await ac.post("/api/v1/browser/action", json={"action": "screenshot"})
        assert res_ss.status_code == 200
        assert res_ss.json()["success"] is True
        assert "screenshot_path" in res_ss.json()
