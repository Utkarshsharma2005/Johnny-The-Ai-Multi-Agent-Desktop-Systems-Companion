"""
NimProvider — NVIDIA NIM API integration.

Design principles (25yr system design perspective):
- Never swallow errors silently. Callers must know what went wrong.
- Retry only on transient failures (429 rate-limit, 503 unavailable).
- Keep the HTTP client per-request; httpx AsyncClient is not thread-safe to share across requests without a connection pool.
- Conversation history is first-class: every call accepts a messages list.
- Telemetry metadata (latency, token counts) returned alongside content.
"""

import asyncio
import base64
import json
import logging
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List, Optional

import httpx

from backend.models.base import ModelProvider
from backend.core.config import settings
from backend.core.cache import system_cache, make_cache_key
from backend.core import redaction

log = logging.getLogger(__name__)

# Retry configuration for transient NIM API errors
_RETRYABLE_STATUS_CODES = {429, 503, 504}
_MAX_RETRIES = 2
_RETRY_BACKOFF_S = [1.0, 3.0]  # wait before retry attempt 1, 2

# ── Shared pooled AsyncClient (connection reuse across all provider calls) ─────
_shared_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    """AsyncClient configured with standard timeouts for model generation."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.NIM_REQUEST_TIMEOUT, connect=settings.NIM_CONNECT_TIMEOUT)
    )


class NimProvider(ModelProvider):
    """
    NVIDIA NIM OpenAI-compatible API provider.
    Supports: Llama 3.3 70B, MiniMax M3 (vision), DeepSeek R1, Nemotron 340B.
    """

    # Johnny's core system identity — injected into every non-vision conversation
    SYSTEM_PROMPT = (
        "You are Johnny, an advanced desktop AI companion running on Linux. "
        "You are sharp, concise, and technically excellent. "
        "You can chat naturally, assist with code, analyze files, and reason across complex tasks. "
        "Never break character. Never mention being an LLM. Respond as Johnny."
    )

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        raw_key = api_key or settings.NIM_API_KEY
        if raw_key and raw_key.startswith("Bearer "):
            raw_key = raw_key[7:].strip()
        self.api_key = raw_key
        self.base_url = (base_url or settings.NIM_BASE_URL).rstrip("/")
        self._auth_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _get_auth_headers(self, model: str) -> Dict[str, str]:
        key = self.api_key
        m = (model or "").lower()
        if "glm" in m and os.getenv("glm-5.3-flash"):
            key = os.getenv("glm-5.3-flash", key)
        elif "minimax" in m and os.getenv("minimax-m3.1-flash"):
            key = os.getenv("minimax-m3.1-flash", key)
        elif "mistral" in m and os.getenv("mistral-large-4-1t-a52b"):
            key = os.getenv("mistral-large-4-1t-a52b", key)
        elif "deepseek" in m and os.getenv("deepseek-v4.1-flash") and os.getenv("deepseek-v4.1-flash") != "NIM_API_KEY":
            key = os.getenv("deepseek-v4.1-flash", key)
        elif "nemotron" in m and os.getenv("nemotron-3.5-super-vl-120b-a12b") and not os.getenv("nemotron-3.5-super-vl-120b-a12b", "").startswith("NVIDIA"):
            key = os.getenv("nemotron-3.5-super-vl-120b-a12b", key)

        if key and key.startswith("Bearer "):
            key = key[7:].strip()

        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _build_messages(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        include_system: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Build the OpenAI-format messages array from conversation history + current prompt.
        History entries are dicts with keys 'role' ('user'|'assistant') and 'content'.
        SECURITY: outgoing prompts/history are redacted so a user-pasted API key
        or token never reaches external model providers.
        """
        messages: List[Dict[str, str]] = []
        if include_system:
            messages.append({"role": "system", "content": self.SYSTEM_PROMPT})
        if history:
            messages.extend(
                {"role": h.get("role", "user"), "content": redaction.redact_text(h.get("content", ""))}
                for h in history
            )
        messages.append({"role": "user", "content": redaction.redact_text(prompt)})
        return messages

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        """
        POST with retry on transient NIM API errors (429, 503, 504).
        Raises httpx.HTTPStatusError on non-retryable failures.
        """
        attempt = 0
        while True:
            try:
                response = await client.post(url, json=payload, headers=headers, timeout=timeout)
                if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                    wait = _RETRY_BACKOFF_S[attempt]
                    log.warning(
                        "NIM API returned %s (attempt %d/%d), retrying in %.1fs",
                        response.status_code, attempt + 1, _MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                    attempt += 1
                    continue
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError:
                raise
            except httpx.TimeoutException as e:
                if attempt < _MAX_RETRIES:
                    wait = _RETRY_BACKOFF_S[attempt]
                    log.warning("NIM API timeout (attempt %d), retrying in %.1fs", attempt + 1, wait)
                    await asyncio.sleep(wait)
                    attempt += 1
                    continue
                raise RuntimeError(f"NIM API timed out after {_MAX_RETRIES + 1} attempts") from e

    # ─────────────────────────────────────────────────────────────────────────
    # Public ModelProvider interface
    # ─────────────────────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> str:
        """
        Single-turn or multi-turn text generation.
        Pass `history` as [{role, content}, ...] for conversational context.
        Raises on failure — callers decide how to handle errors.
        """
        model = model_id or settings.LLAMA_MODEL_ID
        cache_key = make_cache_key(f"nim:{model}", (prompt, history))
        cached = system_cache.get(cache_key)
        if cached is not None:
            log.info("NIM cache HIT | model=%s", model)
            return cached

        url = f"{self.base_url}/chat/completions"
        messages = self._build_messages(prompt, history=history)
        headers = self._get_auth_headers(model)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }

        t0 = time.perf_counter()
        async with _get_client() as client:
            response = await self._post_with_retry(client, url, payload, headers, timeout=settings.NIM_REQUEST_TIMEOUT)

        data = response.json()
        latency_ms = (time.perf_counter() - t0) * 1000
        msg = data["choices"][0]["message"]
        content = msg.get("content")
        if not content:
            content = msg.get("reasoning_content") or ""

        if content:
            system_cache.set(cache_key, content, ttl_s=300.0)

        log.info(
            "NIM generate OK | model=%s latency=%.0fms tokens_in=%s tokens_out=%s",
            model,
            latency_ms,
            data.get("usage", {}).get("prompt_tokens", "?"),
            data.get("usage", {}).get("completion_tokens", "?"),
        )
        return content

    async def stream(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming token generator with conversation history support.
        Yields raw token strings. Raises on connection/auth failures.
        """
        model = model_id or settings.LLAMA_MODEL_ID
        url = f"{self.base_url}/chat/completions"
        messages = self._build_messages(prompt, history=history)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "stream": True,
        }

        headers = {**self._get_auth_headers(model), "Accept": "text/event-stream"}

        t0 = time.perf_counter()
        token_count = 0

        try:
            async with _get_client() as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta_choice = chunk["choices"][0]["delta"]
                                rc = delta_choice.get("reasoning_content")
                                ct = delta_choice.get("content")
                                if rc:
                                    yield ("thought", rc)
                                if ct:
                                    token_count += 1
                                    yield ("token", ct)
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
        except Exception as e:
            # Automatic fallback to primary model if a specialized model fails or hits quota
            primary = settings.LLAMA_MODEL_ID
            if model != primary:
                log.warning("Model %s failed (%s). Falling back to primary %s", model, e, primary)
                payload["model"] = primary
                async with _get_client() as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as fallback_resp:
                        fallback_resp.raise_for_status()
                        async for line in fallback_resp.aiter_lines():
                            if not line:
                                continue
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    delta_choice = chunk["choices"][0]["delta"]
                                    rc = delta_choice.get("reasoning_content")
                                    ct = delta_choice.get("content")
                                    if rc:
                                        yield ("thought", rc)
                                    if ct:
                                        token_count += 1
                                        yield ("token", ct)
                                except (json.JSONDecodeError, KeyError, IndexError):
                                    continue
            else:
                raise

        log.info(
            "NIM stream OK | model=%s latency=%.0fms tokens_yielded=%d",
            model,
            (time.perf_counter() - t0) * 1000,
            token_count,
        )

    async def analyze_image(
        self,
        image_path: str,
        prompt: str,
        model_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Multimodal image analysis via MiniMax M3 (or any vision-capable NIM model).
        Encodes image as base64 data URL — works for local files without a CDN.
        Raises on failure.
        """
        model = model_id or settings.MINIMAX_MODEL_ID
        url = f"{self.base_url}/chat/completions"

        # Pre-flight size check: reject before base64 encoding to avoid OOM
        _MAX_VISION_BYTES = 10 * 1024 * 1024  # 10 MB
        try:
            file_size = Path(image_path).stat().st_size
            if file_size > _MAX_VISION_BYTES:
                raise ValueError(
                    f"Image file too large for vision API: {file_size / 1024 / 1024:.1f} MB "
                    f"(max {_MAX_VISION_BYTES // 1024 // 1024} MB)"
                )
        except OSError as e:
            raise ValueError(f"Cannot access image file: {e}") from e

        with open(image_path, "rb") as f:
            raw = f.read()
        encoded = base64.b64encode(raw).decode("utf-8")
        ext = image_path.lower().rsplit(".", 1)[-1]
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                    ],
                }
            ],
            "max_tokens": kwargs.get("max_tokens", 1024),
        }

        t0 = time.perf_counter()
        client = _get_client()
        response = await self._post_with_retry(client, url, payload, self._auth_headers, timeout=60.0)

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        latency_ms = (time.perf_counter() - t0) * 1000

        log.info("NIM vision OK | model=%s latency=%.0fms image=%s", model, latency_ms, image_path)
        return {
            "status": "success",
            "model_used": model,
            "image_path": image_path,
            "analysis_raw": content,
            "latency_ms": round(latency_ms, 2),
        }

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True
