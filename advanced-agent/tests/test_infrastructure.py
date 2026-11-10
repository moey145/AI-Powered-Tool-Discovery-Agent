"""Tests for search parsing, the network guard, scraping, and rate limiting."""

import logging
from datetime import UTC, datetime, timedelta

import fakeredis
import httpx
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.github import GitHubFacts, belongs_to_tool, maintenance_status, parse_repo, repo_path
from src.models import CompanyInfo, ResearchResult
from src.net import BlockedURLError, create_client, ensure_public
from src.rate_limit import RateLimiter, RedisRateLimiter
from src.scraper import Scraper, extract_text
from src.search_providers import (
    BraveSearchProvider,
    DuckDuckGoSearchProvider,
    GoogleCustomSearchProvider,
    SearchHit,
    SearchManager,
    normalize_hits,
)
from src.store import RedisResultCache


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


async def test_duckduckgo_waits_and_retries_when_asked_to_slow_down(settings):
    statuses = iter([202, 202, 200])

    def handler(request):
        status = next(statuses)
        return httpx.Response(status, text=DDG_HTML if status == 200 else "")

    async with mock_client(handler, settings) as client:
        provider = DuckDuckGoSearchProvider(client)
        provider.retry_delay = 0
        hits = await provider.search("redux", 5)
    assert len(hits) == 1


async def test_duckduckgo_gives_up_after_three_attempts(settings):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(202, text="")

    async with mock_client(handler, settings) as client:
        provider = DuckDuckGoSearchProvider(client)
        provider.retry_delay = 0
        assert await provider.search("redux", 5) == []
    assert len(calls) == 3


async def test_other_providers_do_not_retry_202(settings):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(202, json={})

    async with mock_client(handler, settings) as client:
        assert await BraveSearchProvider(client, "key").search("redux", 5) == []
    assert len(calls) == 1


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


async def test_rate_limiter_blocks_per_client_then_recovers():
    clock = Clock()
    limiter = RateLimiter(per_minute=2, daily_budget=100, clock=clock)
    assert await limiter.check("a") is None
    assert await limiter.check("a") is None
    assert await limiter.check("a") == 60
    assert await limiter.check("b") is None
    clock.now += 61
    assert await limiter.check("a") is None


async def test_rate_limiter_enforces_daily_budget_across_clients():
    clock = Clock()
    limiter = RateLimiter(per_minute=10, daily_budget=2, clock=clock)
    assert await limiter.check("a") is None
    assert await limiter.check("b") is None
    assert await limiter.check("c") == 86_400


async def test_redis_rate_limiter_is_shared_between_instances():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    clock = lambda: 1_000_000.0  # noqa: E731
    first = RedisRateLimiter(redis, per_minute=2, daily_budget=100, clock=clock)
    second = RedisRateLimiter(redis, per_minute=2, daily_budget=100, clock=clock)
    assert await first.check("a") is None
    assert await second.check("a") is None
    assert await first.check("a") == 20


async def test_redis_rate_limiter_enforces_daily_budget():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = RedisRateLimiter(redis, 10, daily_budget=1, clock=lambda: 1_000_000.0)
    assert await limiter.check("a") is None
    assert await limiter.check("b") == 86_400 - 1_000_000 % 86_400


class BrokenRedis:
    async def incr(self, key):
        raise RedisConnectionError("down")

    async def get(self, key):
        raise RedisConnectionError("down")

    async def set(self, key, value, ex=None):
        raise RedisConnectionError("down")


async def test_rate_limits_still_apply_when_redis_is_down():
    limiter = RedisRateLimiter(BrokenRedis(), per_minute=1, daily_budget=100)
    assert await limiter.check("a") is None
    assert await limiter.check("a") is not None


async def test_redis_cache_round_trips_results():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = RedisResultCache(redis, 60)
    result = ResearchResult(query="q", companies=[CompanyInfo(name="X", description="d")])
    await cache.set("q", result)
    assert await cache.get("q") == result
    assert await cache.get("other") is None


async def test_redis_cache_treats_outages_as_a_miss():
    cache = RedisResultCache(BrokenRedis(), 60)
    await cache.set("q", ResearchResult(query="q"))
    assert await cache.get("q") is None


def repo_json(**overrides):
    values = {
        "html_url": "https://github.com/pallets/flask",
        "full_name": "pallets/flask",
        "stargazers_count": 70000,
        "license": {"spdx_id": "BSD-3-Clause"},
        "pushed_at": "2026-10-01T00:00:00Z",
        "archived": False,
        "homepage": "https://flask.palletsprojects.com",
    }
    return {**values, **overrides}


