from guides.generate import render_guide, render_index, render_sitemap, slugify
from src.models import CompanyInfo, ResearchResult


def result(**tool_overrides) -> ResearchResult:
    tool = CompanyInfo(name="Redux", description="A state container.", **tool_overrides)
    return ResearchResult(query="q", companies=[tool], analysis="Pick **Redux**.")


def test_slugify():
    assert slugify("CI/CD platforms") == "ci-cd-platforms"
    assert slugify("C++ libraries") == "cpp-libraries"


def test_guide_contains_the_research_and_a_fresh_search_link():
    html = render_guide("React state tools", result(website="https://redux.js.org"), "2026-11-10")
    assert "Best React state tools" in html
    assert "<strong>Redux</strong>" in html
    assert 'href="https://redux.js.org"' in html
    assert 'href="/?q=React+state+tools"' in html
    assert "2026-11-10" in html
    assert 'rel="canonical" href="https://www.toolscraper.dev/guides/react-state-tools/"' in html


def test_guide_escapes_scraped_text_and_rejects_unsafe_links():
    malicious = ResearchResult(
        query="q",
        companies=[
            CompanyInfo(
                name="<script>alert(1)</script>",
                description="<img src=x onerror=alert(1)>",
                website="javascript:alert(1)",
            )
        ],
        analysis="**<b>bold</b>**",
    )
    html = render_guide("Tools", malicious, "2026-11-10")
    assert "<script>alert" not in html
    assert "<img src=x" not in html
    assert "javascript:alert" not in html
    assert "<b>bold</b>" not in html


def test_guide_hides_unknown_pricing():
    assert "Unknown" not in render_guide("Tools", result(), "2026-11-10")


def test_index_and_sitemap_list_published_guides():
    assert '/guides/python-orms/' in render_index(["Python ORMs"])
    sitemap = render_sitemap(["Python ORMs"])
    assert "<loc>https://www.toolscraper.dev/guides/python-orms/</loc>" in sitemap
    assert "<loc>https://www.toolscraper.dev/</loc>" in sitemap
