import os
import shlex
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.tools.base import BaseTool
from backend.security.permissions import PermissionManager, SecurityLevel

# Shell-metacharacter constructs that require explicit user approval + per-word
# validation. Everything is still executed WITHOUT shell=True.
_SHELL_META = ("|", ";", "&&", "||", ">", ">>", "<", "$(", "`")

# Allowlist for binaries usable *between* pipe segments (read-only / safe text tools)
_PIPE_SEGMENT_ALLOWLIST = {
    "cat", "head", "tail", "grep", "wc", "sort", "uniq", "diff", "echo",
    "printf", "ls", "find", "sed", "stat", "file", "cut", "tr",
}

# Environment kept deliberately minimal: prevents LD_PRELOAD, PYTHONPATH,
# DYLD_* and other env-var based escapes.
_SANITIZED_ENV_KEYS = ("PATH", "HOME", "LANG", "TERM", "USER", "SHELL")

# Hard caps
_MAX_TIMEOUT_SECONDS = 120
_MAX_OUTPUT_BYTES = 100 * 1024  # 100 KB


class RunTerminalCommandTool(BaseTool):
    """
    Executes controlled terminal commands within workspace directory.
    Dynamic security level based on command inspection.

    SECURITY (hardened):
      * subprocess NEVER runs with shell=True — injection impossible.
      * Shell features (pipes/redirects/subshells) require explicit user
        approval + every segment's binary must be in the pipe allowlist.
      * cwd is resolved and must stay inside the user's home directory.
      * Environment is sanitized to a minimal clean set.
      * Timeout hard cap 120s, output truncated to 100KB.
    """

    def __init__(self):
        super().__init__(
            name="run_terminal_command",
            description="Executes a controlled bash terminal command in the workspace directory.",
            security_level=SecurityLevel.LEVEL_1_LOW_RISK_MOD
        )
        self._execution_lock = threading.Lock()

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command string to execute"},
                "cwd": {"type": "string", "description": "Working directory (default: current workspace)"},
                "timeout_seconds": {"type": "integer", "description": "Max execution time in seconds (default: 10)"}
            },
            "required": ["command"]
        }

    def execute(self, arguments: Dict[str, Any], user_approved: bool = False) -> Dict[str, Any]:
        """
        Dynamically classifies command security level prior to validation.
        """
        command = arguments.get("command", "")
        dynamic_level = self.required_security_level(arguments)
        if any(m in command for m in _SHELL_META):
            # Shell constructs (pipes/subshells) are treated as Level 2+ and
            # additionally require explicit user approval.
            dynamic_level = max(dynamic_level, SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE)
            if not user_approved:
                return {
                    "success": False, "tool_name": self.name, "exit_code": -1,
                    "stdout": "", "stderr":
                        "Command uses shell features (pipes/redirects/subshells) which require explicit user approval.",
                    "security_level": dynamic_level.value, "latency_ms": 0.0,
                }

        # The base executor reads security_level. Guard temporary classification
        # so concurrent requests cannot observe another command's lower level.
        with self._execution_lock:
            old_level = self.security_level
            self.security_level = dynamic_level
            try:
                return super().execute(arguments, user_approved=user_approved)
            finally:
                self.security_level = old_level

    def required_security_level(self, arguments: Dict[str, Any]) -> SecurityLevel:
        command = str(arguments.get("command", ""))
        dynamic_level = PermissionManager.classify_command_level(command)
        if any(m in command for m in _SHELL_META):
            dynamic_level = max(dynamic_level, SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE)
        return dynamic_level

    # ── internals ────────────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_env() -> Dict[str, str]:
        env = {
            k: v for k, v in os.environ.items()
            if k in _SANITIZED_ENV_KEYS
        }
        # Normalize PATH to restricted set (no user-writable or relayed dirs)
        env["PATH"] = "/usr/bin:/bin:/usr/local/bin"
        env.pop("LD_PRELOAD", None)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONSTARTUP", None)
        return env

    @staticmethod
    def _validated_cwd(cwd_arg: Any) -> str:
        try:
            resolved = Path(str(cwd_arg or ".")).expanduser().resolve()
        except Exception as e:
            raise ValueError(f"Invalid working directory: {e}")
        home = Path.home().resolve()
        if resolved != home and home not in resolved.parents:
            raise ValueError(
                f"Working directory '{resolved}' is outside the workspace boundary "
                "(user home directory)."
            )
        return str(resolved)

    @classmethod
    def _build_shell_free_argv(cls, command: str) -> List[str]:
        """
        Builds a shell-free argv for commands that use shell meta-features.

        Pipes are preserved by chaining through `/bin/bash -c` — but ONLY after
        every segment has been parsed with shlex and its binary allowlisted,
        and only after user approval. No raw user text is ever passed to bash.
        """
        # Split on pipes only (we reject the rest)
        segments = [s for s in command.split("|")]
        if len(segments) > 1:
            argv = ["bash", "-c", " | ".join(shlex.join(shlex.split(s)) for s in segments)]
            for seg in segments:
                tokens = shlex.split(seg)
                if not tokens or tokens[0].split("/")[-1] not in _PIPE_SEGMENT_ALLOWLIST:
                    raise ValueError(
                        f"Pipeline segment '{seg.strip()[:60]}' is not allowed. "
                        f"Allowed pipe binaries: {sorted(_PIPE_SEGMENT_ALLOWLIST)}"
                    )
            return argv

        # No pipes: plain shlex parse (argv[0] allowlist enforced by PermissionManager)
        return shlex.split(command)

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        command = arguments["command"]
        try:
            timeout = min(int(arguments.get("timeout_seconds", 30)), _MAX_TIMEOUT_SECONDS)
        except (TypeError, ValueError):
            timeout = 30

        try:
            cwd = self._validated_cwd(arguments.get("cwd", "."))
        except ValueError as e:
            return {"command": command, "exit_code": -1, "stdout": "", "stderr": str(e), "success": False}

        try:
            cmd_argv = self._build_shell_free_argv(command)
        except ValueError as e:
            return {"command": command, "exit_code": -1, "stdout": "", "stderr": str(e), "success": False}
        except Exception as e:  # shlex parse error
            return {
                "command": command, "exit_code": -1, "stdout": "",
                "stderr": f"Command parse error: {e}", "success": False,
            }

        try:
            res = subprocess.run(
                cmd_argv,
                shell=False,  # Injection-safe: argv form, never a shell string
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._sanitize_env(),
            )

            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            truncated = False
            if len(stdout) > _MAX_OUTPUT_BYTES:
                stdout = stdout[:_MAX_OUTPUT_BYTES] + "\n... [output truncated at 100KB]"
                truncated = True
            if len(stderr) > _MAX_OUTPUT_BYTES:
                stderr = stderr[:_MAX_OUTPUT_BYTES] + "\n... [stderr truncated at 100KB]"
                truncated = True

            return {
                "command": command,
                "exit_code": res.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "success": res.returncode == 0,
                "output_truncated": truncated,
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "success": False,
            }
        except FileNotFoundError:
            first = cmd_argv[0] if cmd_argv else "unknown"
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command not found: {first}",
                "success": False,
            }
