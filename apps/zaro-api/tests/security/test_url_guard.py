import socket

import pytest

from app.core.url_guard import DisallowedUrlError, UrlGuard

pytestmark = pytest.mark.asyncio


@pytest.fixture
def guard() -> UrlGuard:
    # DNS resolution disabled for pure policy tests; resolution behaviour has
    # its own tests with monkeypatched getaddrinfo.
    return UrlGuard(resolve_dns=False)


class TestSchemePolicy:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "data:text/html,hello",
            "javascript:alert(1)",
        ],
    )
    async def test_non_http_schemes_rejected(self, guard: UrlGuard, url: str):
        with pytest.raises(DisallowedUrlError):
            await _validate(guard, url)

    async def test_https_accepted(self, guard: UrlGuard):
        await _validate(guard, "https://api.partner.com/v1/resource")


class TestCredentialPolicy:
    @pytest.mark.parametrize(
        "url",
        [
            "https://user:password@api.partner.com/",
            "https://user@api.partner.com/",
            "http://admin:hunter2@internal.example.com/",
        ],
    )
    async def test_embedded_credentials_rejected(self, guard: UrlGuard, url: str):
        with pytest.raises(DisallowedUrlError):
            await _validate(guard, url)


class TestPortPolicy:
    async def test_uncommon_port_rejected(self, guard: UrlGuard):
        with pytest.raises(DisallowedUrlError):
            await _validate(guard, "https://api.partner.com:8443/")

    async def test_standard_ports_allowed(self, guard: UrlGuard):
        await _validate(guard, "https://api.partner.com/")
        await _validate(guard, "http://api.partner.com/")

    async def test_invalid_port_rejected(self, guard: UrlGuard):
        with pytest.raises(DisallowedUrlError):
            await _validate(guard, "https://api.partner.com:99999/")


class TestHostAllowlist:
    async def test_host_not_on_allowlist_rejected(self):
        guard = UrlGuard(allowed_hosts=frozenset({"api.partner.com"}))
        with pytest.raises(DisallowedUrlError):
            await _validate(guard, "https://evil.example.com/")

    async def test_allowlisted_host_accepted(self):
        guard = UrlGuard(allowed_hosts=frozenset({"api.partner.com"}), resolve_dns=False)
        await _validate(guard, "https://API.Partner.com/v1")  # case-insensitive


class TestPrivateNetworkBlocking:
    @pytest.fixture
    def resolving_guard(self) -> UrlGuard:
        return UrlGuard(resolve_dns=True)

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://10.0.0.5/",
            "http://172.16.0.9/",
            "http://192.168.1.1/",
            "http://169.254.169.254/latest/meta-data/",  # cloud metadata
            "http://[::1]/",
            "http://[fe80::1]/",
            "http://0.0.0.0/",
            "http://100.64.0.1/",  # carrier-grade NAT
        ],
    )
    async def test_private_and_reserved_literals_rejected(self, guard: UrlGuard, url: str):
        with pytest.raises(DisallowedUrlError):
            await _validate(guard, url)

    async def test_ipv4_mapped_loopback_rejected(self, guard: UrlGuard):
        with pytest.raises(DisallowedUrlError):
            await _validate(guard, "http://[::ffff:127.0.0.1]/")

    async def test_hostname_resolving_to_private_ip_rejected(self, resolving_guard: UrlGuard, monkeypatch):
        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.0.10", 0))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        with pytest.raises(DisallowedUrlError):
            await _validate(resolving_guard, "https://rebind.attacker.example/")

    async def test_hostname_resolving_to_public_ip_accepted(self, resolving_guard: UrlGuard, monkeypatch):
        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        await _validate(resolving_guard, "https://api.partner.com/")

    async def test_all_resolved_addresses_must_be_safe(self, resolving_guard: UrlGuard, monkeypatch):
        def fake_getaddrinfo(host, port, *args, **kwargs):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0)),
            ]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        with pytest.raises(DisallowedUrlError):
            await _validate(resolving_guard, "https://mixed.example.com/")

    async def test_unresolvable_hostname_rejected(self, resolving_guard: UrlGuard, monkeypatch):
        def fake_getaddrinfo(host, port, *args, **kwargs):
            raise socket.gaierror("resolution failed")

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
        with pytest.raises(DisallowedUrlError):
            await _validate(resolving_guard, "https://does-not-exist.invalid/")

    async def test_private_networks_can_be_explicitly_allowed(self):
        permissive = UrlGuard(allow_private_networks=True)
        permissive.validate("http://127.0.0.1/")  # no raise


async def _validate(guard: UrlGuard, url: str) -> None:
    """The guard's validate is sync; keep the async test style uniform."""
    guard.validate(url)
