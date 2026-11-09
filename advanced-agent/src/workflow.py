"""The research pipeline: discover tools, research each one, then recommend."""

import asyncio
import re
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Any, Protocol, TypeVar
from urllib.parse import urlparse

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from .config import Settings
from .logger import get_logger
from .models import (
    CompanyInfo,
    PricingModel,
    PricingPreference,
    ResearchResult,
    ResearchState,
    ToolAnalysis,
    ToolDiscovery,
)
from .prompts import ANALYSIS_SYSTEM, DISCOVERY_SYSTEM, RECOMMENDATION_SYSTEM, format_sources
from .scraper import Page, Scraper
from .search_providers import SearchHit, SearchManager, create_search_manager

logger = get_logger("workflow")

Schema = TypeVar("Schema", bound=BaseModel)
Event = dict[str, Any]

_ARTICLES_TO_READ = 3
_PAGES_PER_TOOL = 2
_NON_OFFICIAL_DOMAINS = (
    "wikipedia.org",
    "medium.com",
    "reddit.com",
    "youtube.com",
    "g2.com",
    "capterra.com",
    "stackshare.io",
    "dev.to",
    "linkedin.com",
    "stackoverflow.com",
    "alternativeto.net",
)


class LLM(Protocol):
    async def structured(self, schema: type[Schema], system: str, user: str) -> Schema: ...

    async def text(self, system: str, user: str) -> str: ...


class OpenAILLM:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None):
        self._chat = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout,
            max_retries=2,
            http_async_client=http_client,
        )

    async def structured(self, schema: type[Schema], system: str, user: str) -> Schema:
        model = self._chat.with_structured_output(schema)
        return await model.ainvoke([SystemMessage(system), HumanMessage(user)])

    async def text(self, system: str, user: str) -> str:
        response = await self._chat.ainvoke([SystemMessage(system), HumanMessage(user)])
        content = response.content
        if isinstance(content, str):
            return content
        return "".join(block.get("text", "") for block in content if isinstance(block, dict))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def is_grounded(name: str, corpus: str) -> bool:
    """True if a tool name literally appears in the text it was supposedly extracted from."""
    candidates = {name.lower(), re.sub(r"\.js$", "", name.lower())}
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])", corpus)
        for candidate in candidates
        if candidate
    )


def official_score(name: str, url: str) -> int:
    """Score how likely a URL is to be the tool's own site. Positive means likely."""
    parts = urlparse(url)
    host = parts.netloc.lower().removeprefix("www.")
    if any(host == domain or host.endswith(f".{domain}") for domain in _NON_OFFICIAL_DOMAINS):
        return -1
    slug = _slug(name)
    # Compare the start of each domain label so "Flask" doesn't match hydroflask.com.
    if slug and any(_slug(label).startswith(slug) for label in host.split(".")):
        return 3
    if host == "github.com" and slug in _slug(parts.path):
        return 2
    return 0


def matches_pricing(company: CompanyInfo, preference: PricingPreference) -> bool:
    """Whether a tool fits the requested pricing. Tools of unknown pricing are kept."""
    if preference == "any" or company.pricing_model is PricingModel.UNKNOWN:
        return True
    if preference == "free":
        # A free tier is usable for free, and the result still shows it as Freemium.
        return (
            company.pricing_model in {PricingModel.FREE, PricingModel.FREEMIUM}
            or company.is_open_source is True
        )
    if preference == "freemium":
        return company.pricing_model is PricingModel.FREEMIUM
    return company.pricing_model in {
        PricingModel.PAID,
        PricingModel.ENTERPRISE,
        PricingModel.FREEMIUM,
    }


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _progress(stage: str, message: str, percent: int, **extra: Any) -> Event:
    return {"type": "progress", "stage": stage, "message": message, "percent": percent, **extra}


