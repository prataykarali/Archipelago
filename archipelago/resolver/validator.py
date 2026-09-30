"""HTTP URL Validator with SSRF Protection, HEAD, and streaming GET fallback."""
from __future__ import annotations

import datetime
import ipaddress
import logging
import re
from typing import Any
from urllib.parse import urlparse
import requests

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

logger = logging.getLogger("archipelago.resolver.validator")

# SSRF Protection: Private & Reserved IP ranges and metadata endpoints
FORBIDDEN_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "169.254.169.254",
    "metadata.google.internal",
    "169.254.169.254.xip.io",
}


def is_safe_url(url: str) -> tuple[bool, str | None]:
    """Check if a URL is safe against SSRF attacks."""
    if not url or not isinstance(url, str):
        return False, "Empty URL"

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Forbidden scheme: {parsed.scheme}"

    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        return False, "Missing hostname"

    if hostname in FORBIDDEN_HOSTS or hostname.endswith(".internal") or hostname.endswith(".local"):
        return False, f"Forbidden internal hostname: {hostname}"

    # Try resolving hostname to IP address to check private ranges
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False, f"Forbidden private IP address: {ip}"
    except ValueError:
        # Not a raw IP literal; domain name check passed
        pass

    return True, None


def check_url_sync(url: str, timeout: float = 8.0) -> dict[str, Any]:
    """Validate a URL synchronously using HEAD with GET stream fallback."""
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    is_safe, error_msg = is_safe_url(url)
    if not is_safe:
        return {
            "url": url,
            "status": 403,
            "final_url": url,
            "working": False,
            "error": f"SSRF Protection: {error_msg}",
            "checked_at": now_str,
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (Archipelago Library Resolver/1.0; +https://archipelago.invalid)"
    }
    
    # 1. Try HEAD request first
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout, headers=headers)
        if resp.status_code < 400:
            return {
                "url": url,
                "status": resp.status_code,
                "final_url": str(resp.url),
                "working": True,
                "redirected": str(resp.url).rstrip("/") != url.rstrip("/"),
                "error": None,
                "checked_at": now_str,
            }
    except Exception as exc:
        logger.debug("HEAD request failed for %s: %s", url, exc)

    # 2. Streaming GET fallback (for publishers/CDNs that reject HEAD)
    try:
        resp = requests.get(url, allow_redirects=True, stream=True, timeout=timeout, headers=headers)
        status_code = resp.status_code
        final_url = str(resp.url)
        try:
            next(resp.iter_content(chunk_size=512), None)
        except Exception:
            pass
        finally:
            resp.close()

        return {
            "url": url,
            "status": status_code,
            "final_url": final_url,
            "working": status_code < 400,
            "redirected": final_url.rstrip("/") != url.rstrip("/"),
            "error": None if status_code < 400 else f"HTTP Status {status_code}",
            "checked_at": now_str,
        }
    except Exception as exc:
        return {
            "url": url,
            "status": 0,
            "final_url": url,
            "working": False,
            "error": str(exc),
            "checked_at": now_str,
        }


async def check_url_async(url: str, timeout: float = 8.0) -> dict[str, Any]:
    """Validate a URL asynchronously using httpx."""
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    is_safe, error_msg = is_safe_url(url)
    if not is_safe:
        return {
            "url": url,
            "status": 403,
            "final_url": url,
            "working": False,
            "error": f"SSRF Protection: {error_msg}",
            "checked_at": now_str,
        }

    if _HAS_HTTPX:
        headers = {
            "User-Agent": "Mozilla/5.0 (Archipelago Library Resolver/1.0; +https://archipelago.invalid)"
        }
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
                try:
                    resp = await client.head(url)
                    if resp.status_code < 400:
                        return {
                            "url": url,
                            "status": resp.status_code,
                            "final_url": str(resp.url),
                            "working": True,
                            "redirected": str(resp.url).rstrip("/") != url.rstrip("/"),
                            "error": None,
                            "checked_at": now_str,
                        }
                except Exception:
                    pass

                # Streaming GET fallback
                async with client.stream("GET", url) as resp:
                    return {
                        "url": url,
                        "status": resp.status_code,
                        "final_url": str(resp.url),
                        "working": resp.status_code < 400,
                        "redirected": str(resp.url).rstrip("/") != url.rstrip("/"),
                        "error": None if resp.status_code < 400 else f"HTTP Status {resp.status_code}",
                        "checked_at": now_str,
                    }
        except Exception as exc:
            return {
                "url": url,
                "status": 0,
                "final_url": url,
                "working": False,
                "error": str(exc),
                "checked_at": now_str,
            }

    return check_url_sync(url, timeout=timeout)
