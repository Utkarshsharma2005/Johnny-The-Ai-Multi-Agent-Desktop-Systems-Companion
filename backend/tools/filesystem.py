import os
from pathlib import Path
from typing import Dict, Any
from backend.tools.base import BaseTool
from backend.security.permissions import SecurityLevel
from backend.core.security import SecuritySandbox

class ReadFileTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="read_file",
            description="Reads file content securely within workspace boundaries.",
            security_level=SecurityLevel.LEVEL_0_SAFE_READ
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute or relative file path"}
            },
            "required": ["file_path"]
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        file_path = arguments["file_path"]
        valid, msg, path = SecuritySandbox.validate_file_path(file_path)
        if not valid:
            raise ValueError(msg)

        content = path.read_text(encoding="utf-8", errors="replace")
        return {"file_path": str(path), "content": content, "size_bytes": len(content)}

class ListDirTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="list_dir",
            description="Lists directory contents within workspace boundaries.",
            security_level=SecurityLevel.LEVEL_0_SAFE_READ
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dir_path": {"type": "string", "description": "Directory path to list"}
            },
            "required": ["dir_path"]
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        dir_path = arguments.get("dir_path", ".")
        valid, msg, target = SecuritySandbox.validate_directory_path(dir_path)
        if not valid:
            raise ValueError(msg)

        items = []
        try:
            for child in sorted(target.iterdir()):
                try:
                    items.append({
                        "name": child.name,
                        "is_dir": child.is_dir(),
                        "size_bytes": child.stat().st_size if child.is_file() else 0,
                    })
                except PermissionError:
                    # Skip unreadable children rather than crashing
                    items.append({"name": child.name, "is_dir": child.is_dir(), "error": "permission_denied"})
        except PermissionError as e:
            raise ValueError(f"Cannot list directory (permission denied): {target}") from e

        return {"dir_path": str(target), "total_items": len(items), "items": items}

class WriteFileTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="write_file",
            description="Creates or overwrites a source code file within workspace.",
            security_level=SecurityLevel.LEVEL_1_LOW_RISK_MOD
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Content string to write"}
            },
            "required": ["file_path", "content"]
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        file_path = arguments["file_path"]
        content = arguments["content"]

        # SECURITY: Restrict writes to within user home directory only
        # This prevents models from writing to /etc, /usr, /root, etc.
        _WRITE_ALLOWED_BASE = Path.home().expanduser().resolve()
        # Resolve symlinks first so a symlink pointing outside home cannot bypass
        # the boundary check (Path.resolve follows the whole symlink chain).
        raw_target = Path(file_path).expanduser()
        if raw_target.is_symlink():
            raise PermissionError(
                f"Write denied: '{raw_target}' is a symlink. Writing through symlinks is blocked."
            )
        target = raw_target.resolve()
        try:
            target.relative_to(_WRITE_ALLOWED_BASE)
        except ValueError:
            raise PermissionError(
                f"Write denied: target path '{target}' is outside the allowed write boundary '{_WRITE_ALLOWED_BASE}'. "
                "Writes are restricted to within user home directory."
            )

        # Reject writes to sensitive config/credential files (by name in ANY dir)
        _BLOCKED_WRITE_NAMES = {
            ".ssh", ".bashrc", ".profile", ".bash_profile", ".zshrc", ".zprofile",
            ".env", ".env.local", "id_rsa", "id_ed25519", "id_ecdsa",
            ".git-credentials", ".netrc", ".npmrc", ".zprofile",
        }
        if target.name.lower() in _BLOCKED_WRITE_NAMES or any(part.lower() in _BLOCKED_WRITE_NAMES for part in target.parts):
            raise PermissionError(f"Write denied: '{target.name}' is a protected configuration file.")
        if target.name.lower().endswith((".pem", ".key")):
            raise PermissionError(f"Write denied: private key/PEM files cannot be written ({target.name}).")

        # Enforce 1MB content size cap to prevent disk exhaustion
        _MAX_WRITE_BYTES = 1 * 1024 * 1024
        if len(content.encode("utf-8")) > _MAX_WRITE_BYTES:
            raise ValueError(f"Content too large: exceeds 1MB write limit ({len(content)} chars).")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        return {"file_path": str(target), "written_bytes": len(content.encode("utf-8"))}

class DeleteFileTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="delete_file",
            description="Deletes a file from the workspace (Level 2 Destructive).",
            security_level=SecurityLevel.LEVEL_2_POTENTIALLY_DESTRUCTIVE
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File path to delete"}
            },
            "required": ["file_path"]
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        file_path = arguments["file_path"]

        # Run through security sandbox FIRST (traversal + kernel region + symlink resolution)
        valid, msg, target = SecuritySandbox.validate_file_path(file_path)
        if not valid:
            raise ValueError(msg)

        # Extra: verify the REAL path (post-symlink-resolution) is within some safe boundary
        allowed_roots = [Path.home().expanduser().resolve()]
        if any(target.is_relative_to(root) for root in allowed_roots):
            pass
        else:
            raise PermissionError(
                f"Delete denied: '{target}' is outside the allowed boundary (home directory). "
                "Requires explicit Level 3 approval to override."
            )

        # Never delete root-level or protected credential files
        _BLOCKED_DELETE_NAMES = {
            ".ssh", ".bashrc", ".profile", ".bash_profile", ".zshrc",
            ".env", "id_rsa", "id_ed25519", ".git-credentials",
        }
        if target.name.lower() in _BLOCKED_DELETE_NAMES or len(target.parts) <= 1:
            raise PermissionError(f"Delete denied: '{target.name}' is a protected file.")

        if target.is_dir():
            raise ValueError(f"Use delete directory for directories: {target}")

        target.unlink()
        return {"file_path": str(target), "deleted": True}
