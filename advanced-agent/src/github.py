"""Verified facts about open-source tools from the GitHub API."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from .logger import get_logger

logger = get_logger("github")

_API = "https://api.github.com"
_MIN_STARS = 500
_ACTIVE_DAYS = 180
_STALE_DAYS = 730
_MAX_CACHED = 512
_OPEN_SOURCE_LICENSES = {
    "0BSD",
    "AGPL-3.0",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "BSL-1.0",
    "EPL-1.0",
    "EPL-2.0",
    "GPL-2.0",
    "GPL-3.0",
    "ISC",
    "LGPL-2.1",
    "LGPL-3.0",
    "MIT",
    "MPL-2.0",
    "PostgreSQL",
    "Unlicense",
    "Zlib",
}
_SHARED_HOSTS = {
    "github.io",
    "gitlab.io",
    "herokuapp.com",
    "netlify.app",
    "pages.dev",
    "readthedocs.io",
    "vercel.app",
}
_NON_REPO_PATHS = {
    "about",
    "collections",
    "customer-stories",
    "enterprise",
    "explore",
    "features",
    "login",
    "marketplace",
    "orgs",
    "pricing",
    "resources",
    "security",
    "settings",
    "signup",
    "solutions",
    "sponsors",
    "topics",
    "trending",
}


@dataclass(frozen=True)
class RepoFacts:
    url: str
    stars: int
    license: str | None
    is_open_source: bool
    last_commit: str | None
    maintenance: str | None
    homepage: str | None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def maintenance_status(pushed_at: datetime, archived: bool, now: datetime) -> str:
    if archived:
        return "archived"
    age = (now - pushed_at).days
    if age <= _ACTIVE_DAYS:
        return "active"
    return "slowing" if age <= _STALE_DAYS else "stale"


def repo_path(url: str) -> str | None:
    """Return "owner/repo" for a GitHub repository URL, or None for anything else."""
    parts = urlparse(url)
    if parts.netloc.lower().removeprefix("www.") != "github.com":
        return None
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) < 2 or segments[0].lower() in _NON_REPO_PATHS:
        return None
    return f"{segments[0]}/{segments[1].removesuffix('.git')}"


def names_match(tool: str, full_name: str) -> bool:
    """Require an exact name match, so a repository is never credited to the wrong tool."""
    owner, _, repo = full_name.partition("/")
    slug = _slug(tool)
    return bool(slug) and slug in {_slug(repo), _slug(owner + repo)} or (
        tool.lower().endswith(".js") and _slug(tool[:-3]) == _slug(repo)
    )


def site_of(url: str) -> str:
    """The registrable part of a URL's host, keeping one more label on shared hosting domains."""
    labels = urlparse(url).netloc.lower().removeprefix("www.").split(".")
    keep = 3 if ".".join(labels[-2:]) in _SHARED_HOSTS else 2
    return ".".join(labels[-keep:])


def belongs_to_tool(tool: str, data: dict[str, Any], urls: list[str]) -> bool:
    """A matching name isn't proof of ownership: anyone can create a repository called "Pinecone".

    Accept a repository when its account is named after the tool (django/django, jestjs/jest,
    aws/aws-cdk), or when its listed homepage is on a site that came up for the tool.
    """
    owner = _slug(data["full_name"].partition("/")[0])
    slug = _slug(tool)
    if len(owner) >= 3 and (owner.startswith(slug) or slug.startswith(owner)):
        return True
    homepage = data.get("homepage") or ""
    if not homepage.startswith(("http://", "https://")):
        return False
    sites = {site_of(url) for url in urls if site_of(url) != "github.com"}
    return site_of(homepage) in sites


def parse_repo(data: dict[str, Any], now: datetime | None = None) -> RepoFacts:
    now = now or datetime.now(UTC)
    license_id = (data.get("license") or {}).get("spdx_id")
    if license_id == "NOASSERTION":
        license_id = None
    pushed = data.get("pushed_at")
    pushed_at = datetime.fromisoformat(pushed.replace("Z", "+00:00")) if pushed else None
    homepage = data.get("homepage") or None
    if homepage and not homepage.startswith(("http://", "https://")):
        homepage = None
    return RepoFacts(
        url=data["html_url"],
        stars=data.get("stargazers_count", 0),
        license=license_id,
        is_open_source=license_id in _OPEN_SOURCE_LICENSES,
        last_commit=pushed_at.date().isoformat() if pushed_at else None,
        maintenance=(
            maintenance_status(pushed_at, bool(data.get("archived")), now) if pushed_at else None
        ),
        homepage=homepage,
    )


class GitHubFacts:
    def __init__(self, client: httpx.AsyncClient, token: str | None = None):
        self.client = client
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self._cache: dict[str, RepoFacts | None] = {}

    async def facts_for(self, name: str, urls: list[str]) -> RepoFacts | None:
        """Find a tool's repository from known URLs or an exact-name search."""
        key = _slug(name)
        if key in self._cache:
            return self._cache[key]
        paths = [path for path in map(repo_path, urls) if path and names_match(name, path)]
        data = await self._get(f"/repos/{paths[0]}") if paths else await self._search(name, urls)
        facts = parse_repo(data) if data and belongs_to_tool(name, data, urls) else None
        if len(self._cache) >= _MAX_CACHED:
            self._cache.clear()
        self._cache[key] = facts
        return facts

    async def _search(self, name: str, urls: list[str]) -> dict[str, Any] | None:
        result = await self._get(
            "/search/repositories",
            {"q": f"{name} in:name", "sort": "stars", "per_page": 10},
        )
        for item in (result or {}).get("items", []):
            if (
                item.get("stargazers_count", 0) >= _MIN_STARS
                and names_match(name, item["full_name"])
                and belongs_to_tool(name, item, urls)
            ):
                return item
        return None

    async def _get(self, path: str, params: dict | None = None) -> dict[str, Any] | None:
        try:
            response = await self.client.get(f"{_API}{path}", params=params, headers=self.headers)
        except httpx.HTTPError as exc:
            logger.info("GitHub request failed: %s", type(exc).__name__)
            return None
        if response.status_code != 200:
            logger.info("GitHub returned HTTP %s", response.status_code)
            return None
        return response.json()
