import re
from enum import Enum
from typing import Dict, Any, Tuple, List, Set

class SecurityLevel(int, Enum):
    LEVEL_0_SAFE_READ = 0            # Automated safe reads (read file, list dir, git status, docker ps)
    LEVEL_1_LOW_RISK_MOD = 1         # Automated low-risk mods (write file, run tests, compile)
    LEVEL_2_POTENTIALLY_DESTRUCTIVE = 2  # Requires user confirmation (delete file, git reset --hard, docker prune)
    LEVEL_3_DANGEROUS_SYSTEM = 3     # Always explicit confirmation (sudo, disk format, firewall)

class PermissionManager:
    """
    V0.4 Tool Security Permission Engine.
    Enforces strict 4-tier security sandboxing on all model tool call requests.
    """

    FORBIDDEN_COMMAND_PATTERNS: List[re.Pattern] = [
        re.compile(r"rm\s+-[rRfF]+\s+(/|\*|/\*|\.\.)"), # Root / wild deletion
        re.compile(r"rm\s+-[rRfF]+\s+~/?\s*$"),         # Home deletion
        re.compile(r"mkfs"),                            # Disk formatting
        re.compile(r"dd\s+if="),                        # Direct disk write
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;"), # Fork bomb
        re.compile(r"shutdown|reboot|init\s+0"),        # System shutdown
        re.compile(r"chmod\s+-R\s+777\s+/"),           # Unrestricted root permissions
        # ── Obfuscation / pipe-to-shell / interpreter eval escapes ─────────────
        re.compile(r"curl[^|]*\|\s*(sh|bash|zsh|python|perl)\b", re.IGNORECASE),
        re.compile(r"wget[^|]*\|\s*(sh|bash|zsh|python|perl)\b", re.IGNORECASE),
        re.compile(r"\|\s*(sudo\s+)?(sh|bash|zsh)\b"),  # any pipe into a shell
        re.compile(r"\bbase64\s+(-d|--decode)\b", re.IGNORECASE),  # decode-then-run obfuscation
        re.compile(r"(?s)\beval\b.*\b(decoderaw|env|base64)\b"),   # eval obfuscation
        re.compile(r"\bnc\b|\bncat\b|\bnetcat\b"),       # reverse shells / listeners
        re.compile(r">\s*/dev/(sd[a-z]|nvme|disk|vda)"), # raw device write
        re.compile(r"\b(gdb|ptrace)\b.*\battach\b"),     # process memory injection
    ]

    STRICT_SUDO_PATTERN = re.compile(r"\bsudo\b")

    # Allowlist of safe command first-tokens. Commands NOT in this list require
    # user approval even at lower security levels (defense-in-depth).
    SAFE_COMMAND_ALLOWLIST: Set[str] = {
        "ls", "cat", "head", "tail", "wc", "grep", "find", "echo", "printf",
        "pwd", "date", "whoami", "uname", "which", "file", "stat", "du",
        "touch", "mkdir", "cp", "mv", "pytest", "python", "python3", "pip",
        "node", "npm", "npx", "cargo", "rustc", "git", "docker", "make",
        "sort", "uniq", "diff", "sed", "printenv", "cut", "tr",
        # NOTE: curl/wget/awk are deliberately NOT allowlisted — network
        # fetchers and interpreters require explicit user approval.
    }

    @classmethod
    def validate_tool_call(
        cls,
        tool_name: str,
        arguments: Dict[str, Any],
        required_level: SecurityLevel,
        user_approved: bool = False
    ) -> Tuple[bool, str]:
        """
        Validates security permissions for a requested tool call.
        Returns (granted: bool, reason: str).
        """
        # 1. Check raw command arguments against forbidden system destruction patterns FIRST
        command_str = str(arguments.get("command") or arguments.get("cmd") or "")
        if command_str:
            for pattern in cls.FORBIDDEN_COMMAND_PATTERNS:
                if pattern.search(command_str):
                    return False, f"Permission DENIED: Command contains forbidden high-risk system pattern '{pattern.pattern}'."

            if cls.STRICT_SUDO_PATTERN.search(command_str) and required_level < SecurityLevel.LEVEL_3_DANGEROUS_SYSTEM:
                if not user_approved:
                    return False, "Permission DENIED: Sudo execution requires explicit LEVEL 3 user approval."

            # Allowlist gate: unknown commands need explicit user approval
            first_token = cls._first_token(command_str)
            if first_token and first_token not in cls.SAFE_COMMAND_ALLOWLIST and not user_approved:
                return False, (
                    f"Permission DENIED: Command '{first_token}' is not in the safe allowlist. "
                    "Explicit user approval is required for unlisted commands."
                )

        # 2. Check Level 2 & 3 required user approval
        if required_level >= SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE and not user_approved:
            level_name = "LEVEL 2 (Destructive)" if required_level == SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE else "LEVEL 3 (Dangerous)"
            return False, f"Permission DENIED: Tool '{tool_name}' requires {level_name} user confirmation before execution."

        return True, f"Permission GRANTED for tool '{tool_name}' (Level {required_level.value})"

    @staticmethod
    def _first_token(command: str) -> str:
        """Best-effort first-token extraction (handles 'VAR=x cmd ...')."""
        tokens = command.strip().split()
        idx = 0
        while idx < len(tokens) and "=" in tokens[idx] and not tokens[idx].startswith("-"):
            idx += 1
        if idx < len(tokens):
            tok = tokens[idx]
            return tok.split("/")[-1]  # normalize /usr/bin/git -> git
        return ""

    @classmethod
    def classify_command_level(cls, command: str) -> SecurityLevel:
        """
        Classifies a terminal command string into its security level.
        """
        cmd_lower = command.lower().strip()

        if cls.STRICT_SUDO_PATTERN.search(cmd_lower) or any(kw in cmd_lower for kw in ["mkfs", "fdisk", "iptables", "ufw"]):
            return SecurityLevel.LEVEL_3_DANGEROUS_SYSTEM

        if any(kw in cmd_lower for kw in ["rm -rf", "git reset --hard", "git push --force", "docker system prune", "docker rm"]):
            return SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE

        if any(kw in cmd_lower for kw in ["pytest", "npm test", "npm run build", "touch", "mkdir", "git commit", "git checkout"]):
            return SecurityLevel.LEVEL_1_LOW_RISK_MOD

        return SecurityLevel.LEVEL_0_SAFE_READ
