"""Tests for SSRF protection in backend.ingestion.ssrf and fetcher.

Covers:
  - _check_ip: IPv4 blocked ranges, IPv4 public, IPv4-mapped IPv6
  - _check_ip: IPv6 blocked ranges and public
  - validate_url_ssrf: IP-literal URLs (no DNS needed)
  - validate_url_ssrf: hostname resolution (socket.getaddrinfo mocked)
  - validate_url_ssrf: bad scheme
  - fetch_and_extract: redirect to private address is blocked
  - fetch_and_extract: CGNAT / link-local / documentation ranges
"""
from __future__ import annotations

import ipaddress
import socket
from unittest.mock import patch

import httpx
import pytest
import respx

from backend.ingestion.ssrf import (
    SSRFBlockedError,
    _check_ip,
    _resolve_and_check,
    validate_url_ssrf,
)
from backend.ingestion.fetcher import fetch_and_extract


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _v4(addr: str) -> ipaddress.IPv4Address:
    return ipaddress.IPv4Address(addr)


def _v6(addr: str) -> ipaddress.IPv6Address:
    return ipaddress.IPv6Address(addr)


def _mock_getaddrinfo(ip: str):
    """Return a patch that makes getaddrinfo resolve to *ip*."""
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return patch(
        "backend.ingestion.ssrf.socket.getaddrinfo",
        return_value=[(family, socket.SOCK_STREAM, 0, "", (ip, 80))],
    )


# ---------------------------------------------------------------------------
# _check_ip — IPv4 public addresses (must not raise)
# ---------------------------------------------------------------------------

class TestCheckIpPublicV4:
    def test_google_dns(self):
        _check_ip(_v4("8.8.8.8"))

    def test_cloudflare_dns(self):
        _check_ip(_v4("1.1.1.1"))

    def test_just_outside_172_31(self):
        # 172.32.0.1 is NOT in 172.16.0.0/12
        _check_ip(_v4("172.32.0.1"))

    def test_just_below_172_16(self):
        # 172.15.0.1 is NOT in 172.16.0.0/12
        _check_ip(_v4("172.15.0.1"))

    def test_198_17_public(self):
        # 198.17.x.x is NOT in benchmarking range 198.18.0.0/15
        _check_ip(_v4("198.17.255.255"))


# ---------------------------------------------------------------------------
# _check_ip — IPv4 blocked addresses (must raise)
# ---------------------------------------------------------------------------

class TestCheckIpBlockedV4:
    def test_loopback_127_0_0_1(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("127.0.0.1"))

    def test_loopback_127_255_255_255(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("127.255.255.255"))

    def test_rfc1918_10_x(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("10.0.0.1"))

    def test_rfc1918_10_255(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("10.255.255.255"))

    def test_rfc1918_192_168(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("192.168.1.1"))

    def test_rfc1918_172_16(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("172.16.0.1"))

    def test_rfc1918_172_31(self):
        # 172.31.x.x is inside 172.16.0.0/12
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("172.31.255.255"))

    def test_link_local_169_254(self):
        # Cloud metadata servers (AWS 169.254.169.254, GCP, Azure)
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("169.254.169.254"))

    def test_link_local_apipa(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("169.254.0.1"))

    def test_multicast(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("224.0.0.1"))

    def test_broadcast_240_range(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("240.0.0.1"))

    def test_cgnat_100_64(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("100.64.0.1"))

    def test_cgnat_100_127(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("100.127.255.255"))

    def test_unspecified_0_0_0_0(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v4("0.0.0.0"))


# ---------------------------------------------------------------------------
# _check_ip — IPv6 public addresses (must not raise)
# ---------------------------------------------------------------------------

class TestCheckIpPublicV6:
    def test_google_ipv6_dns(self):
        _check_ip(_v6("2001:4860:4860::8888"))

    def test_cloudflare_ipv6_dns(self):
        _check_ip(_v6("2606:4700:4700::1111"))


# ---------------------------------------------------------------------------
# _check_ip — IPv6 blocked addresses (must raise)
# ---------------------------------------------------------------------------

class TestCheckIpBlockedV6:
    def test_loopback(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("::1"))

    def test_link_local_fe80(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("fe80::1"))

    def test_link_local_febf(self):
        # fe80::/10 covers fe80:: through febf::
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("febf::1"))

    def test_unique_local_fc(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("fc00::1"))

    def test_unique_local_fd(self):
        # fd00::/8 is inside fc00::/7
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("fd12:3456:789a::1"))

    def test_multicast_ff(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("ff02::1"))

    def test_unspecified(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("::"))

    def test_ipv4_mapped_loopback(self):
        # ::ffff:127.0.0.1 must be caught via IPv4 unwrapping
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("::ffff:127.0.0.1"))

    def test_ipv4_mapped_private_192_168(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("::ffff:192.168.1.1"))

    def test_ipv4_mapped_private_10(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("::ffff:10.0.0.1"))

    def test_ipv4_mapped_link_local(self):
        with pytest.raises(SSRFBlockedError):
            _check_ip(_v6("::ffff:169.254.169.254"))


# ---------------------------------------------------------------------------
# validate_url_ssrf — scheme validation
# ---------------------------------------------------------------------------

class TestValidateScheme:
    @pytest.mark.asyncio
    async def test_ftp_rejected(self):
        with pytest.raises(ValueError, match="Only http"):
            await validate_url_ssrf("ftp://example.com/")

    @pytest.mark.asyncio
    async def test_file_rejected(self):
        with pytest.raises(ValueError, match="Only http"):
            await validate_url_ssrf("file:///etc/passwd")

    @pytest.mark.asyncio
    async def test_no_scheme_rejected(self):
        with pytest.raises(ValueError):
            await validate_url_ssrf("example.com/page")


