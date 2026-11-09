"""
redaction.py — Secret/PII redaction helper for Johnny.

Used before logging, broadcasting agent-bus events, or persisting task
checkpoints so API keys, tokens and other sensitive material never leak.

Keep this pure and dependency-free (regex only) — it runs on hot paths.
"""

import re
import json
from typing import Any, Dict, List

# nvapi-*, OpenRouter sk-or-v1-*, generic OpenAI sk-*,hf_*, ghp_* tokens
_API_KEY_PATTERNS: List[re.Pattern] = [
    re.compile(r"nvapi-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"sk-or-v\d+-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\b(?:hf|ghp|gho|github_pat)_[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"(?i)\b(JOHN(?:NY)?_API_TOKEN|API_KEY|SECRET|PASSWORD|PASSWD)\s*[=:]\s*\S{6,}"),
]
_BEARER_PATTERNS = [
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{6,}"),
    re.compile(r"(?i)\bauthorization\s*[=:]?\s*[^\s\"']{6,}"),
]
_PEM_PATTERN = re.compile(r"-----[A-Z ]*(?:PRIVATE)?[A-Z ]*KEY-----[\s\S]*?-----[A-Z ]*KEY-----")
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}\b")
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

_API_KEY_SUB = "[REDACTED_KEY]"
_BEARER_SUB = "[REDACTED_AUTH]"
_PEM_SUB = "[REDACTED_PEM_BLOCK]"
_JWT_SUB = "[REDACTED_JWT]"


def redact_text(text: str, redact_emails: bool = False) -> str:
    """Redact secrets from a text string. Emails only when explicitly asked
    (chat text legitimately contains emails)."""
    if not isinstance(text, str) or not text:
        return text
    out = text
    for pat in _API_KEY_PATTERNS:
        out = pat.sub(_API_KEY_SUB, out)
    for pat in _BEARER_PATTERNS:
        out = pat.sub(_BEARER_SUB, out)
    out = _PEM_PATTERN.sub(_PEM_SUB, out)
    out = _JWT_PATTERN.sub(_JWT_SUB, out)
    if redact_emails:
        out = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", out)
    return out


def redact_json(obj: Any, _depth: int = 0) -> Any:
    """Recursively redact strings inside dicts/lists (depth-capped)."""
    if _depth > 8 or isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {str(k): redact_json(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_json(v, _depth + 1) for v in obj]
    return obj


def contains_secret(text: str) -> bool:
    """True when text appears to contain credential-like material."""
    if not isinstance(text, str) or not text:
        return False
    for pat in _API_KEY_PATTERNS + _BEARER_PATTERNS + [_PEM_PATTERN, _JWT_PATTERN]:
        if pat.search(text):
            return True
    return False


__all__ = ["redact_text", "redact_json", "contains_secret"]
