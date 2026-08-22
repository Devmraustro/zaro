"""SSRF guard for outbound HTTP requests.

Phase 1.4 establishes the policy layer that every future outbound call
(webhooks, avatar fetches, importers) must pass through. The guard rejects:

- non-http(s) schemes (file://, gopher://, ftp://, ...)
- credentials embedded in URLs
- hostnames resolving to private, loopback, link-local or reserved networks
  (DNS is resolved and *all* returned addresses are checked, closing the
  DNS-rebinding window at request time)

Usage::

    guard = UrlGuard(allowed_hosts={"api.partner.com"})
    await guard.validate("https://api.partner.com/v1/resource")

The actual fetching stays with the caller; this module only answers
"may we talk to this URL?".
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.core.exceptions import BadRequestError


class DisallowedUrlError(BadRequestError):
    code = "disallowed_url"


@dataclass(frozen=True)
class UrlGuard:
    """Immutable outbound-URL policy."""

    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    allowed_ports: frozenset[int] = field(default_factory=lambda: frozenset({80, 443}))
    allow_private_networks: bool = False
    resolve_dns: bool = True

    def validate(self, url: str) -> None:
        """Raise :class:`DisallowedUrlError` when ``url`` violates policy."""
        try:
            parsed = urlparse(url)
        except ValueError as exc:
            raise DisallowedUrlError("Malformed URL") from exc

        if parsed.scheme not in ("http", "https"):
            raise DisallowedUrlError("Only http(s) URLs are allowed")
        if not parsed.hostname:
            raise DisallowedUrlError("URL has no hostname")
        if parsed.username or parsed.password:
            raise DisallowedUrlError("Credentials in URLs are not allowed")

        try:
            port = parsed.port
        except ValueError as exc:
            raise DisallowedUrlError("Invalid URL port") from exc
        effective_port = port if port is not None else (443 if parsed.scheme == "https" else 80)
        if self.allowed_ports and effective_port not in self.allowed_ports:
            raise DisallowedUrlError(f"Port {effective_port} is not allowed")

        hostname = parsed.hostname.lower()
        if self.allowed_hosts and hostname not in {h.lower() for h in self.allowed_hosts}:
            raise DisallowedUrlError("Host is not on the allow-list")

        if not self.allow_private_networks:
            self._reject_private(hostname)

    def _reject_private(self, hostname: str) -> None:
        literal = _as_ip_address(hostname)
        candidates: list[ipaddress.IPv4Address | ipaddress.IPv6Address]
        if literal is not None:
            candidates = [literal]
        elif self.resolve_dns:
            try:
                infos = socket.getaddrinfo(hostname, None)
            except socket.gaierror as exc:
                raise DisallowedUrlError("Hostname could not be resolved") from exc
            candidates = []
            for info in infos:
                addr = _as_ip_address(str(info[4][0]))
                if addr is not None:
                    candidates.append(addr)
        else:
            return

        for address in candidates:
            if _is_blocked(address):
                raise DisallowedUrlError("URL resolves to a private or reserved network")


def _as_ip_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        # ::ffff:127.0.0.1 must be judged by its IPv4 semantics.
        return address.ipv4_mapped
    return address


def _is_blocked(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or address in ipaddress.ip_network("100.64.0.0/10")  # carrier-grade NAT
    )
