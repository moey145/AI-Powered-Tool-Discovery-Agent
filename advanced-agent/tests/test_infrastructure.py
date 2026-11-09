"""Tests for search parsing, the network guard, scraping, and rate limiting."""

import logging

import httpx
import pytest

from src.net import BlockedURLError, create_client, ensure_public
from src.rate_limit import RateLimiter
from src.scraper import Scraper, extract_text
from src.search_providers import (
    BraveSearchProvider,
    DuckDuckGoSearchProvider,
    GoogleCustomSearchProvider,
    SearchHit,
    SearchManager,
    normalize_hits,
)


async def public_resolver(host: str) -> list[str]:
    return ["93.184.216.34"]


def mock_client(handler, settings, resolve=public_resolver) -> httpx.AsyncClient:
    return create_client(settings, transport=httpx.MockTransport(handler), resolve=resolve)


DDG_HTML = """
<div class="result"><a class="result__a"
  href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fredux.js.org%2F%3Futm_source%3Dx">Redux</a>
  <a class="result__snippet">State container</a></div>
<div class="result"><a class="result__a" href="/y.js?ad=1">Ad</a></div>
"""


async def test_duckduckgo_unwraps_redirects_and_skips_ads(settings):
    handler = lambda request: httpx.Response(200, text=DDG_HTML)  # noqa: E731
    async with mock_client(handler, settings) as client:
        hits = await DuckDuckGoSearchProvider(client).search("redux", 5)
    assert [hit.url for hit in hits] == ["https://redux.js.org/?utm_source=x"]
    assert hits[0].snippet == "State container"


async def test_brave_parses_results_and_sends_key(settings):
    def handler(request):
        assert request.headers["X-Subscription-Token"] == "brave-key"
        results = [{"url": "https://a.dev", "title": "A", "description": "About A"}]
        return httpx.Response(200, json={"web": {"results": results}})

    async with mock_client(handler, settings) as client:
        hits = await BraveSearchProvider(client, "brave-key").search("a", 5)
    assert hits == [SearchHit("https://a.dev", "A", "About A")]


async def test_manager_falls_back_when_first_provider_is_empty(settings):
    def handler(request):
        if request.url.host == "www.googleapis.com":
            return httpx.Response(403, text="quota")
        return httpx.Response(200, text=DDG_HTML)

    async with mock_client(handler, settings) as client:
        manager = SearchManager(
            [GoogleCustomSearchProvider(client, "k", "cx"), DuckDuckGoSearchProvider(client)]
        )
        hits = await manager.search("redux", 5)
    assert hits[0].url == "https://redux.js.org/"


async def test_manager_skips_unconfigured_providers(settings):
    async with mock_client(lambda r: httpx.Response(200, text=""), settings) as client:
        manager = SearchManager(
            [BraveSearchProvider(client, None), GoogleCustomSearchProvider(client, "k", None)]
        )
    assert manager.providers == []


async def test_provider_failures_never_log_the_api_key(settings, caplog):
    def handler(request):
        raise httpx.ConnectError("failed", request=request)

    logging.getLogger("tool_agent").propagate = True
    async with mock_client(handler, settings) as client:
        with caplog.at_level(logging.DEBUG, logger="tool_agent"):
            hits = await GoogleCustomSearchProvider(client, "SECRETKEY", "cx").search("q", 5)
    assert hits == []
    assert "SECRETKEY" not in caplog.text


def test_normalize_hits_dedupes_caps_domains_and_drops_binaries():
    hits = [
        SearchHit("https://a.dev/1?utm_source=x", "", ""),
        SearchHit("https://a.dev/1", "", ""),
        SearchHit("https://a.dev/2", "", ""),
        SearchHit("https://a.dev/3", "", ""),
        SearchHit("https://b.dev/file.pdf", "", ""),
        SearchHit("ftp://c.dev/x", "", ""),
    ]
    assert [hit.url for hit in normalize_hits(hits, 10)] == ["https://a.dev/1", "https://a.dev/2"]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/",
        "http://[::1]/",
        "http://localhost:8000/",
        "http://metadata.google.internal/",
        "file:///etc/passwd",
    ],
)
async def test_ensure_public_blocks_internal_targets(url):
    with pytest.raises(BlockedURLError):
        await ensure_public(httpx.URL(url), public_resolver)


async def test_ensure_public_blocks_hostnames_resolving_to_private_ips():
    async def private_resolver(host):
        return ["10.1.2.3"]

    with pytest.raises(BlockedURLError):
        await ensure_public(httpx.URL("https://sneaky.example.com"), private_resolver)


async def test_scraper_refuses_redirects_to_internal_addresses(settings):
    def handler(request):
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/"})

    async with mock_client(handler, settings) as client:
        assert await Scraper(client, settings).fetch("https://public.example.com") is None


def test_extract_text_prefers_main_content_and_removes_noise():
    html = """<html><head><title>T</title><meta name="description" content="Desc"></head>
    <body><nav>Menu</nav><main>Real content<script>evil()</script></main></body></html>"""
    assert extract_text(html, 1000) == ("T", "Desc Real content")


async def test_scraper_ignores_non_html(settings):
    handler = lambda r: httpx.Response(200, headers={"content-type": "image/png"}, content=b"x")  # noqa: E731
    async with mock_client(handler, settings) as client:
        assert await Scraper(client, settings).fetch("https://a.dev") is None


async def test_scraper_returns_readable_page(settings):
    body = "<html><title>A</title><main>" + "word " * 100 + "</main></html>"
    handler = lambda r: httpx.Response(200, headers={"content-type": "text/html"}, text=body)  # noqa: E731
    async with mock_client(handler, settings) as client:
        page = await Scraper(client, settings).fetch("https://a.dev")
    assert page and page.title == "A"


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


def test_rate_limiter_blocks_per_client_then_recovers():
    clock = Clock()
    limiter = RateLimiter(per_minute=2, daily_budget=100, clock=clock)
    assert limiter.check("a") is None
    assert limiter.check("a") is None
    assert limiter.check("a") == 60
    assert limiter.check("b") is None
    clock.now += 61
    assert limiter.check("a") is None


def test_rate_limiter_enforces_daily_budget_across_clients():
    clock = Clock()
    limiter = RateLimiter(per_minute=10, daily_budget=2, clock=clock)
    assert limiter.check("a") is None
    assert limiter.check("b") is None
    assert limiter.check("c") == 86_400
