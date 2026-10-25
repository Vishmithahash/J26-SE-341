"""The connection probe must bracket IPv6 addresses (localhost resolves to ::1 on Windows)."""

import asyncio
from unittest.mock import patch

import httpx

from app.shared.projects import connection_service


def test_probe_brackets_ipv6_loopback_address():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"status": "ok"})

    real_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    with (
        patch.object(
            connection_service,
            "validate_target_safety",
            return_value=(True, None, "::1"),
        ),
        patch.object(
            connection_service.httpx, "AsyncClient", side_effect=client_factory
        ),
    ):
        outcome = asyncio.run(
            connection_service.probe_endpoint("http://localhost:3100/api/v1/health")
        )

    assert outcome.reachable is True
    assert seen == ["http://[::1]:3100/api/v1/health"]
