"""Outbound HTTP client that refuses to reach private or internal addresses."""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable

import httpx

from .config import Settings

Resolver = Callable[[str], Awaitable[list[str]]]


class BlockedURLError(httpx.TransportError):
    """The request targeted a non-public address."""


async def resolve_host(host: str) -> list[str]:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []  # Unresolvable hosts fail on their own when the request is sent.
    return [info[4][0] for info in infos]


def _is_public(address: str) -> bool:
    try:
        return ipaddress.ip_address(address.split("%", 1)[0]).is_global
    except ValueError:
        return False


async def ensure_public(url: httpx.URL, resolve: Resolver = resolve_host) -> None:
    if url.scheme not in {"http", "https"}:
        raise BlockedURLError(f"Unsupported scheme: {url.scheme}")
    host = url.host
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        if host == "localhost" or host.endswith((".localhost", ".internal", ".local")):
            raise BlockedURLError(f"Blocked host: {host}") from None
        addresses = await resolve(host)
    if not all(_is_public(address) for address in addresses):
        raise BlockedURLError(f"Blocked host: {host}")


def create_client(
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None = None,
    resolve: Resolver = resolve_host,
) -> httpx.AsyncClient:
    async def guard(request: httpx.Request) -> None:
        # Event hooks also run for every redirect hop.
        await ensure_public(request.url, resolve)

    return httpx.AsyncClient(
        transport=transport,
        follow_redirects=True,
        timeout=settings.http_timeout,
        headers={"User-Agent": settings.user_agent, "Accept-Language": "en-US,en;q=0.9"},
        limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
        event_hooks={"request": [guard]},
    )