class ResultCache:
    def __init__(self, ttl_seconds: int, max_entries: int = 128):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, ResearchResult]] = OrderedDict()

    def get(self, key: str) -> ResearchResult | None:
        item = self._items.get(key)
        if item is None:
            return None
        if time.monotonic() - item[0] >= self.ttl:
            del self._items[key]
            return None
        self._items.move_to_end(key)
        return item[1]

    def set(self, key: str, value: ResearchResult) -> None:
        self._items[key] = (time.monotonic(), value)
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)


class Workflow:
    def __init__(self, settings: Settings, llm: LLM, search: SearchManager, scraper: Scraper):
        self.settings = settings
        self.llm = llm
        self.search = search
        self.scraper = scraper
        self.cache = ResultCache(settings.cache_ttl_seconds)
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(ResearchState)
        graph.add_node("discover", self._discover)
        graph.add_node("research", self._research)
        graph.add_node("recommend", self._recommend)
        graph.add_edge(START, "discover")
        graph.add_conditional_edges(
            "discover", lambda state: "research" if state.get("tools") else END
        )
        graph.add_edge("research", "recommend")
        graph.add_edge("recommend", END)
        return graph.compile()

    async def stream(self, query: str) -> AsyncIterator[Event]:
        """Yield progress events, then one final {"type": "result", "result": ...} event."""
        key = query.casefold()
        cached = self.cache.get(key)
        if cached:
            yield {"type": "result", "result": cached}
            return

        state: ResearchState = {}
        inputs: ResearchState = {"query": query}
        async for mode, payload in self.graph.astream(inputs, stream_mode=["custom", "values"]):
            if mode == "custom":
                yield payload
            else:
                state = payload

        result = self._to_result(query, state)
        if result.status == "success":
            self.cache.set(key, result)
        yield {"type": "result", "result": result}

    async def run(self, query: str) -> ResearchResult:
        async for event in self.stream(query):
            if event["type"] == "result":
                return event["result"]
        raise RuntimeError("Workflow ended without a result")

    @staticmethod
    def _to_result(query: str, state: ResearchState) -> ResearchResult:
        companies = state.get("companies", [])
        unresearched = state.get("unresearched", [])
        if not companies:
            status = "no_results"
        elif unresearched:
            status = "partial"
        else:
            status = "success"
        return ResearchResult(
            query=query,
            companies=companies,
            analysis=state.get("analysis"),
            status=status,
            unresearched=unresearched,
            pricing_preference=state.get("pricing_preference", "any"),
        )

    async def _discover(self, state: ResearchState) -> ResearchState:
        write = get_stream_writer()
        query = state["query"]
        write(_progress("searching", "Searching the web", 5))
        hits = await self.search.search(f"best {query}", 8)
        if not hits:
            return {"tools": []}

        write(_progress("reading", "Reading comparison articles", 12))
        pages = await self.scraper.fetch_many([hit.url for hit in hits[:_ARTICLES_TO_READ]])

        sections = [(hit.title or hit.url, hit.snippet) for hit in hits]
        sections += [(page.title or page.url, page.text) for page in pages]
        sources = format_sources(sections)

        write(_progress("extracting", "Identifying relevant tools", 18))
        system = DISCOVERY_SYSTEM.format(max_tools=self.settings.max_tools)
        discovery = await self.llm.structured(
            ToolDiscovery, system, f"Query: {query}\n\n{sources}"
        )

        corpus = sources.lower()
        tools: list[str] = []
        seen: set[str] = set()
        for raw in discovery.tools:
            name = raw.strip()
            if name and name.casefold() not in seen and is_grounded(name, corpus):
                seen.add(name.casefold())
                tools.append(name)
        tools = tools[: self.settings.max_tools]
        write(_progress("researching", f"Found {len(tools)} tools", 25, tools=tools))
        return {"tools": tools, "pricing_preference": discovery.pricing_preference}

    async def _research(self, state: ResearchState) -> ResearchState:
        write = get_stream_writer()
        tools = state["tools"]
        semaphore = asyncio.Semaphore(self.settings.max_concurrent_research)

        async def research_one(name: str) -> tuple[str, CompanyInfo | None]:
            async with semaphore:
                try:
                    return name, await self._research_tool(name, state["query"])
                except Exception:
                    logger.warning("Research failed for %s", name, exc_info=True)
                    return name, None

        tasks = [asyncio.create_task(research_one(name)) for name in tools]
        results: dict[str, CompanyInfo | None] = {}
        try:
            async with asyncio.timeout(self.settings.research_timeout):
                for finished in asyncio.as_completed(tasks):
                    name, company = await finished
                    results[name] = company
                    percent = 25 + round(60 * len(results) / len(tools))
                    write(_progress("researching", f"Researched {name}", percent, tool=name))
        except TimeoutError:
            logger.warning("Research hit its time limit with %s/%s done", len(results), len(tools))
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        companies = [results[name] for name in tools if results.get(name)]
        unresearched = [name for name in tools if not results.get(name)]
        return {"companies": companies, "unresearched": unresearched}

    async def _research_tool(self, name: str, query: str) -> CompanyInfo | None:
        # The user's query disambiguates names like Flask, Rocket, or Echo.
        hits = await self.search.search(f"{name} {query} official site pricing", 5)
        if not hits:
            return None
        ranked = sorted(hits, key=lambda hit: official_score(name, hit.url), reverse=True)
        pages = await self.scraper.fetch_many([hit.url for hit in ranked[:_PAGES_PER_TOOL]])
        sections = [(hit.url, f"{hit.title}. {hit.snippet}") for hit in hits]
        sections += [(page.url, page.text) for page in pages]
        analysis = await self.llm.structured(
            ToolAnalysis, ANALYSIS_SYSTEM, f"Tool: {name}\n\n{format_sources(sections)}"
        )
        return CompanyInfo(
            name=name,
            description=analysis.description,
            website=self._choose_website(name, analysis.website, ranked, pages),
            pricing_model=analysis.pricing_model,
            is_open_source=analysis.is_open_source,
            api_available=analysis.api_available,
            tech_stack=analysis.tech_stack[:5],
            language_support=analysis.language_support[:5],
            integration_capabilities=analysis.integration_capabilities[:5],
            sources=[page.url for page in pages] or [hit.url for hit in ranked[:_PAGES_PER_TOOL]],
        )

    @staticmethod
    def _choose_website(
        name: str, proposed: str | None, ranked: list[SearchHit], pages: list[Page]
    ) -> str | None:
        """Only return a URL backed by what we actually retrieved. Never construct one."""
        known_urls = [hit.url for hit in ranked] + [page.url for page in pages]
        if proposed and proposed.startswith(("http://", "https://")):
            if _host(proposed) in {_host(url) for url in known_urls}:
                return proposed
        best = next((url for url in known_urls if official_score(name, url) > 0), None)
        if best is None:
            return None
        parts = urlparse(best)
        return f"{parts.scheme}://{parts.netloc}" if parts.netloc != "github.com" else best

    async def _recommend(self, state: ResearchState) -> ResearchState:
        write = get_stream_writer()
        companies = state.get("companies", [])
        if not companies:
            return {"analysis": None}
        preference = state.get("pricing_preference", "any")
        matching = [c for c in companies if matches_pricing(c, preference)] or companies

        write(_progress("recommending", "Writing the recommendation", 90))
        facts = "\n".join(
            f"- {c.name}: {c.description} Pricing: {c.pricing_model.value}. "
            f"Open source: {c.is_open_source}."
            for c in matching
        )
        try:
            analysis = await self.llm.text(
                RECOMMENDATION_SYSTEM, f"Query: {state['query']}\n\nTools:\n{facts}"
            )
        except Exception:
            logger.warning("Recommendation failed", exc_info=True)
            analysis = None
        return {"companies": matching, "analysis": analysis}


def create_workflow(settings: Settings, client: httpx.AsyncClient) -> Workflow:
    return Workflow(
        settings=settings,
        llm=OpenAILLM(settings),
        search=create_search_manager(settings, client),
        scraper=Scraper(client, settings),
    )
