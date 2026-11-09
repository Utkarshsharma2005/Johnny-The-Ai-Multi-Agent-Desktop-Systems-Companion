import pytest
import os
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.security.permissions import PermissionManager, SecurityLevel
from backend.tools.registry import tool_registry

def test_permission_manager_sandboxing():
    # Level 0 automated safe read
    granted, msg = PermissionManager.validate_tool_call("read_file", {"file_path": "README.md"}, SecurityLevel.LEVEL_0_SAFE_READ)
    assert granted is True

    # Level 2 destructive without user approval -> DENIED
    granted, msg = PermissionManager.validate_tool_call("delete_file", {"file_path": "test.tmp"}, SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE, user_approved=False)
    assert granted is False
    assert "Permission DENIED" in msg

    # Level 2 destructive WITH user approval -> GRANTED
    granted, msg = PermissionManager.validate_tool_call("delete_file", {"file_path": "test.tmp"}, SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE, user_approved=True)
    assert granted is True

    # Forbidden pattern -> DENIED even with approval
    granted, msg = PermissionManager.validate_tool_call("run_terminal_command", {"command": "rm -rf /"}, SecurityLevel.LEVEL_1_LOW_RISK_MOD, user_approved=True)
    assert granted is False
    assert "forbidden" in msg.lower()

def test_filesystem_tools():
    # Write file
    res_write = tool_registry.execute_tool("write_file", {"file_path": "tests_tmp_sample.txt", "content": "Johnny test content"})
    assert res_write["success"] is True

    # Read file
    res_read = tool_registry.execute_tool("read_file", {"file_path": "tests_tmp_sample.txt"})
    assert res_read["success"] is True
    assert res_read["result"]["content"] == "Johnny test content"

    # List dir
    res_list = tool_registry.execute_tool("list_dir", {"dir_path": "."})
    assert res_list["success"] is True
    assert res_list["result"]["total_items"] > 0

    # Delete file without approval -> DENIED
    res_del_denied = tool_registry.execute_tool("delete_file", {"file_path": "tests_tmp_sample.txt"}, user_approved=False)
    assert res_del_denied["success"] is False

    # Delete file WITH approval -> SUCCEEDED
    res_del_ok = tool_registry.execute_tool("delete_file", {"file_path": "tests_tmp_sample.txt"}, user_approved=True)
    assert res_del_ok["success"] is True

def test_terminal_command_tool():
    res = tool_registry.execute_tool("run_terminal_command", {"command": "echo 'Hello Johnny Terminal'"})
    assert res["success"] is True
    assert "Hello Johnny Terminal" in res["result"]["stdout"]

def test_git_tools():
    res_status = tool_registry.execute_tool("git_status", {})
    assert res_status["success"] is True
    assert "is_git_repo" in res_status["result"]

@pytest.mark.asyncio
async def test_tools_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/v1/tools
        res_list = await client.get("/api/v1/tools")
        assert res_list.status_code == 200
        data = res_list.json()
        assert data["total_tools"] > 0

        # POST /api/v1/tools/execute (safe tool)
        res_exec = await client.post("/api/v1/tools/execute", json={"tool_name": "list_dir", "arguments": {"dir_path": "."}})
        assert res_exec.status_code == 200
        assert res_exec.json()["success"] is True

        # POST /api/v1/tools/execute (unregistered tool -> 404)
        res_invalid = await client.post("/api/v1/tools/execute", json={"tool_name": "non_existent_tool", "arguments": {}})
        assert res_invalid.status_code == 404
