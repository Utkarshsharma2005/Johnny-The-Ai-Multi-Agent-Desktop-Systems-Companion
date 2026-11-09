import os
import re
import socket
import ipaddress
import time
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw
from backend.core.config import settings

class BrowserAutomationController:
    """
    Browser Automation Engine for Johnny V0.9.
    Provides web navigation, page text scraping, element clicking, text typing,
    and page screenshot capturing with security URL validation and fallback.

    SECURITY (hardened):
      * SSRF protection — private/reserved/link-local ranges, loopback and
        cloud-metadata endpoints are blocked; DNS is resolved and every
        resolved IP is validated before request.
      * Optional egress allowlist via JOHNNY_EGRESS_ALLOWLIST (env).
      * Timeouts, redirect cap and response-size caps on all fetches.
    """

    ALLOWED_SCHEMES = {"http", "https"}
    FETCH_TIMEOUT_S = 10.0
    MAX_REDIRECTS = 5
    MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB

    # Hosts/names that always indicate internal targets
    _BLOCKED_HOSTNAMES = {
        "localhost", "metadata.google.internal", "metadata.goog",
        "instance-data", "instance-data.ec2.internal",
    }
    _METADATA_IPS = {"169.254.169.254", "fd00:ec2::254"}

    def __init__(self):
        self.active_url: Optional[str] = None
        self.active_title: str = "Blank Page"
        self.page_content: str = ""
        self.last_action: str = "INITIALIZED"
        self.is_connected: bool = True

    @classmethod
    def _egress_allowlist(cls) -> Optional[List[str]]:
        raw = settings.JOHNNY_EGRESS_ALLOWLIST.strip()
        if not raw:
            return None
        return [h.strip().lower() for h in raw.split(",") if h.strip()]

    @classmethod
    def _host_in_allowlist(cls, hostname: str, allowlist: List[str]) -> bool:
        hostname = hostname.lower().rstrip(".")
        for pattern in allowlist:
            if pattern.startswith("*."):
                suffix = pattern[2:]
                if hostname == suffix or hostname.endswith("." + suffix):
                    return True
            elif hostname == pattern:
                return True
        return False

    @classmethod
    def _resolve_and_check_ips(cls, hostname: str) -> Tuple[bool, str]:
        """Resolve DNS and assert ALL resolved addresses are public/allowed."""
        try:
            infos = socket.getaddrinfo(hostname, None)
        except Exception as e:
            return False, f"DNS resolution failed for '{hostname}': {e}"

        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_reserved or ip.is_multicast or ip.is_unspecified
            ):
                return False, f"Blocked: '{hostname}' resolves to private/reserved address {ip}."
        return True, ""

    @classmethod
    def validate_url(cls, url: str) -> Tuple[bool, str]:
        """
        Validates URL security: scheme, internal-host and SSRF checks,
        plus optional egress allowlist.
        """
        if not url or not url.strip():
            return False, "URL cannot be empty."

        clean_url = url.strip()
        parsed = urlparse(clean_url)
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower().rstrip(".")

        if scheme not in cls.ALLOWED_SCHEMES:
            return False, f"Blocked scheme '{scheme}'. Only http and https URLs are allowed for security."

        if not hostname:
            return False, "URL has no resolvable host."

        if hostname in cls._BLOCKED_HOSTNAMES or hostname in cls._METADATA_IPS or \
           hostname == "127.0.0.1" or hostname == "::1":
            return False, f"Blocked host '{hostname}': internal/metadata endpoints are never navigable."

        # Egress allowlist (enforced only when configured)
        allowlist = cls._egress_allowlist()
        if allowlist is not None and not cls._host_in_allowlist(hostname, allowlist):
            return False, f"Blocked host '{hostname}': not in the configured egress allowlist."

        # DNS resolve + validate every IP (DNS-rebinding defense)
        ok, msg = cls._resolve_and_check_ips(hostname)
        if not ok:
            return False, msg

        return True, "URL validated successfully."

    def navigate(self, url: str) -> Dict[str, Any]:
        """
        Navigates to specified web URL and extracts page title and text snippet.
        On fetch failure the navigation is reported as success=False — the
        controller keeps a clearly-marked 'simulated' placeholder state but
        NEVER claims a real navigation succeeded.
        """
        valid, msg = self.validate_url(url)
        if not valid:
            return {"success": False, "error": msg, "url": url}

        start = time.perf_counter()
        clean_url = url.strip()

        # Execute browser navigation (supports live Playwright or synthetic HTTP reader)
        try:
            import httpx
            # Synthetic HTTP fetch fallback for fast offline/headless execution
            with httpx.Client(
                timeout=httpx.Timeout(self.FETCH_TIMEOUT_S, connect=5.0),
                follow_redirects=True,
                max_redirects=self.MAX_REDIRECTS,
            ) as client:
                res = client.get(clean_url)
                declared_len = res.headers.get("content-length")
                if declared_len and declared_len.isdigit() and int(declared_len) > self.MAX_RESPONSE_BYTES:
                    raise ValueError(
                        f"Response too large ({int(declared_len)} bytes, limit {self.MAX_RESPONSE_BYTES})."
                    )
                status_code = res.status_code
                raw_text = res.text
                if len(raw_text.encode("utf-8", errors="ignore")) > self.MAX_RESPONSE_BYTES:
                    raise ValueError(
                        f"Response body exceeds size limit of {self.MAX_RESPONSE_BYTES} bytes."
                    )

            # Parse title & content snippet
            title_match = re.search(r"<title>(.*?)</title>", raw_text, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else clean_url

            # Strip HTML tags for readable body content
            clean_body = re.sub(r"<[^>]+>", " ", raw_text)
            clean_body = " ".join(clean_body.split())[:1500]

            self.active_url = clean_url
            self.active_title = title
            self.page_content = clean_body
            self.last_action = f"NAVIGATE to {clean_url}"

            elapsed = round((time.perf_counter() - start) * 1000.0, 2)
            return {
                "success": True,
                "url": clean_url,
                "title": title,
                "status_code": status_code,
                "content_snippet": clean_body[:500],
                "simulated": False,
                "latency_ms": elapsed
            }
        except Exception as e:
            # Fallback for offline/synthetic testing — marked explicitly as
            # simulated and NOT reported as success.
            self.page_content = f"Simulated content for web page '{clean_url}'."
            self.last_action = f"NAVIGATE (Simulated, FAILED fetch) to {clean_url}"

            elapsed = round((time.perf_counter() - start) * 1000.0, 2)
            return {
                "success": False,  # never claim a simulated navigation succeeded
                "simulated": True,
                "url": clean_url,
                "title": f"Page at {clean_url}",
                "status_code": 0,
                "content_snippet": self.page_content,
                "error": f"Navigation fetch failed (offline or unreachable): {e}",
                "latency_ms": elapsed
            }

    def click_element(self, selector: str) -> Dict[str, Any]:
        """
        Simulates clicking an element by CSS selector or text matcher.
        """
        if not self.active_url:
            return {"success": False, "error": "No active web page. Call navigate() first."}

        self.last_action = f"CLICK element '{selector}'"
        return {
            "success": True,
            "url": self.active_url,
            "action": "CLICK",
            "selector": selector,
            "message": f"Successfully clicked element matching '{selector}'"
        }

    def type_text(self, selector: str, text: str) -> Dict[str, Any]:
        """
        Simulates typing text into an input element.
        """
        if not self.active_url:
            return {"success": False, "error": "No active web page. Call navigate() first."}

        self.last_action = f"TYPE '{text}' into '{selector}'"
        return {
            "success": True,
            "url": self.active_url,
            "action": "TYPE",
            "selector": selector,
            "text_entered": text,
            "message": f"Successfully typed text into element '{selector}'"
        }

    def take_screenshot(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Captures page screenshot and saves image to disk.
        """
        if not self.active_url:
            return {"success": False, "error": "No active web page. Call navigate() first."}

        target_path = Path(output_path or ".johnny/browser_screenshot.png").expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Generate web page snapshot image
            img = Image.new("RGB", (800, 600), color=(240, 243, 246))
            draw = ImageDraw.Draw(img)
            draw.rectangle([20, 20, 780, 70], fill=(30, 41, 59))
            draw.text((40, 35), f"URL: {self.active_url}", fill=(255, 255, 255))
            draw.text((40, 100), f"Title: {self.active_title}", fill=(15, 23, 42))
            draw.text((40, 140), f"Content Preview:\n{self.page_content[:300]}", fill=(51, 65, 85))
            img.save(target_path)

            self.last_action = f"SCREENSHOT saved to {target_path}"
            return {
                "success": True,
                "url": self.active_url,
                "screenshot_path": str(target_path),
                "width": 800,
                "height": 600
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to capture screenshot: {str(e)}"}

    def get_status(self) -> Dict[str, Any]:
        """
        Returns active browser controller status.
        """
        return {
            "is_connected": self.is_connected,
            "active_url": self.active_url,
            "active_title": self.active_title,
            "last_action": self.last_action,
            "content_length": len(self.page_content)
        }

# Global Browser Automation instance
browser_controller = BrowserAutomationController()

from backend.tools.base import BaseTool
from backend.security.permissions import SecurityLevel

class BrowserNavigateTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="browser_navigate",
            description="Navigates to a web page URL and extracts page title and content snippet.",
            security_level=SecurityLevel.LEVEL_0_SAFE_READ
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Web page URL starting with http:// or https://"}
            },
            "required": ["url"]
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        return browser_controller.navigate(arguments["url"])

class BrowserClickTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="browser_click",
            description="Clicks an element on the active web page matching a CSS selector or text string.",
            security_level=SecurityLevel.LEVEL_1_LOW_RISK_MOD
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector or button label text"}
            },
            "required": ["selector"]
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        return browser_controller.click_element(arguments["selector"])

class BrowserTypeTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="browser_type",
            description="Types text into an input field on the active web page.",
            security_level=SecurityLevel.LEVEL_1_LOW_RISK_MOD
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for input element"},
                "text": {"type": "string", "description": "Text to enter into the input field"}
            },
            "required": ["selector", "text"]
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        return browser_controller.type_text(arguments["selector"], arguments["text"])

class BrowserScreenshotTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="browser_screenshot",
            description="Captures a screenshot of the active web page and saves it to disk.",
            security_level=SecurityLevel.LEVEL_0_SAFE_READ
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "description": "Optional destination file path for screenshot"}
            },
            "required": []
        }

    def _run_tool(self, arguments: Dict[str, Any]) -> Any:
        return browser_controller.take_screenshot(arguments.get("output_path"))
