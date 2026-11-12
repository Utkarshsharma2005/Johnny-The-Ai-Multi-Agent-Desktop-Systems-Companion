import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional
from backend.core.verification_engine import verification_engine
from backend.tools.registry import tool_registry
from backend.core.agent_bus import agent_bus, EventType, AgentEvent
from backend.security.permissions import SecurityLevel
from backend.core.approvals import approval_broker

class TaskStatus(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"

class TaskStep:
    def __init__(self, step_number: int, description: str, tool_name: Optional[str] = None, tool_args: Optional[Dict[str, Any]] = None):
        self.step_number = step_number
        self.description = description
        self.tool_name = tool_name
        self.tool_args = tool_args or {}
        self.status = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
        self.output: Optional[Any] = None
        self.latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "description": self.description,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "status": self.status,
            "output": self.output,
            "latency_ms": self.latency_ms
        }

class Task:
    def __init__(self, id: str, goal: str, locked_requirements: Optional[Dict[str, Any]] = None):
        self.id = id
        self.goal = goal
        self.locked_requirements = locked_requirements or {}
        self.status = TaskStatus.PLANNING
        self.steps: List[TaskStep] = []
        self.verification_report: Optional[Dict[str, Any]] = None
        self.recovery_attempts: int = 0
        self.logs: List[str] = []
        self.created_at = time.time()
        self.updated_at = time.time()
        self.pending_approval: Optional[Dict[str, Any]] = None

    def add_log(self, message: str):
        timestamp_str = time.strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp_str}] {message}")
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        pending_approval = self.pending_approval
        if pending_approval:
            pending_approval = {k: v for k, v in pending_approval.items() if k != "id"}
        return {
            "id": self.id,
            "goal": self.goal,
            "locked_requirements": self.locked_requirements,
            "pending_approval": pending_approval,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "verification_report": self.verification_report,
            "recovery_attempts": self.recovery_attempts,
            "logs": self.logs,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

from backend.core.task_store import task_store

class AutonomousTaskEngine:
    """
    V0.5/V0.7 Autonomous Task Engine.
    Orchestrates multi-step task planning, controlled workspace tool execution,
    closed-loop verification, automated recovery loops, and atomic state checkpointing.
    """

    MAX_RECOVERY_ATTEMPTS = 2

    def __init__(self):
        self._tasks: Dict[str, Task] = {}

    def create_task(self, goal: str, locked_requirements: Optional[Dict[str, Any]] = None) -> Task:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = Task(id=task_id, goal=goal, locked_requirements=locked_requirements)
        task.add_log(f"Initialized autonomous task '{task_id}' for goal: {goal}")

        # Generate initial plan steps tailored to the goal
        task.steps = self._decompose_plan(goal, locked_requirements)
        task.add_log(f"Decomposed goal into {len(task.steps)} plan execution steps.")

        self._tasks[task_id] = task
        task_store.save_checkpoint(task.id, task.to_dict())

        # 🔔 Publish to agent bus
        agent_bus.publish(AgentEvent(
            type=EventType.TASK_STATUS,
            agent="planner",
            content=f"New task created [{task_id}]: {goal}",
            metadata={"task_id": task_id, "steps": len(task.steps)},
            severity="info",
        ))
        agent_bus.publish_thought(
            agent="planner",
            content=f"Decomposed goal into {len(task.steps)} execution steps. Beginning multi-agent coordination.",
        )
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def deny_approval(self, task_id: str) -> None:
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.AWAITING_APPROVAL:
            task.pending_approval = None
            task.status = TaskStatus.FAILED
            task.add_log("User denied the pending action approval; task stopped without executing it.")
            task_store.save_checkpoint(task.id, task.to_dict())

    def list_tasks(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._tasks.values()]

    def terminate_all_tasks(self) -> Dict[str, Any]:
        """
        Immediately cancels and terminates all running and pending tasks.
        """
        terminated_count = 0
        for task in self._tasks.values():
            if task.status in [TaskStatus.PLANNING, TaskStatus.EXECUTION, TaskStatus.VERIFYING, TaskStatus.RECOVERING, TaskStatus.AWAITING_APPROVAL]:
                if task.pending_approval:
                    approval_broker.resolve(task.pending_approval.get("id", ""), False)
                    task.pending_approval = None
                task.status = TaskStatus.FAILED
                task.add_log("🛑 Task TERMINATED by user emergency stop.")
                task_store.save_checkpoint(task.id, task.to_dict())
                terminated_count += 1
        return {"status": "success", "terminated_count": terminated_count}

    def restore_task(self, task_dict: Dict[str, Any]) -> Task:
        """
        Restores a Task instance from a saved checkpoint dictionary.
        """
        task = Task(
            id=task_dict["id"],
            goal=task_dict["goal"],
            locked_requirements=task_dict.get("locked_requirements")
        )
        task.status = TaskStatus(task_dict.get("status", TaskStatus.PLANNING.value))
        task.recovery_attempts = task_dict.get("recovery_attempts", 0)
        task.verification_report = task_dict.get("verification_report")
        task.logs = task_dict.get("logs", [])
        task.created_at = task_dict.get("created_at", time.time())
        task.updated_at = task_dict.get("updated_at", time.time())

        restored_steps = []
        for s in task_dict.get("steps", []):
            step = TaskStep(
                step_number=s["step_number"],
                description=s["description"],
                tool_name=s.get("tool_name"),
                tool_args=s.get("tool_args")
            )
            step.status = s.get("status", "PENDING")
            step.output = s.get("output")
            step.latency_ms = s.get("latency_ms", 0.0)
            restored_steps.append(step)

        task.steps = restored_steps
        self._tasks[task.id] = task
        return task

    def execute_task(self, task_id: str, approval_id: Optional[str] = None) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        task.status = TaskStatus.EXECUTION
        task.add_log("Commencing step-by-step tool execution pipeline.")
        task_store.save_checkpoint(task.id, task.to_dict())

        agent_bus.publish(AgentEvent(
            type=EventType.TASK_STATUS,
            agent="executor",
            content=f"Task [{task_id}] entering EXECUTION phase — {len(task.steps)} steps queued.",
            metadata={"task_id": task_id, "status": "EXECUTION"},
            severity="info",
        ))

        # Step 1: Execute each plan step (skipping completed ones if resuming)
        for step in task.steps:
            if step.status == "COMPLETED":
                task.add_log(f"Step {step.step_number} already COMPLETED (skipping).")
                continue

            step.status = "RUNNING"
            task.add_log(f"Executing Step {step.step_number}: {step.description}")
            task_store.save_checkpoint(task.id, task.to_dict())

            agent_bus.publish_action(
                agent="executor",
                action=f"Step {step.step_number}/{len(task.steps)}: {step.description}",
                metadata={"tool": step.tool_name, "args": step.tool_args},
            )

            if step.tool_name:
                start_step = time.perf_counter()

                # ── SECURITY: never auto-approve Level 2/3 tool usage ─────────
                # Level 0/1 run autonomously; Level 2/3 require explicit user
                # approval (via the agent-bus permission flow) before executing.
                tool = tool_registry.get_tool(step.tool_name)
                tool_level = (tool.required_security_level(step.tool_args) if tool is not None and hasattr(tool, "required_security_level") else tool.security_level) if tool is not None else \
                    SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE
                approved_this_step = False
                if tool_level >= SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE:
                    if approval_id and approval_broker.consume(approval_id, step.tool_name, step.tool_args,
                                                               task_id=task.id, step_number=step.step_number):
                        approved_this_step = True
                        task.pending_approval = None
                    else:
                        task.pending_approval = approval_broker.request(
                            step.tool_name, step.tool_args, task_id=task.id,
                            step_number=step.step_number, risk_level=int(tool_level))
                    step.status = "PENDING"
                    approval_note = (
                        f"Step {step.step_number} requires LEVEL {tool_level.value} user "
                        f"approval — execution paused pending agent-bus approval."
                    )
                    if not approved_this_step:
                        task.status = TaskStatus.AWAITING_APPROVAL
                        task.add_log(approval_note)
                        agent_bus.publish_debate(
                            agent="critic",
                            target="planner",
                            content=f"Step {step.step_number} ({step.tool_name}) requires Level {tool_level.value} elevated privileges. Gating execution for explicit user confirmation.",
                            severity="warn"
                        )
                        agent_bus.publish(AgentEvent(type=EventType.PERMISSION_REQ, agent="executor",
                            content=approval_note, metadata=self._approval_metadata(task.pending_approval),
                            severity="critical" if tool_level == SecurityLevel.LEVEL_3_DANGEROUS_SYSTEM else "warn"))
                        task_store.save_checkpoint(task.id, task.to_dict())
                        return task.to_dict()

                tool_res = tool_registry.execute_tool(
                    name=step.tool_name,
                    arguments=step.tool_args,
                    user_approved=approved_this_step,
                )
                step.latency_ms = round((time.perf_counter() - start_step) * 1000.0, 2)
                step.output = tool_res

                if tool_res.get("success"):
                    step.status = "COMPLETED"
                    task.add_log(f"Step {step.step_number} SUCCEEDED ({step.latency_ms}ms).")
                    agent_bus.publish_result(
                        agent="executor",
                        content=f"Step {step.step_number} completed in {step.latency_ms}ms ✓",
                        success=True,
                    )
                else:
                    step.status = "FAILED"
                    task.add_log(f"Step {step.step_number} FAILED: {tool_res.get('error')}")
                    agent_bus.publish_result(
                        agent="executor",
                        content=f"Step {step.step_number} failed: {tool_res.get('error', 'unknown error')}",
                        success=False,
                    )
                    agent_bus.publish_debate(
                        agent="critic",
                        target="executor",
                        content=f"Step {step.step_number} failed. Should we retry or abort? Escalating to verifier.",
                        severity="warn",
                    )
            else:
                step.status = "COMPLETED"
                step.output = {"success": True, "message": "Manual / Analytical step completed."}

            task_store.save_checkpoint(task.id, task.to_dict())

        # Step 2: Trigger Closed-Loop Verification
        task.status = TaskStatus.VERIFYING
        task.add_log("Tool execution complete. Triggering closed-loop VerificationEngine pipeline.")
        task_store.save_checkpoint(task.id, task.to_dict())

        agent_bus.publish(AgentEvent(
            type=EventType.AGENT_THOUGHT,
            agent="verifier",
            content="All steps executed. Running closed-loop verification pipeline (LINT + HEALTH_CHECK)…",
            severity="info",
        ))

        v_report = verification_engine.run_full_verification(checks=["LINT", "HEALTH_CHECK"])
        task.verification_report = v_report

        if v_report["is_verified"]:
            task.status = TaskStatus.COMPLETED
            task.add_log(f"Verification PASSED with confidence score {v_report['confidence_score']:.2f}. Task COMPLETED.")
            agent_bus.publish_decision(
                agent="verifier",
                content=f"Task VERIFIED ✅ — confidence {v_report['confidence_score']:.0%}. Task marked COMPLETED.",
                metadata={"confidence": v_report["confidence_score"]},
            )
        else:
            # Step 3: Trigger Controlled Recovery Loop if verification failed
            task.add_log(f"Verification FAILED. Failed checks: {v_report['failed_checks']}")
            agent_bus.publish_debate(
                agent="verifier",
                target="planner",
                content=f"Verification FAILED on checks: {v_report['failed_checks']}. Initiating recovery loop.",
                severity="warn",
            )
            self._attempt_recovery_loop(task)

        task_store.save_checkpoint(task.id, task.to_dict())
        return task.to_dict()

    @staticmethod
    def _approval_metadata(approval: Dict[str, Any]) -> Dict[str, Any]:
        return {k: approval.get(k) for k in ("id", "task_id", "step_number", "action", "arguments", "risk_level", "expires_at")}

    def _attempt_recovery_loop(self, task: Task):
        """
        Attempts controlled recovery when closed-loop verification fails.
        """
        while task.recovery_attempts < self.MAX_RECOVERY_ATTEMPTS:
            task.recovery_attempts += 1
            task.status = TaskStatus.RECOVERING
            task.add_log(f"Recovery Attempt {task.recovery_attempts}/{self.MAX_RECOVERY_ATTEMPTS}: Inspecting failure logs...")
            task_store.save_checkpoint(task.id, task.to_dict())

            # Simple recovery action: re-run lint / safe cleanup
            rec_res = tool_registry.execute_tool("list_dir", {"dir_path": "."})
            task.add_log(f"Recovery inspection completed. Re-triggering verification pipeline...")

            re_report = verification_engine.run_full_verification(checks=["LINT", "HEALTH_CHECK"])
            task.verification_report = re_report

            if re_report["is_verified"]:
                task.status = TaskStatus.COMPLETED
                task.add_log(f"Recovery Attempt {task.recovery_attempts} SUCCEEDED! Task COMPLETED.")
                task_store.save_checkpoint(task.id, task.to_dict())
                return

        task.status = TaskStatus.FAILED
        task.add_log(f"Task FAILED after {task.recovery_attempts} recovery attempts. Requires user inspection.")
        task_store.save_checkpoint(task.id, task.to_dict())

    def _decompose_plan(self, goal: str, locked: Optional[Dict[str, Any]] = None) -> List[TaskStep]:
        """
        Dynamically decomposes user goals into structured, phased task execution steps
        matched to available workspace, browser, git, and terminal tools.
        Uses exact token boundaries and priority ordering to prevent intent collisions.
        """
        import re
        goal_lower = goal.lower().strip()

        # Extract full URL — strip surrounding prose delimiters like `(`, `)`, `"`, `'`, `.` from the match
        url_match = re.search(r'https?://[^\s\'"<>()\[\]]+', goal)
        host_match = None
        if url_match:
            target_url = url_match.group(0).rstrip(".,;:!?)")
        else:
            # Bare-domain normalization (e.g. docs.python.org → https://docs.python.org),
            # also strip trailing punctuation
            host_match = re.search(r'\b(?:[a-zA-Z0-9-]+\.)+(?:org|com|net|io|dev|edu|gov|co|ai)\b[^\s\'"()]*', goal)
            target_url = f"https://{host_match.group(0).rstrip('.,;:!?)')}" if host_match else None

        # Build a URL-scrubbed version of goal_lower for keyword matching so that words
        # inside URLs (e.g. "git" in "github.com", "docker" in "hub.docker.com") don't
        # trigger operation-specific steps unintentionally.
        scrubbed_lower = re.sub(r'https?://\S+', '', goal_lower)
        if host_match:
            scrubbed_lower = re.sub(re.escape(host_match.group(0).lower()), '', scrubbed_lower)
        scrubbed_lower = scrubbed_lower.strip()

        # ── 1. Version Control & Git Operations (high precedence over general 'check') ──
        if re.search(r'\b(git|commit|diff|branch|push|rebase|stash|pull request|pr)\b', scrubbed_lower):
            return [
                TaskStep(1, "Inspect git repository status and modified files", tool_name="git_status", tool_args={}),
                TaskStep(2, "Review active code diffs across workspace", tool_name="git_diff", tool_args={}),
                TaskStep(3, "Verify branch consistency against project spec", tool_name="read_file", tool_args={"file_path": "README.md"})
            ]

        # ── 2. Docker & Container Management ──────────────────────────────
        if re.search(r'\b(docker|container|dockerfile|compose)\b', scrubbed_lower):
            return [
                TaskStep(1, "Inspect active Docker containers", tool_name="docker_ps", tool_args={}),
                TaskStep(2, "Inspect workspace container configuration", tool_name="list_dir", tool_args={"dir_path": "."})
            ]

        # ── 3. Web & Browser Automation Goals ──────────────────────────────
        # Only select browser plan when the goal contains an explicit browser verb.
        # A URL alone is not sufficient — it may appear in an integration-test or webhook goal.
        # target_url remains available as context for other operations.
        explicit_browser_verb = bool(re.search(r'\b(browse|browser|navigate|website|webpage|scrape)\b', scrubbed_lower))
        is_browser_intent = explicit_browser_verb
        if is_browser_intent:
            if target_url:
                return [
                    TaskStep(1, f"Navigate browser controller to {target_url}", tool_name="browser_navigate", tool_args={"url": target_url}),
                    TaskStep(2, "Capture rendered page viewport screenshot & inspect DOM", tool_name="browser_screenshot", tool_args={}),
                    TaskStep(3, "Verify extracted content & interactive links", tool_name="list_dir", tool_args={"dir_path": ".johnny/browser_screenshots"})
                ]
            else:
                # No destination URL specified — inspect workspace documentation first to locate target
                return [
                    TaskStep(1, "Inspect workspace documentation to identify target service URL", tool_name="read_file", tool_args={"file_path": "README.md"}),
                    TaskStep(2, "Inspect active directory configuration", tool_name="list_dir", tool_args={"dir_path": "."})
                ]

        # ── 4. Test Execution & Quality Assurance ──────────────────────────
        if re.search(r'\b(pytest|test|tests|test suite|unit test|integration test)\b', scrubbed_lower):
            return [
                TaskStep(1, "Inspect repository and active working state", tool_name="git_status", tool_args={}),
                TaskStep(2, "Inspect test suite directory and test manifests", tool_name="list_dir", tool_args={"dir_path": "tests"}),
                TaskStep(3, "Execute automated test verification in sandbox", tool_name="run_terminal_command", tool_args={"command": "MODEL_PROVIDER=mock pytest tests/ -q"})
            ]

        # ── 5. General Engineering & Architecture ──────────────────────────
        return [
            TaskStep(1, "Inspect workspace file tree & dependencies", tool_name="list_dir", tool_args={"dir_path": "."}),
            TaskStep(2, "Inspect active repository status & branch", tool_name="git_status", tool_args={}),
            TaskStep(3, "Inspect project architecture & requirements", tool_name="read_file", tool_args={"file_path": "README.md"}),
            TaskStep(4, "Run sandbox verification checks", tool_name="run_terminal_command", tool_args={"command": "MODEL_PROVIDER=mock pytest tests/ -q"})
        ]

# Global singleton task engine instance
task_engine = AutonomousTaskEngine()
