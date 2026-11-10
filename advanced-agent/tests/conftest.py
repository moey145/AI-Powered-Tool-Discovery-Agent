import asyncio
import os
import re

os.environ["OPENAI_API_KEY"] = "test-key"  # Lets `api` import without a real key.

import pytest

from src.config import Settings
from src.models import PricingModel, ToolAnalysis, ToolDiscovery
from src.scraper import Page
from src.search_providers import SearchHit


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, openai_api_key="test-key", research_timeout=2.0)


def analysis(**overrides) -> ToolAnalysis:
    values = {
        "describes_requested_tool": True,
        "relevant_sources": ["*"],  # FakeLLM expands this to every source it was shown.
        "description": "A tool.",
        "website": None,
        "pricing_model": PricingModel.FREE,
        "paid_plans_mentioned": False,
        "is_open_source": True,
        "api_available": None,
        "tech_stack": [],
        "language_support": [],
        "integration_capabilities": [],
    }
    return ToolAnalysis(**{**values, **overrides})


class FakeLLM:
    def __init__(self, tools=("Redux", "Zustand"), preference="any", analyses=None):
        self.tools = list(tools)
        self.preference = preference
        self.analyses = analyses or {}
        self.calls: list[str] = []
        self.prompts: list[str] = []
        self.fail_for: set[str] = set()
        self.delay_for: set[str] = set()
        self.fail_text = False

    async def structured(self, schema, system, user):
        self.calls.append(schema.__name__)
        self.prompts.append(user)
        if schema is ToolDiscovery:
            return ToolDiscovery(tools=self.tools, pricing_preference=self.preference)
        name = user.split("\n", 1)[0].removeprefix("Tool: ")
        if name in self.delay_for:
            await asyncio.sleep(30)
        if name in self.fail_for:
            raise RuntimeError("model error with secret detail")
        result = self.analyses.get(name, analysis())
        if result.relevant_sources == ["*"]:
            shown = re.findall(r"^\[(https?://[^\]]+)\]$", user, flags=re.MULTILINE)
            result = result.model_copy(update={"relevant_sources": shown})
        return result

    async def text(self, system, user):
        self.calls.append("text")
        if self.fail_text:
            raise RuntimeError("model error")
        return "Pick **Redux**."


class FakeSearch:
    """Returns one article mentioning every tool, unless given specific hits."""

    def __init__(self, article="Redux and Zustand and Vue.js are popular.", tool_hits=None):
        self.article = article
        self.tool_hits = tool_hits
        self.tool_queries: list[str] = []
        self.discovery_queries: list[str] = []

    async def search(self, query, limit):
        if self.article is None:
            return []
        if query.startswith("best ") or query.endswith(" top alternatives list"):
            self.discovery_queries.append(query)
            return [SearchHit("https://blog.example.com/best", "Best tools", self.article)]
        self.tool_queries.append(query)
        if self.tool_hits is not None:
            return self.tool_hits
        name = query.split(" ", 1)[0]
        slug = name.lower()
        return [SearchHit(f"https://{slug}.dev/docs", name, f"{name} docs")]


class FakeScraper:
    def __init__(self):
        self.requested: list[str] = []

    async def fetch_many(self, urls):
        self.requested.extend(urls)
        return [Page(url=url, title="Page", text="Page body text") for url in urls]
