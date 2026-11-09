import pytest

from src.models import CompanyInfo, PricingModel
from src.search_providers import SearchHit
from src.workflow import Workflow, is_grounded, matches_pricing, official_score
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
    assert result.companies[0].sources == ["https://redux.dev/docs"]


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
