"""The research pipeline: discover tools, research each one, then recommend."""

import asyncio
import re
import time
from collections.abc import AsyncIterator
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar
from urllib.parse import urlparse

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from .config import Settings
from .github import GitHubFacts, RepoFacts
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
from .store import RedisResultCache, ResultCache

logger = get_logger("workflow")

Schema = TypeVar("Schema", bound=BaseModel)
Event = dict[str, Any]

_ARTICLES_TO_READ = 3
_PAGES_PER_TOOL = 2
_MIN_TOOLS = 3
_RETRY_PHRASING = "{query} top alternatives list"
_UNREADABLE_DOMAINS = (
    "reddit.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "youtube.com",
    "instagram.com",
    "quora.com",
    "pinterest.com",
)
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


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


_usage: ContextVar[Usage | None] = ContextVar("llm_usage", default=None)


def _record_usage(message: Any) -> None:
    usage = _usage.get()
    metadata = getattr(message, "usage_metadata", None)
    if usage is not None and metadata:
        usage.input_tokens += metadata.get("input_tokens", 0)
        usage.output_tokens += metadata.get("output_tokens", 0)


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
        model = self._chat.with_structured_output(schema, include_raw=True)
        output = await model.ainvoke([SystemMessage(system), HumanMessage(user)])
        _record_usage(output["raw"])
        if output["parsed"] is None:
            raise ValueError("The model returned no usable output")
        return output["parsed"]

    async def text(self, system: str, user: str) -> str:
        response = await self._chat.ainvoke([SystemMessage(system), HumanMessage(user)])
        _record_usage(response)
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


def _url_key(url: str) -> str:
    # Models sometimes copy a source label together with its surrounding brackets.
    return url.strip().strip("[]<>").strip().rstrip("/").lower()


def is_readable(url: str) -> bool:
    """False for sites that usually block scraping or show only a login wall."""
    host = _host(url)
    return not any(host == domain or host.endswith(f".{domain}") for domain in _UNREADABLE_DOMAINS)


def _progress(stage: str, message: str, percent: int, **extra: Any) -> Event:
    return {"type": "progress", "stage": stage, "message": message, "percent": percent, **extra}


