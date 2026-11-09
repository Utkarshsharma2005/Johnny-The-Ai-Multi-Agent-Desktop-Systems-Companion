
import os
import re
from pathlib import Path
from typing import Tuple, Optional, List

# ─── Blocked filesystem regions (Level 0 absolute denials) ───────────────────────
# These are never allowed regardless of permission level or user approval.
_BLOCKED_PATH_PREFIXES: List[str] = [
    "/proc",          # Linux kernel process/memory data
    "/sys",           # Linux kernel sysfs
    "/dev",           # Device files
    "/run/systemd",   # systemd private runtime
]

_BLOCKED_EXACT_PATHS: List[str] = [
    "/etc/shadow",
    "/etc/gshadow",
    "/etc/sudoers",
    "/etc/passwd",       # Readable, but should not be sent to LLMs
    "/etc/ssh/ssh_host_rsa_key",
    "/etc/ssl/private",
]

_TRAVERSAL_PATTERN = re.compile(r"(\.\./|%2e%2e|%252e%252e)", re.IGNORECASE)

# Sensitive credential/config files that must never be read OR written by tools
# (checked on file names in any directory, not just system paths).
_BLOCKED_SENSITIVE_NAMES = {
    ".env", ".env.local", ".ssh", ".bashrc", ".bash_profile", ".zshrc",
    ".profile", ".zprofile", ".git-credentials", ".netrc", ".npmrc",
    "id_rsa", "id_ed25519", "id_ecdsa", "credentials",
}


class SecuritySandbox:
    """
    4-Tier Path Security Inspector for all Johnny local file operations.
    Enforces:
    - Path traversal prevention (../ and encoded variants)
    - Kernel filesystem blocking (/proc, /sys, /dev)
    - Sensitive OS credential file blocking
    - Optional workspace boundary enforcement
    """

    @staticmethod
    def validate_file_path(
        file_path: str,
        allowed_base: Optional[str] = None,
    ) -> Tuple[bool, str, Path]:
        """
        Validates that a file path is safe to read (Level 0).
        
        Args:
            file_path: Raw path string from user or model.
            allowed_base: If set, restricts reads to this directory and below.
        """
        # 1. Reject empty / null paths
        if not file_path or not str(file_path).strip():
            return False, "File path cannot be empty.", Path(".")

        # 2. Detect traversal sequences BEFORE resolving (catches encoded attacks)
        if _TRAVERSAL_PATTERN.search(file_path):
            return False, "Path traversal attempt detected in file path.", Path(file_path)

        try:
            path = Path(file_path).expanduser().resolve()
        except Exception as e:
            return False, f"Invalid path syntax: {str(e)}", Path(file_path)

        # 3. Block kernel/sensitive filesystem regions
        path_str = str(path)
        for blocked_prefix in _BLOCKED_PATH_PREFIXES:
            if path_str.startswith(blocked_prefix):
                return False, f"Access denied: Path is in a blocked system region ({blocked_prefix}).", path

        for blocked_exact in _BLOCKED_EXACT_PATHS:
            if path_str == blocked_exact or path_str.startswith(blocked_exact + "/"):
                return False, f"Access denied: Path is a sensitive system file.", path

        # 3b. Block sensitive credential files by name in any location
        name_lower = path.name.lower()
        if name_lower in _BLOCKED_SENSITIVE_NAMES or any(part.lower() in _BLOCKED_SENSITIVE_NAMES for part in path.parts):
            return False, "Access denied: Path matches a protected credential/config file name.", path
        if name_lower.endswith(".pem") or name_lower.endswith(".key"):
            return False, "Access denied: Reading private key/PEM files is not permitted.", path

        # 4. Workspace boundary enforcement (optional)
        if allowed_base:
            base = Path(allowed_base).expanduser().resolve()
            try:
                path.relative_to(base)
            except ValueError:
                return False, f"Path is outside allowed workspace boundary: {base}", path

        # 5. Standard existence and permission checks
        if not path.exists():
            return False, f"File does not exist: {path}", path

        if not path.is_file():
            return False, f"Path is not a regular file: {path}", path

        if not os.access(path, os.R_OK):
            return False, f"Read permission denied for file: {path}", path

        return True, "Path validated successfully", path

    @staticmethod
    def validate_directory_path(
        dir_path: str,
        allowed_base: Optional[str] = None,
    ) -> Tuple[bool, str, Path]:
        """
        Validates that a directory path is safe to list (Level 0).
        Applies the same traversal and kernel-region checks as validate_file_path.
        """
        if not dir_path or not str(dir_path).strip():
            return False, "Directory path cannot be empty.", Path(".")

        if _TRAVERSAL_PATTERN.search(dir_path):
            return False, "Path traversal attempt detected in directory path.", Path(dir_path)

        try:
            path = Path(dir_path).expanduser().resolve()
        except Exception as e:
            return False, f"Invalid path syntax: {str(e)}", Path(dir_path)

        path_str = str(path)
        for blocked_prefix in _BLOCKED_PATH_PREFIXES:
            if path_str.startswith(blocked_prefix):
                return False, f"Access denied: Directory is in a blocked system region ({blocked_prefix}).", path

        if allowed_base:
            base = Path(allowed_base).expanduser().resolve()
            try:
                path.relative_to(base)
            except ValueError:
                return False, f"Directory is outside allowed workspace boundary: {base}", path

        if not path.exists():
            return False, f"Directory does not exist: {path}", path

        if not path.is_dir():
            return False, f"Path is not a directory: {path}", path

        return True, "Directory path validated successfully", path