async def test_github_uses_a_known_repository_url(settings):
    def handler(request):
        assert request.url.path == "/repos/pallets/flask"
        return httpx.Response(200, json=repo_json())

    urls = ["https://github.com/pallets/flask", "https://flask.palletsprojects.com/en/stable/"]
    async with mock_client(handler, settings) as client:
        facts = await GitHubFacts(client).facts_for("Flask", urls)
    assert facts.is_open_source and facts.license == "BSD-3-Clause" and facts.stars == 70000


async def test_github_search_requires_an_exact_name_and_real_adoption(settings):
    items = [
        repo_json(full_name="someone/flask-extras", stargazers_count=90000),
        repo_json(full_name="someone/flask", stargazers_count=12),
        repo_json(),
    ]

    def handler(request):
        assert request.url.path == "/search/repositories"
        return httpx.Response(200, json={"items": items})

    async with mock_client(handler, settings) as client:
        facts = await GitHubFacts(client).facts_for("Flask", ["https://flask.palletsprojects.com"])
    assert facts.url == "https://github.com/pallets/flask"


async def test_github_rejects_a_same_named_repository_from_someone_else(settings):
    impostor = repo_json(
        full_name="wmww/Pinecone",
        html_url="https://github.com/wmww/Pinecone",
        homepage="http://pinecone-lang.herokuapp.com/",
    )
    handler = lambda request: httpx.Response(200, json={"items": [impostor]})  # noqa: E731
    async with mock_client(handler, settings) as client:
        assert await GitHubFacts(client).facts_for("Pinecone", ["https://www.pinecone.io"]) is None


async def test_github_search_needs_a_homepage_match_even_for_a_same_named_account(settings):
    robot = repo_json(
        full_name="husky/husky",
        html_url="https://github.com/husky/husky",
        homepage="http://wiki.ros.org/Robots/Husky",
    )
    handler = lambda request: httpx.Response(200, json={"items": [robot]})  # noqa: E731
    urls = ["https://typicode.github.io/husky/"]
    async with mock_client(handler, settings) as client:
        assert await GitHubFacts(client).facts_for("Husky", urls) is None


async def test_github_rejects_an_unrelated_repository_found_in_search_results(settings):
    personal = repo_json(
        full_name="vinijmoura/Azure-DevOps",
        html_url="https://github.com/vinijmoura/Azure-DevOps",
        homepage="",
    )
    handler = lambda request: httpx.Response(200, json=personal)  # noqa: E731
    urls = ["https://github.com/vinijmoura/Azure-DevOps", "https://azure.microsoft.com/devops"]
    async with mock_client(handler, settings) as client:
        assert await GitHubFacts(client).facts_for("Azure DevOps", urls) is None


@pytest.mark.parametrize(
    ("tool", "full_name", "homepage", "urls", "expected"),
    [
        ("Jest", "jestjs/jest", "", [], True),
        ("Vitest", "vitest-dev/vitest", "", [], True),
        ("Sentry", "getsentry/sentry", "", [], True),
        ("Django", "django/django", "", [], True),
        ("AWS CDK", "aws/aws-cdk", "", [], True),
        ("Warp", "warpdotdev/warp", "https://www.warp.dev", ["https://docs.rs/warp"], False),
        ("Zustand", "pmndrs/zustand", "https://zustand-demo.pmnd.rs/", ["https://x.pmnd.rs"], True),
        ("Pinecone", "wmww/Pinecone", "http://p.herokuapp.com", ["https://q.herokuapp.com"], False),
        ("Overcommit", "sds/overcommit", "", ["https://github.com/sds/overcommit"], False),
    ],
)
def test_belongs_to_tool(tool, full_name, homepage, urls, expected):
    assert belongs_to_tool(tool, {"full_name": full_name, "homepage": homepage}, urls) is expected


async def test_github_failures_return_nothing(settings):
    handler = lambda request: httpx.Response(403, json={})  # noqa: E731
    async with mock_client(handler, settings) as client:
        assert await GitHubFacts(client).facts_for("Flask", []) is None


def test_non_open_source_licenses_are_not_labelled_open_source():
    facts = parse_repo(repo_json(license={"spdx_id": "NOASSERTION"}))
    assert facts.is_open_source is False and facts.license is None


@pytest.mark.parametrize(
    ("days", "archived", "expected"),
    [(10, False, "active"), (400, False, "slowing"), (1000, False, "stale"), (1, True, "archived")],
)
def test_maintenance_status(days, archived, expected):
    now = datetime(2026, 11, 1, tzinfo=UTC)
    assert maintenance_status(now - timedelta(days=days), archived, now) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/pallets/flask/tree/main", "pallets/flask"),
        ("https://github.com/features/actions", None),
        ("https://github.com/pallets", None),
        ("https://gitlab.com/a/b", None),
    ],
)
def test_repo_path(url, expected):
    assert repo_path(url) == expected
