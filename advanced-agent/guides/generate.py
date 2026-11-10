"""Generate static guide pages for popular searches. This spends real API credits.

Usage, from advanced-agent/:  python -m guides.generate [--limit N]
Writes HTML into react-frontend/public/guides, plus a sitemap. Commit the output to publish it.
"""

import argparse
import asyncio
import re
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from urllib.parse import quote_plus

from src.config import get_settings
from src.models import CompanyInfo, ResearchResult
from src.net import create_client
from src.workflow import create_workflow

SITE = "https://www.toolscraper.dev"
PUBLIC_DIR = Path(__file__).resolve().parents[2] / "react-frontend" / "public"
TOPICS = [
    "Python web frameworks",
    "JavaScript testing frameworks",
    "React state management libraries",
    "Vue component libraries",
    "Python ORM libraries",
    "CI/CD platforms",
    "Error monitoring tools",
    "API gateways",
    "Vector databases",
    "Headless CMS platforms",
    "Infrastructure as code tools",
    "Open source observability tools",
]
STYLE = """
:root{color-scheme:light dark;--bg:#f8fafc;--card:#fff;--text:#1e293b;--muted:#64748b;
--line:#e2e8f0;--link:#2563eb}
@media(prefers-color-scheme:dark){:root{--bg:#0f172a;--card:#1e293b;--text:#f1f5f9;
--muted:#94a3b8;--line:#334155;--link:#60a5fa}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);line-height:1.6;
font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:860px;margin:0 auto;padding:2.5rem 1rem 4rem}
nav a,a{color:var(--link)}
h1{font-size:2.25rem;line-height:1.2;margin:1rem 0 .5rem}
.meta{color:var(--muted);margin:0 0 1.5rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:1.25rem;margin:1rem 0}
.card h2{font-size:1.2rem;margin:0 0 .25rem}
.facts{color:var(--muted);font-size:.9rem;margin:.5rem 0 0}
.cta{display:inline-block;margin-top:1.5rem;font-weight:600}
ul.topics{padding-left:1.25rem}
"""


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("++", "pp")).strip("-")


def safe_link(url: str | None, label: str) -> str:
    if not url or not url.startswith(("http://", "https://")):
        return ""
    return f'<a href="{escape(url, quote=True)}" rel="noopener nofollow">{escape(label)}</a>'


def format_inline(text: str) -> str:
    """Escape model text, then apply its one permitted format: **bold**."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(text))


def page(title: str, description: str, path: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | Tool Scraper</title>
<meta name="description" content="{escape(description, quote=True)}">
<link rel="canonical" href="{SITE}{path}">
<link rel="icon" type="image/svg+xml" href="/logo.svg">
<style>{STYLE}</style>
</head>
<body><main>
<nav><a href="/">Tool Scraper</a> / <a href="/guides/">Guides</a></nav>
{body}
</main></body>
</html>
"""


def tool_card(tool: CompanyInfo) -> str:
    facts = []
    if tool.pricing_model.value != "Unknown":
        facts.append(tool.pricing_model.value)
    if tool.license:
        facts.append(tool.license)
    elif tool.is_open_source:
        facts.append("Open source")
    if tool.github_stars is not None:
        facts.append(f"{tool.github_stars:,} GitHub stars")
    if tool.last_commit:
        facts.append(f"updated {tool.last_commit}")
    links = [safe_link(tool.website, "Website"), safe_link(tool.github_url, "GitHub")]
    links += [safe_link(url, f"Source {i}") for i, url in enumerate(tool.sources[:3], 1)]
    return (
        f'<section class="card"><h2>{escape(tool.name)}</h2>'
        f"<p>{escape(tool.description)}</p>"
        f'<p class="facts">{escape(" · ".join(facts))}</p>'
        f'<p class="facts">{" · ".join(link for link in links if link)}</p></section>'
    )


def render_guide(topic: str, result: ResearchResult, researched: str) -> str:
    title = f"Best {topic}"
    names = ", ".join(tool.name for tool in result.companies[:4])
    description = f"A sourced comparison of {topic.lower()}, including {names}."
    summary = f"<p>{format_inline(result.analysis)}</p>" if result.analysis else ""
    cards = "".join(tool_card(tool) for tool in result.companies)
    body = (
        f"<h1>{escape(title)}</h1>"
        f'<p class="meta">Researched from live sources on {escape(researched)}.</p>'
        f"{summary}{cards}"
        f'<a class="cta" href="/?q={quote_plus(topic)}">Run a fresh search</a>'
    )
    return page(title, description, f"/guides/{slugify(topic)}/", body)


def render_index(topics: list[str]) -> str:
    items = "".join(
        f'<li><a href="/guides/{slugify(topic)}/">Best {escape(topic)}</a></li>'
        for topic in topics
    )
    body = (
        "<h1>Developer Tool Guides</h1>"
        '<p class="meta">Sourced comparisons of popular developer tool categories.</p>'
        f'<ul class="topics">{items}</ul>'
    )
    description = "Sourced comparisons of popular developer tool categories."
    return page("Developer Tool Guides", description, "/guides/", body)


def render_sitemap(topics: list[str]) -> str:
    paths = ["/", "/guides/", *(f"/guides/{slugify(topic)}/" for topic in topics)]
    urls = "".join(f"<url><loc>{SITE}{path}</loc></url>" for path in paths)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'
    )


async def main(limit: int | None, delay: float) -> None:
    settings = get_settings()
    researched = datetime.now(UTC).date().isoformat()
    published: list[str] = []
    async with create_client(settings) as client:
        workflow = create_workflow(settings, client)
        for index, topic in enumerate(TOPICS[:limit]):
            if index:
                await asyncio.sleep(delay)
            result = await workflow.run(topic)
            if not result.companies:
                print(f"SKIP {topic}: {result.status}")
                continue
            folder = PUBLIC_DIR / "guides" / slugify(topic)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "index.html").write_text(
                render_guide(topic, result, researched), encoding="utf-8"
            )
            published.append(topic)
            print(f"OK   {topic}: {len(result.companies)} tools")
            for tool in result.companies:
                print(f"       {tool.name} -> {tool.github_url or 'no repository'}")
    guides = PUBLIC_DIR / "guides"
    guides.mkdir(parents=True, exist_ok=True)
    (guides / "index.html").write_text(render_index(published), encoding="utf-8")
    (PUBLIC_DIR / "sitemap.xml").write_text(render_sitemap(published), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--delay", type=float, default=0, help="seconds between topics, for GitHub's API limit"
    )
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.delay))
