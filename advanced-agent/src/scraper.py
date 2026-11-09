import asyncio
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from .config import Settings
from .logger import get_logger

logger = get_logger("scraper")

_NOISE_TAGS = ["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"]
_TEXT_TYPES = ("text/html", "application/xhtml", "text/plain")


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    text: str


def extract_text(html: str, max_chars: int) -> tuple[str, str]:
    """Return (title, main readable text) for an HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": "description"})
    description = str(meta.get("content", "")).strip() if meta else ""
    for tag in soup(_NOISE_TAGS):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    body = " ".join(root.get_text(" ", strip=True).split())
    return title, f"{description} {body}".strip()[:max_chars]


class Scraper:
    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings

    async def fetch(self, url: str) -> Page | None:
        """Fetch one page as readable text, or return None if it is unusable."""
        try:
            raw = await self._download(url)
        except httpx.HTTPError as exc:
            logger.info("Could not fetch %s: %s", url, type(exc).__name__)
            return None
        if raw is None:
            return None
        title, text = await asyncio.to_thread(extract_text, raw, self.settings.max_page_chars)
        if len(text) < self.settings.min_page_chars:
            return None
        return Page(url=url, title=title, text=text)

    async def fetch_many(self, urls: list[str]) -> list[Page]:
        pages = await asyncio.gather(*(self.fetch(url) for url in urls))
        return [page for page in pages if page]

    async def _download(self, url: str) -> str | None:
        async with self.client.stream("GET", url) as response:
            if response.status_code != 200:
                return None
            content_type = response.headers.get("content-type", "").lower()
            if not content_type.startswith(_TEXT_TYPES):
                return None
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= self.settings.max_page_bytes:
                    break
            encoding = response.charset_encoding or "utf-8"
        return b"".join(chunks).decode(encoding, errors="replace")
