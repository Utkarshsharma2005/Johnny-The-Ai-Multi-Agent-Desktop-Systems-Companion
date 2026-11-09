import pytest

from backend.core.approvals import ApprovalBroker


def test_approval_is_bound_to_action_and_exact_arguments_and_is_one_use():
    broker = ApprovalBroker()
    args = {"command": "git status", "cwd": "."}
    request = broker.request("run_terminal_command", args)

    assert broker.resolve(request["id"], True)
    assert not broker.consume(request["id"], "run_terminal_command", {"command": "git clean -fd"})
    assert broker.consume(request["id"], "run_terminal_command", args)
    assert not broker.consume(request["id"], "run_terminal_command", args)


def test_task_approval_is_bound_to_task_and_step():
    broker = ApprovalBroker()
    args = {"file_path": "notes.txt"}
    request = broker.request("delete_file", args, task_id="task-a", step_number=2)
    assert broker.resolve(request["id"], True)
    assert not broker.consume(request["id"], "delete_file", args)
    assert not broker.consume(request["id"], "delete_file", args, task_id="task-a", step_number=1)
    assert broker.consume(request["id"], "delete_file", args, task_id="task-a", step_number=2)


def test_denial_and_expiry_do_not_issue_approval(monkeypatch):
    broker = ApprovalBroker()
    denied = broker.request("delete_file", {"file_path": "x"})
    assert broker.resolve(denied["id"], False)
    assert not broker.consume(denied["id"], "delete_file", {"file_path": "x"})

    expired = broker.request("delete_file", {"file_path": "y"})
    monkeypatch.setattr("backend.core.approvals.time.time", lambda: expired["expires_at"] + 1)
    assert not broker.resolve(expired["id"], True)


def test_explicit_approval_cannot_be_sent_as_a_boolean():
    from backend.api.tools import ToolExecuteRequest
    from backend.api.tasks import TaskCreateRequest

    with pytest.raises(Exception):
        ToolExecuteRequest(tool_name="delete_file", user_approved=True)
    with pytest.raises(Exception):
        TaskCreateRequest(goal="delete files", user_approved=True)


def test_task_pauses_then_resumes_once_after_server_approval(monkeypatch):
    from backend.agents.task_engine import AutonomousTaskEngine, TaskStatus, TaskStep
    from backend.core.approvals import approval_broker
    from backend.security.permissions import SecurityLevel
    from backend.tools.base import BaseTool
    from backend.tools.registry import tool_registry

    class DestructiveFixtureTool(BaseTool):
        def __init__(self):
            super().__init__("approval_fixture", "test-only", SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE)
            self.calls = 0

        @property
        def parameters_schema(self):
            return {"type": "object", "properties": {}}

        def _run_tool(self, arguments):
            self.calls += 1
            return {"changed": True}

    tool = DestructiveFixtureTool()
    monkeypatch.setitem(tool_registry._tools, tool.name, tool)
    monkeypatch.setattr("backend.agents.task_engine.task_store.save_checkpoint", lambda *_: None)
    monkeypatch.setattr("backend.agents.task_engine.verification_engine.run_full_verification",
                        lambda **_: {"is_verified": True, "confidence_score": 1.0, "failed_checks": []})
    engine = AutonomousTaskEngine()
    task = engine.create_task("fixture")
    task.steps = [TaskStep(1, "fixture action", tool.name, {})]

    paused = engine.execute_task(task.id)
    assert paused["status"] == TaskStatus.AWAITING_APPROVAL.value
    assert paused["verification_report"] is None
    assert "id" not in paused["pending_approval"]  # checkpoint-safe representation
    assert tool.calls == 0

    approval_id = task.pending_approval["id"]
    assert approval_broker.resolve(approval_id, True)
    completed = engine.execute_task(task.id, approval_id=approval_id)
    assert completed["status"] == TaskStatus.COMPLETED.value
    assert tool.calls == 1
