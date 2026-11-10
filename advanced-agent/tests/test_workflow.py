import pytest

from src.github import RepoFacts
from src.models import CompanyInfo, PricingModel
from src.search_providers import SearchHit
from src.workflow import Workflow, is_grounded, is_readable, matches_pricing, official_score
from tests.conftest import FakeLLM, FakeScraper, FakeSearch, analysis


def build(settings, llm=None, search=None) -> tuple[Workflow, FakeLLM]:
    llm = llm or FakeLLM()
    return Workflow(settings, llm, search or FakeSearch(), FakeScraper()), llm


async def test_returns_researched_tools_and_recommendation(settings):
    workflow, _ = build(settings)
    result = await workflow.run("react state")
    assert [c.name for c in result.companies] == ["Redux", "Zustand"]
    assert result.status == "success"
    assert result.analysis == "Pick **Redux**."
    assert "https://redux.dev/docs" in result.companies[0].sources


async def test_tool_searches_include_the_users_query_for_context(settings):
    search = FakeSearch()
    workflow, _ = build(settings, search=search)
    await workflow.run("react state")
    assert "Redux react state official site pricing" in search.tool_queries


async def test_drops_tools_not_named_in_the_sources(settings):
    workflow, _ = build(settings, FakeLLM(tools=["Redux", "Zustand Pro"]))
    result = await workflow.run("react state")
    assert [c.name for c in result.companies] == ["Redux"]


async def test_no_search_results_is_reported_without_calling_the_llm(settings):
    workflow, llm = build(settings, search=FakeSearch(article=None))
    result = await workflow.run("react state")
    assert result.status == "no_results"
    assert result.companies == []
    assert llm.calls == []


async def test_website_is_never_invented(settings):
    hits = [SearchHit("https://www.reddit.com/r/reactjs", "Thread", "About Redux")]
    workflow, _ = build(settings, search=FakeSearch(tool_hits=hits))
    result = await workflow.run("react state")
    assert all(company.website is None for company in result.companies)


async def test_rejects_llm_website_from_an_unseen_domain(settings):
    llm = FakeLLM(analyses={"Redux": analysis(website="https://evil.example.com")})
    workflow, _ = build(settings, llm)
    result = await workflow.run("react state")
    assert result.companies[0].website == "https://redux.dev"


async def test_accepts_llm_website_from_a_retrieved_domain(settings):
    llm = FakeLLM(analyses={"Redux": analysis(website="https://redux.dev/introduction")})
    workflow, _ = build(settings, llm)
    result = await workflow.run("react state")
    assert result.companies[0].website == "https://redux.dev/introduction"


async def test_tool_analysis_sees_the_users_search(settings):
    workflow, llm = build(settings)
    await workflow.run("rust web frameworks")
    analysis_prompts = [p for p in llm.prompts if p.startswith("Tool: Redux")]
    assert analysis_prompts[0].startswith("Tool: Redux\nSearch: rust web frameworks\n")


async def test_drops_a_tool_whose_sources_describe_a_different_product(settings):
    other_product = analysis(describes_requested_tool=False)
    workflow, _ = build(settings, FakeLLM(analyses={"Zustand": other_product}))
    result = await workflow.run("react state")
    assert [c.name for c in result.companies] == ["Redux"]
    assert result.unresearched == ["Zustand"]
    assert result.status == "partial"


async def test_relevant_sources_are_matched_even_with_brackets(settings):
    llm = FakeLLM(analyses={"Redux": analysis(relevant_sources=["[https://redux.dev/docs]"])})
    workflow, _ = build(settings, llm)
    result = await workflow.run("react state")
    redux = next(c for c in result.companies if c.name == "Redux")
    assert redux.website == "https://redux.dev"
    assert "https://redux.dev/docs" in redux.sources


class RecordingGitHub:
    def __init__(self):
        self.urls: list[str] = []

    async def facts_for(self, name, urls):
        self.urls.extend(urls)
        return None


async def test_same_named_product_sources_supply_no_links_or_facts(settings):
    terminal = "https://www.warp.dev"
    framework = "https://docs.rs/warp/latest/warp/"
    hits = [SearchHit(terminal, "Warp terminal", "AI terminal"), SearchHit(framework, "warp", "")]
    llm = FakeLLM(
        tools=["Warp"],
        analyses={
            "Warp": analysis(
                relevant_sources=[framework],
                website=terminal,
                description="A Rust web framework.",
            )
        },
    )
    github = RecordingGitHub()
    workflow = Workflow(
        settings,
        llm,
        FakeSearch(article="Warp is popular.", tool_hits=hits),
        FakeScraper(),
        github=github,
    )
    result = await workflow.run("rust web frameworks")
    warp = result.companies[0]
    assert warp.website != terminal
    assert all("warp.dev" not in url for url in warp.sources)
    assert github.urls
    assert all("warp.dev" not in url for url in github.urls)


