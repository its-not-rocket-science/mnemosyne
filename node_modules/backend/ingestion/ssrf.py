"""SSRF guard for server-side URL fetching.

Every outbound URL (initial request and each redirect) is validated before
the TCP connection is opened.  Validation has two stages:

1.  IP-literal hosts are parsed directly with :mod:`ipaddress` and checked
    against the blocked-range tables.

2.  Hostname hosts are resolved via :func:`socket.getaddrinfo` (in a thread
    so the event loop is not blocked).  Every returned address is checked;
    if *any* resolves to a blocked range the URL is rejected.

IPv4-mapped IPv6 addresses (``::ffff:192.168.x.x``) are unwrapped and the
embedded IPv4 address is checked, so the mapping cannot be used as a bypass.

Known limitation
----------------
This guard does not prevent DNS-rebinding attacks.  A malicious DNS server
could return a public address for the pre-flight check and then return a
private address when the OS opens the actual connection.  Full protection
requires replacing the hostname with the resolved IP in the outbound request
(changing the ``Host`` header accordingly), which breaks many CDN-hosted
sites.  For the threat model here (blocking accidental or naïve SSRF),
resolve-and-check is sufficient.  Deploy behind an egress firewall for
defence-in-depth against sophisticated rebinding.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Blocked address ranges
# ---------------------------------------------------------------------------

_BLOCKED_V4: list[ipaddress.IPv4Network] = [
    ipaddress.IPv4Network("0.0.0.0/8"),        # "this" network / unspecified
    ipaddress.IPv4Network("10.0.0.0/8"),        # RFC 1918 private
    ipaddress.IPv4Network("100.64.0.0/10"),     # CGNAT shared space (RFC 6598)
    ipaddress.IPv4Network("127.0.0.0/8"),       # loopback
    ipaddress.IPv4Network("169.254.0.0/16"),    # link-local (APIPA / cloud metadata)
    ipaddress.IPv4Network("172.16.0.0/12"),     # RFC 1918 private (172.16–172.31)
    ipaddress.IPv4Network("192.0.0.0/24"),      # IETF protocol assignments
    ipaddress.IPv4Network("192.168.0.0/16"),    # RFC 1918 private
    ipaddress.IPv4Network("198.18.0.0/15"),     # benchmarking (RFC 2544)
    ipaddress.IPv4Network("198.51.100.0/24"),   # documentation TEST-NET-2
    ipaddress.IPv4Network("203.0.113.0/24"),    # documentation TEST-NET-3
    ipaddress.IPv4Network("224.0.0.0/4"),       # multicast
    ipaddress.IPv4Network("240.0.0.0/4"),       # reserved / broadcast
]

_BLOCKED_V6: list[ipaddress.IPv6Network] = [
    ipaddress.IPv6Network("::/128"),            # unspecified
    ipaddress.IPv6Network("::1/128"),           # loopback
    ipaddress.IPv6Network("::ffff:0:0/96"),     # IPv4-mapped (also unwrapped below)
    ipaddress.IPv6Network("64:ff9b::/96"),      # IPv4/IPv6 translation (RFC 6052)
    ipaddress.IPv6Network("100::/64"),          # discard prefix (RFC 6666)
    ipaddress.IPv6Network("fc00::/7"),          # unique-local (ULA: fc00:: and fd00::)
    ipaddress.IPv6Network("fe80::/10"),         # link-local
    ipaddress.IPv6Network("ff00::/8"),          # multicast
    ipaddress.IPv6Network("2001::/32"),         # Teredo tunneling (RFC 4380)
    ipaddress.IPv6Network("2001:db8::/32"),     # documentation (RFC 3849)
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class SSRFBlockedError(ValueError):
    """Raised when a URL resolves to a blocked private or reserved address."""


def _check_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Raise :exc:`SSRFBlockedError` if *addr* is in a blocked network.

    IPv4-mapped IPv6 addresses are unwrapped so that ``::ffff:192.168.1.1``
    is caught by the IPv4 table rather than relying solely on the
    ``::ffff:0:0/96`` entry.
    """
    if isinstance(addr, ipaddress.IPv6Address):
        mapped = addr.ipv4_mapped
        if mapped is not None:
            _check_ip(mapped)
            return
        if any(addr in net for net in _BLOCKED_V6):
            raise SSRFBlockedError(
                f"Requests to the address {addr} are not permitted "
                "(address is in a restricted range)."
            )
    else:
        if any(addr in net for net in _BLOCKED_V4):
            raise SSRFBlockedError(
                f"Requests to the address {addr} are not permitted "
                "(address is in a restricted range)."
            )


def _resolve_and_check(host: str, port: int) -> None:
    """Resolve *host* via :func:`socket.getaddrinfo` and check every result.

    Designed to be called via :func:`asyncio.to_thread`; does not touch the
    event loop.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SSRFBlockedError(
            f"The hostname {host!r} could not be resolved: {exc}"
        ) from exc

    if not infos:
        raise SSRFBlockedError(
            f"The hostname {host!r} did not resolve to any address."
        )

    for _family, _type, _proto, _canonname, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            continue  # malformed entry from getaddrinfo — skip
        try:
            _check_ip(addr)
        except SSRFBlockedError:
            raise SSRFBlockedError(
                f"Requests to {host!r} are not permitted "
                "(hostname resolves to a restricted address)."
            )


async def validate_url_ssrf(url: str) -> None:
    """Validate *url* is safe to fetch; raise on SSRF targets.

    Checks scheme, then either validates an IP-literal host directly or
    resolves the hostname and checks every DNS result.

    Args:
        url: The absolute URL to validate.

    Raises:
        ValueError: Non-http/https scheme, missing host, or malformed URL.
        SSRFBlockedError: The URL resolves to a blocked private/reserved address.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(
            f"Only http and https URLs are supported (got scheme {scheme!r})."
        )

    host = parsed.hostname  # strips [ ] from IPv6 literals; None if absent
    if not host:
        raise ValueError("URL has no host component.")

    port = parsed.port or (443 if scheme == "https" else 80)

    # IP-literal host: validate directly without a DNS round-trip.
    try:
        addr = ipaddress.ip_address(host)
        _check_ip(addr)
        return
    except SSRFBlockedError:
        raise
    except ValueError:
        pass  # not an IP literal — continue to DNS resolution

    # Hostname: resolve in a thread and check every returned address.
    await asyncio.to_thread(_resolve_and_check, host, port)