# ---------------------------------------------------------------------------
# validate_url_ssrf — IP-literal URLs (no DNS mock needed)
# ---------------------------------------------------------------------------

class TestValidateIpLiteral:
    @pytest.mark.asyncio
    async def test_localhost_ip_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://127.0.0.1/")

    @pytest.mark.asyncio
    async def test_127_x_x_x_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://127.1.2.3/")

    @pytest.mark.asyncio
    async def test_10_x_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://10.0.0.1/")

    @pytest.mark.asyncio
    async def test_192_168_x_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://192.168.0.1/")

    @pytest.mark.asyncio
    async def test_172_16_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://172.16.0.1/")

    @pytest.mark.asyncio
    async def test_172_31_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://172.31.0.1/")

    @pytest.mark.asyncio
    async def test_172_15_allowed(self):
        # 172.15.x.x is outside 172.16.0.0/12 — IP literal, no DNS, must not raise.
        await validate_url_ssrf("http://172.15.0.1/")

    @pytest.mark.asyncio
    async def test_link_local_metadata_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://169.254.169.254/latest/meta-data/")

    @pytest.mark.asyncio
    async def test_ipv6_loopback_literal_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://[::1]/")

    @pytest.mark.asyncio
    async def test_ipv6_link_local_literal_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://[fe80::1]/")

    @pytest.mark.asyncio
    async def test_ipv6_unique_local_literal_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://[fd00::1]/")

    @pytest.mark.asyncio
    async def test_ipv4_mapped_ipv6_literal_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url_ssrf("http://[::ffff:192.168.1.1]/")


# ---------------------------------------------------------------------------
# validate_url_ssrf — hostname resolution (mocked getaddrinfo)
# ---------------------------------------------------------------------------

class TestValidateHostname:
    @pytest.mark.asyncio
    async def test_localhost_hostname_blocked(self):
        with _mock_getaddrinfo("127.0.0.1"):
            with pytest.raises(SSRFBlockedError):
                await validate_url_ssrf("http://localhost/")

    @pytest.mark.asyncio
    async def test_hostname_resolving_to_private_blocked(self):
        with _mock_getaddrinfo("10.0.0.1"):
            with pytest.raises(SSRFBlockedError):
                await validate_url_ssrf("http://internal.corp/")

    @pytest.mark.asyncio
    async def test_hostname_resolving_to_ipv6_loopback_blocked(self):
        with _mock_getaddrinfo("::1"):
            with pytest.raises(SSRFBlockedError):
                await validate_url_ssrf("http://myhost.local/")

    @pytest.mark.asyncio
    async def test_public_hostname_allowed(self):
        with _mock_getaddrinfo("93.184.216.34"):  # example.com
            await validate_url_ssrf("http://example.com/")  # must not raise

    @pytest.mark.asyncio
    async def test_unresolvable_hostname_blocked(self):
        with patch(
            "backend.ingestion.ssrf.socket.getaddrinfo",
            side_effect=socket.gaierror("Name or service not known"),
        ):
            with pytest.raises(SSRFBlockedError, match="could not be resolved"):
                await validate_url_ssrf("http://does-not-exist.invalid/")


# ---------------------------------------------------------------------------
# _resolve_and_check — edge cases
# ---------------------------------------------------------------------------

class TestResolveAndCheck:
    def test_private_ip_raises(self):
        with _mock_getaddrinfo("192.168.1.1"):
            with pytest.raises(SSRFBlockedError):
                _resolve_and_check("myhost.local", 80)

    def test_public_ip_passes(self):
        with _mock_getaddrinfo("8.8.8.8"):
            _resolve_and_check("dns.google", 80)  # must not raise


# ---------------------------------------------------------------------------
# fetch_and_extract — integration: redirect to private address is blocked
# ---------------------------------------------------------------------------

class TestFetchAndExtractSsrf:
    @pytest.mark.asyncio
    @respx.mock
    async def test_redirect_to_private_blocked(self):
        """A 3xx redirect that points to a private IP must be blocked."""
        respx.get("http://public.example.com/article").mock(
            return_value=httpx.Response(
                301,
                headers={"location": "http://192.168.1.1/steal"},
            )
        )
        with pytest.raises((SSRFBlockedError, ValueError)):
            await fetch_and_extract("http://public.example.com/article")

    @pytest.mark.asyncio
    @respx.mock
    async def test_redirect_to_loopback_blocked(self):
        respx.get("http://public.example.com/").mock(
            return_value=httpx.Response(
                302,
                headers={"location": "http://127.0.0.1/"},
            )
        )
        with pytest.raises((SSRFBlockedError, ValueError)):
            await fetch_and_extract("http://public.example.com/")

    @pytest.mark.asyncio
    async def test_direct_private_ip_blocked(self):
        with pytest.raises((SSRFBlockedError, ValueError)):
            await fetch_and_extract("http://192.168.1.1/")

    @pytest.mark.asyncio
    async def test_direct_localhost_blocked(self):
        with pytest.raises((SSRFBlockedError, ValueError)):
            await fetch_and_extract("http://127.0.0.1/")

    @pytest.mark.asyncio
    async def test_bad_scheme_blocked(self):
        with pytest.raises(ValueError, match="Only http"):
            await fetch_and_extract("ftp://example.com/")