async def test_one_failing_tool_gives_a_partial_result(settings):
    llm = FakeLLM()
    llm.fail_for.add("Zustand")
    workflow, _ = build(settings, llm)
    result = await workflow.run("react state")
    assert result.status == "partial"
    assert [c.name for c in result.companies] == ["Redux"]
    assert result.unresearched == ["Zustand"]


async def test_timeout_keeps_tools_that_already_finished(settings):
    settings.research_timeout = 0.2
    llm = FakeLLM()
    llm.delay_for.add("Zustand")
    workflow, _ = build(settings, llm)
    result = await workflow.run("react state")
    assert result.status == "partial"
    assert [c.name for c in result.companies] == ["Redux"]
    assert result.unresearched == ["Zustand"]
    assert result.analysis == "Pick **Redux**."


async def test_all_tools_failing_is_no_results(settings):
    llm = FakeLLM()
    llm.fail_for.update({"Redux", "Zustand"})
    workflow, _ = build(settings, llm)
    result = await workflow.run("react state")
    assert result.status == "no_results"
    assert result.analysis is None


async def test_recommendation_failure_keeps_the_tools(settings):
    llm = FakeLLM()
    llm.fail_text = True
    workflow, _ = build(settings, llm)
    result = await workflow.run("react state")
    assert len(result.companies) == 2
    assert result.analysis is None


async def test_applies_the_pricing_preference_from_the_llm(settings):
    paid = analysis(pricing_model=PricingModel.PAID, is_open_source=False)
    llm = FakeLLM(preference="free", analyses={"Zustand": paid})
    workflow, _ = build(settings, llm)
    result = await workflow.run("free react state")
    assert [c.name for c in result.companies] == ["Redux"]
    assert result.pricing_preference == "free"


async def test_keeps_all_tools_if_none_match_the_preference(settings):
    paid = analysis(pricing_model=PricingModel.PAID, is_open_source=False)
    llm = FakeLLM(preference="free", analyses={"Redux": paid, "Zustand": paid})
    workflow, _ = build(settings, llm)
    result = await workflow.run("free react state")
    assert len(result.companies) == 2


async def test_stream_reports_rising_progress_then_one_result(settings):
    workflow, _ = build(settings)
    events = [event async for event in workflow.stream("react state")]
    percents = [event["percent"] for event in events if event["type"] == "progress"]
    assert percents == sorted(percents)
    assert percents[0] < percents[-1]
    assert [event["type"] for event in events].count("result") == 1
    assert events[-1]["type"] == "result"


async def test_full_results_are_cached_case_insensitively(settings):
    workflow, llm = build(settings)
    await workflow.run("React State")
    calls = len(llm.calls)
    await workflow.run("react state")
    assert len(llm.calls) == calls


async def test_partial_results_are_not_cached(settings):
    llm = FakeLLM()
    llm.fail_for.add("Zustand")
    workflow, _ = build(settings, llm)
    await workflow.run("react state")
    calls = len(llm.calls)
    await workflow.run("react state")
    assert len(llm.calls) > calls


async def test_stream_emits_each_tool_as_it_finishes(settings):
    workflow, _ = build(settings)
    events = [event async for event in workflow.stream("react state")]
    finished = [event["company"]["name"] for event in events if event["type"] == "tool"]
    assert sorted(finished) == ["Redux", "Zustand"]


async def test_searches_again_when_too_few_tools_are_found(settings):
    search = FakeSearch()
    workflow, _ = build(settings, FakeLLM(tools=["Redux"]), search)
    await workflow.run("react state")
    assert search.discovery_queries == ["best react state", "react state top alternatives list"]


async def test_does_not_search_again_with_enough_tools(settings):
    search = FakeSearch(article="Redux Zustand MobX are popular.")
    workflow, _ = build(settings, FakeLLM(tools=["Redux", "Zustand", "MobX"]), search)
    await workflow.run("react state")
    assert search.discovery_queries == ["best react state"]