class Workflow:
    def __init__(
        self,
        settings: Settings,
        llm: LLM,
        search: SearchManager,
        scraper: Scraper,
        cache: ResultCache | RedisResultCache | None = None,
        github: GitHubFacts | None = None,
    ):
        self.settings = settings
        self.llm = llm
        self.search = search
        self.scraper = scraper
        self.github = github
        self.cache = cache or ResultCache(settings.cache_ttl_seconds)
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
        cached = await self.cache.get(key)
        if cached:
            logger.info("Served from cache")
            yield {"type": "result", "result": cached}
            return

        started = time.monotonic()
        usage = Usage()
        _usage.set(usage)
        state: ResearchState = {}
        inputs: ResearchState = {"query": query}
        async for mode, payload in self.graph.astream(inputs, stream_mode=["custom", "values"]):
            if mode == "custom":
                yield payload
            else:
                state = payload

        result = self._to_result(query, state)
        cost = (
            usage.input_tokens * self.settings.input_price_per_million
            + usage.output_tokens * self.settings.output_price_per_million
        ) / 1_000_000
        logger.info(
            "Search finished status=%s tools=%s input_tokens=%s output_tokens=%s "
            "estimated_cost_usd=%.5f seconds=%.1f",
            result.status,
            len(result.companies),
            usage.input_tokens,
            usage.output_tokens,
            cost,
            time.monotonic() - started,
        )
        if result.status == "success":
            await self.cache.set(key, result)
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
        tools, preference = await self._find_tools(query, f"best {query}", write)
        if len(tools) < _MIN_TOOLS:
            write(_progress("extracting", "Checking more sources", 20))
            more, _ = await self._find_tools(query, _RETRY_PHRASING.format(query=query))
            seen = {tool.casefold() for tool in tools}
            tools += [tool for tool in more if tool.casefold() not in seen]
        tools = tools[: self.settings.max_tools]
        if tools:
            write(_progress("researching", f"Found {len(tools)} tools", 25, tools=tools))
        return {"tools": tools, "pricing_preference": preference}

    async def _find_tools(
        self, query: str, search_query: str, write: Any = None
    ) -> tuple[list[str], PricingPreference]:
        hits = await self.search.search(search_query, 8)
        if not hits:
            return [], "any"

        if write:
            write(_progress("reading", "Reading comparison articles", 12))
        readable = [hit.url for hit in hits if is_readable(hit.url)]
        pages = await self.scraper.fetch_many(readable[:_ARTICLES_TO_READ])

        sections = [(hit.title or hit.url, hit.snippet) for hit in hits]
        sections += [(page.title or page.url, page.text) for page in pages]
        sources = format_sources(sections)

        if write:
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
        return tools, discovery.pricing_preference

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
                    if company:
                        write({"type": "tool", "company": company.model_dump(mode="json")})
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
        readable = [hit.url for hit in ranked if is_readable(hit.url)][:_PAGES_PER_TOOL]
        urls = readable + self._pricing_page(name, ranked, readable)
        pages = await self.scraper.fetch_many(urls)
        sections = [(hit.url, f"{hit.title}. {hit.snippet}") for hit in hits]
        sections += [(page.url, page.text) for page in pages]
        analysis = await self.llm.structured(
            ToolAnalysis,
            ANALYSIS_SYSTEM,
            f"Tool: {name}\nSearch: {query}\n\n{format_sources(sections)}",
        )
        if not analysis.describes_requested_tool:
            logger.info("Sources for %s describe a different product", name)
            return None

        # Search results for a shared name mix products (Warp the terminal, warp the web
        # framework), so only sources the analysis judged relevant can supply links and facts.
        relevant = {_url_key(url) for url in analysis.relevant_sources}
        ranked = [hit for hit in ranked if _url_key(hit.url) in relevant]
        pages = [page for page in pages if _url_key(page.url) in relevant]
        relevant_urls = [hit.url for hit in ranked] + [page.url for page in pages]

        website = self._choose_website(name, analysis.website, ranked, pages)
        sources = [page.url for page in pages] or [hit.url for hit in ranked[:_PAGES_PER_TOOL]]
        facts = await self._repo_facts(name, relevant_urls)
        company = CompanyInfo(
            name=name,
            description=analysis.description,
            website=website,
            pricing_model=analysis.pricing_model,
            is_open_source=analysis.is_open_source,
            api_available=analysis.api_available,
            tech_stack=analysis.tech_stack[:5],
            language_support=analysis.language_support[:5],
            integration_capabilities=analysis.integration_capabilities[:5],
            sources=sources,
        )
        return self._apply_repo_facts(company, facts, analysis.paid_plans_mentioned)

    @staticmethod
    def _pricing_page(name: str, ranked: list[SearchHit], already: list[str]) -> list[str]:
        """Add the official site's /pricing page, where pricing is most likely stated."""
        official = next((hit.url for hit in ranked if official_score(name, hit.url) == 3), None)
        if official is None:
            return []
        parts = urlparse(official)
        pricing = f"{parts.scheme}://{parts.netloc}/pricing"
        return [] if pricing in already else [pricing]

    async def _repo_facts(self, name: str, urls: list[str]) -> RepoFacts | None:
        if self.github is None:
            return None
        try:
            return await self.github.facts_for(name, urls)
        except Exception:
            logger.warning("GitHub lookup failed for %s", name, exc_info=True)
            return None

    @staticmethod
    def _apply_repo_facts(
        company: CompanyInfo, facts: RepoFacts | None, paid_plans_mentioned: bool
    ) -> CompanyInfo:
        """Overlay facts from the GitHub API, which are more reliable than extracted text.

        An open-source license plus sources that mention no paid offering means Free, even if
        the model guessed Freemium or Paid. Tools like Supabase, which are open source but
        sell a hosted plan, keep the model's label.
        """
        if facts is None:
            return company
        updates: dict[str, Any] = {
            "github_url": facts.url,
            "github_stars": facts.stars,
            "license": facts.license,
            "last_commit": facts.last_commit,
            "maintenance": facts.maintenance,
            "website": company.website or facts.homepage or facts.url,
        }
        if facts.is_open_source:
            updates["is_open_source"] = True
            if not paid_plans_mentioned:
                updates["pricing_model"] = PricingModel.FREE
        if facts.url not in company.sources:
            updates["sources"] = [*company.sources, facts.url]
        return company.model_copy(update=updates)

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


def create_workflow(
    settings: Settings,
    client: httpx.AsyncClient,
    cache: ResultCache | RedisResultCache | None = None,
) -> Workflow:
    token = settings.github_token.get_secret_value() if settings.github_token else None
    return Workflow(
        settings=settings,
        llm=OpenAILLM(settings),
        search=create_search_manager(settings, client),
        scraper=Scraper(client, settings),
        cache=cache,
        github=GitHubFacts(client, token),
    )
