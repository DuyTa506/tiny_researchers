"""Network security utilities — SSRF protection."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Private/loopback ranges that must be blocked (SSRF protection)
_BLOCKED_RANGES = [
    ipaddress.ip_network(r)
    for r in [
        "127.0.0.0/8",      # Loopback
        "10.0.0.0/8",       # Private class A
        "172.16.0.0/12",    # Private class B
        "192.168.0.0/16",   # Private class C
        "169.254.0.0/16",   # Link-local
        "::1/128",          # IPv6 loopback
        "fc00::/7",         # IPv6 unique local
        "fe80::/10",        # IPv6 link-local
    ]
]


def validate_url_target(url: str) -> tuple[bool, str]:
    """
    Check that *url* does not resolve to a private/loopback address.

    Returns:
        (True, "") if URL is safe.
        (False, reason) if URL is blocked.

    Raises:
        ValueError: If hostname cannot be resolved or URL is otherwise invalid.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError(f"Invalid URL (no hostname): {url!r}")

    try:
        resolved = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(resolved)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve hostname {hostname!r}: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"Invalid IP address resolved for {hostname!r}: {exc}") from exc

    for blocked in _BLOCKED_RANGES:
        if ip in blocked:
            return False, f"Blocked private/loopback address: {ip} (range {blocked})"

    return True, ""
