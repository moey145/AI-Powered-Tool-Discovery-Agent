import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from .config import Settings
from .logger import get_logger

logger = get_logger("search")

_RETRYABLE = {429, 500, 502, 503, 504}
_TRACKING = {"gclid", "fbclid", "mc_cid", "mc_eid"}
_BINARY_EXTENSIONS = (".pdf", ".zip", ".rar", ".7z", ".dmg", ".exe")
_MAX_PER_DOMAIN = 2


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str
    snippet: str


def clean_url(url: str) -> str:
    parts = urlparse(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING
    ]
    return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, urlencode(query), ""))


def normalize_hits(hits: list[SearchHit], limit: int) -> list[SearchHit]:
    """Drop duplicates and binary files, and keep at most two results per domain."""
    seen: set[str] = set()
    per_domain: dict[str, int] = {}
    output: list[SearchHit] = []
    for hit in hits:
        parts = urlparse(hit.url)
        if parts.scheme not in {"http", "https"} or parts.path.lower().endswith(_BINARY_EXTENSIONS):
            continue
        url = clean_url(hit.url)
        domain = parts.netloc.lower()
        if url in seen or per_domain.get(domain, 0) >= _MAX_PER_DOMAIN:
            continue
        seen.add(url)
        per_domain[domain] = per_domain.get(domain, 0) + 1
        output.append(SearchHit(url=url, title=hit.title[:200], snippet=hit.snippet[:400]))
        if len(output) == limit:
            break
    return output


class SearchProvider(ABC):
    name: str

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    async def _request(self, query: str, limit: int) -> httpx.Response: ...

    @abstractmethod
    def _parse(self, response: httpx.Response) -> list[SearchHit]: ...

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        """Return hits, retrying once on a transient failure. Never raises for HTTP errors."""
        for attempt in range(2):
            try:
                response = await self._request(query, limit)
            except httpx.HTTPError as exc:
                # Log only the type: the exception text can contain a URL with an API key.
                logger.warning("%s request failed: %s", self.name, type(exc).__name__)
                continue
            if response.status_code == 200:
                return self._parse(response)
            logger.warning("%s returned HTTP %s", self.name, response.status_code)
            if response.status_code not in _RETRYABLE:
                break
            if attempt == 0:
                await asyncio.sleep(0.5)
        return []


class BraveSearchProvider(SearchProvider):
    name = "brave"

    def __init__(self, client: httpx.AsyncClient, api_key: str | None):
        super().__init__(client)
        self.api_key = api_key

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def _request(self, query: str, limit: int) -> httpx.Response:
        return await self.client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": min(limit, 20)},
            headers={"X-Subscription-Token": self.api_key or "", "Accept": "application/json"},
        )

    def _parse(self, response: httpx.Response) -> list[SearchHit]:
        results = response.json().get("web", {}).get("results", [])
        return [
            SearchHit(url=r["url"], title=r.get("title", ""), snippet=r.get("description", ""))
            for r in results
            if r.get("url")
        ]


class GoogleCustomSearchProvider(SearchProvider):
    name = "google_custom_search"

    def __init__(self, client: httpx.AsyncClient, api_key: str | None, engine_id: str | None):
        super().__init__(client)
        self.api_key = api_key
        self.engine_id = engine_id

    def is_available(self) -> bool:
        return bool(self.api_key and self.engine_id)

    async def _request(self, query: str, limit: int) -> httpx.Response:
        return await self.client.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": self.api_key,
                "cx": self.engine_id,
                "q": query,
                "num": min(limit, 10),
                "safe": "active",
                "fields": "items(title,link,snippet)",
            },
        )

    def _parse(self, response: httpx.Response) -> list[SearchHit]:
        return [
            SearchHit(url=i["link"], title=i.get("title", ""), snippet=i.get("snippet", ""))
            for i in response.json().get("items", [])
            if i.get("link")
        ]


class DuckDuckGoSearchProvider(SearchProvider):
    """Keyless fallback using DuckDuckGo's HTML page."""

    name = "duckduckgo"

    def is_available(self) -> bool:
        return True

    async def _request(self, query: str, limit: int) -> httpx.Response:
        return await self.client.post(
            "https://html.duckduckgo.com/html/", data={"q": query, "kl": "us-en"}
        )

    def _parse(self, response: httpx.Response) -> list[SearchHit]:
        soup = BeautifulSoup(response.text, "html.parser")
        hits: list[SearchHit] = []
        for container in soup.select("div.result"):
            link = container.select_one("a.result__a")
            href = str(link.get("href", "")) if link else ""
            if not link or not href or href.startswith(("/y.js", "#")):
                continue
            url = self._unwrap(href)
            if url is None:
                continue
            title = link.get_text(strip=True)
            snippet_el = container.select_one(".result__snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else title
            hits.append(SearchHit(url=url, title=title, snippet=snippet))
        return hits

    @staticmethod
    def _unwrap(href: str) -> str | None:
        """Result links usually point at a DuckDuckGo redirect that holds the real URL."""
        absolute = urljoin("https://duckduckgo.com/", href)
        parts = urlparse(absolute)
        if parts.netloc.endswith("duckduckgo.com"):
            target = parse_qs(parts.query).get("uddg")
            return target[0] if target else None
        return absolute


class SearchManager:
    """Tries providers in order until one returns results."""

    def __init__(self, providers: list[SearchProvider]):
        self.providers = [provider for provider in providers if provider.is_available()]

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        for provider in self.providers:
            hits = normalize_hits(await provider.search(query, limit), limit)
            if hits:
                return hits
        logger.warning("No search provider returned results")
        return []


def _secret(value) -> str | None:
    return value.get_secret_value() if value else None


def create_search_manager(settings: Settings, client: httpx.AsyncClient) -> SearchManager:
    brave = BraveSearchProvider(client, _secret(settings.brave_search_api_key))
    google = GoogleCustomSearchProvider(
        client, _secret(settings.google_custom_search_api_key), settings.google_search_engine_id
    )
    duckduckgo = DuckDuckGoSearchProvider(client)
    order: list[SearchProvider] = [brave, google, duckduckgo]
    preferred = next((p for p in order if p.name == settings.search_provider), None)
    if preferred:
        order = [preferred, *(p for p in order if p is not preferred)]
    return SearchManager(order)