async def test_skips_sites_that_block_scraping(settings):
    hits = [
        SearchHit("https://www.reddit.com/r/reactjs", "Thread", "About Redux"),
        SearchHit("https://redux.dev/docs", "Docs", "Redux docs"),
    ]
    scraper = FakeScraper()
    workflow = Workflow(settings, FakeLLM(), FakeSearch(tool_hits=hits), scraper)
    await workflow.run("react state")
    assert not any("reddit.com" in url for url in scraper.requested)
    assert "https://redux.dev/docs" in scraper.requested


async def test_reads_the_official_pricing_page(settings):
    scraper = FakeScraper()
    workflow = Workflow(settings, FakeLLM(), FakeSearch(), scraper)
    await workflow.run("react state")
    assert "https://redux.dev/pricing" in scraper.requested


class FakeGitHub:
    async def facts_for(self, name, urls):
        if name != "Redux":
            return None
        return RepoFacts(
            url="https://github.com/reduxjs/redux",
            stars=61000,
            license="MIT",
            is_open_source=True,
            last_commit="2026-10-01",
            maintenance="active",
            homepage="https://redux.js.org",
        )


async def test_github_facts_override_extracted_unknowns(settings):
    unknown = analysis(pricing_model=PricingModel.UNKNOWN, is_open_source=None)
    hits = [SearchHit("https://blog.example.com/redux", "Post", "About Redux")]
    workflow = Workflow(
        settings,
        FakeLLM(analyses={"Redux": unknown}),
        FakeSearch(tool_hits=hits),
        FakeScraper(),
        github=FakeGitHub(),
    )
    result = await workflow.run("react state")
    redux = next(c for c in result.companies if c.name == "Redux")
    assert redux.is_open_source is True
    assert redux.pricing_model is PricingModel.FREE
    assert redux.license == "MIT"
    assert redux.github_stars == 61000
    assert redux.maintenance == "active"
    assert redux.website == "https://redux.js.org"
    assert "https://github.com/reduxjs/redux" in redux.sources


async def test_github_facts_do_not_override_known_pricing(settings):
    paid = analysis(pricing_model=PricingModel.FREEMIUM)
    workflow = Workflow(
        settings,
        FakeLLM(analyses={"Redux": paid}),
        FakeSearch(),
        FakeScraper(),
        github=FakeGitHub(),
    )
    result = await workflow.run("react state")
    assert next(c for c in result.companies if c.name == "Redux").pricing_model.value == "Freemium"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.reddit.com/r/x", False),
        ("https://m.facebook.com/x", False),
        ("https://netflix.com/x", True),
        ("https://redux.js.org", True),
    ],
)
def test_is_readable(url, expected):
    assert is_readable(url) is expected


@pytest.mark.parametrize(
    ("name", "text", "expected"),
    [
        ("Redux", "we use redux here", True),
        ("Vue.js", "vue is great", True),
        ("C++", "a c++ library", True),
        ("Bun", "a bundler", False),
        ("Zustand Pro", "zustand is free", False),
    ],
)
def test_is_grounded(name, text, expected):
    assert is_grounded(name, text) is expected


@pytest.mark.parametrize(
    ("name", "url", "expected"),
    [
        ("Argo CD", "https://argo-cd.readthedocs.io/en/stable", 3),
        ("Redux", "https://github.com/reduxjs/redux", 2),
        ("Redux", "https://en.wikipedia.org/wiki/Redux", -1),
        ("Redux", "https://example.com/a", 0),
        ("Flask", "https://www.hydroflask.com", 0),
        ("Flask", "https://flask.palletsprojects.com/en/stable/", 3),
    ],
)
def test_official_score(name, url, expected):
    assert official_score(name, url) == expected


@pytest.mark.parametrize(
    ("pricing", "open_source", "preference", "expected"),
    [
        (PricingModel.FREE, None, "free", True),
        (PricingModel.FREEMIUM, False, "free", True),
        (PricingModel.PAID, True, "free", True),
        (PricingModel.PAID, False, "free", False),
        (PricingModel.FREEMIUM, False, "paid", True),
        (PricingModel.FREE, True, "paid", False),
        (PricingModel.UNKNOWN, None, "paid", True),
        (PricingModel.PAID, False, "any", True),
    ],
)
def test_matches_pricing(pricing, open_source, preference, expected):
    company = CompanyInfo(
        name="X", description="d", pricing_model=pricing, is_open_source=open_source
    )
    assert matches_pricing(company, preference) is expected
