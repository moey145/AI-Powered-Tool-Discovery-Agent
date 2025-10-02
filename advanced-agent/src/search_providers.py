from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import random
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from .config import settings
from .logger import get_logger

logger = get_logger('search_providers')

class SearchProvider(ABC):
    """Abstract base class for search providers"""
    
    @abstractmethod
    async def search(self, query: str, num_results: int) -> Dict[str, Any]:
        """Search for results and return standardized format"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available (has API key)"""
        pass

    async def close(self):
        """Optional async cleanup"""
        return

class GoogleCustomSearchProvider(SearchProvider):
    """Google Custom Search JSON API provider"""
    
    def __init__(self):
        self.api_key = settings.google_custom_search_api_key
        self.search_engine_id = settings.google_search_engine_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.timeout = aiohttp.ClientTimeout(total=getattr(settings, 'google_custom_search_timeout', 15))
        # Session reuse and simple TTL cache
        self._cache: Dict[Tuple[str, int], Tuple[float, Dict[str, Any]]] = {}
        self._cache_ttl_seconds: int = 120
        self._max_retries: int = getattr(settings, 'max_retries', 3)

    async def close(self):
        """No-op for interface compatibility."""
        return
    
    def is_available(self) -> bool:
        return bool(self.api_key) and bool(self.search_engine_id)
    
    async def search(self, query: str, num_results: int) -> Dict[str, Any]:
        """Search using Google Custom Search API"""
        if not self.is_available():
            logger.warning("⚠️ Google Custom Search API key or Search Engine ID not set")
            return {"data": []}

        # Normalize inputs
        eff_results = min(max(1, num_results), getattr(settings, 'max_search_results', num_results))

        # Cache key and lookup
        cache_key = (query, eff_results)
        now = asyncio.get_event_loop().time()
        cached = self._cache.get(cache_key)
        if cached and cached[0] < now:
            self._cache.pop(cache_key, None)
        elif cached and cached[0] >= now:
            return cached[1]

        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": min(eff_results, 10),  # Google API max is 10 per request
            "safe": "active",
            "fields": "items(title,link,snippet,pagemap)"
        }

        # Retry with exponential backoff + jitter
        for attempt in range(self._max_retries):
            connector = aiohttp.TCPConnector(
                limit=5,
                limit_per_host=3,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            session_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            }
            try:
                async with aiohttp.ClientSession(timeout=self.timeout, connector=connector, connector_owner=True, headers=session_headers) as session:
                    async with session.get(self.base_url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            results = self._parse_google_results(data, eff_results)
                            # Normalize and apply early domain cap
                            results = self._normalize_and_cap(results, eff_results)
                            out = {"data": results}
                            # Store in cache
                            self._cache[cache_key] = (now + self._cache_ttl_seconds, out)
                            logger.info(f"✅ Google Custom Search successful: {len(results)} results")
                            return out
                        elif response.status in (429, 500, 502, 503, 504):
                            backoff = min(8, 2 ** attempt)
                            jitter = random.uniform(0.2, 0.8)
                            wait_s = backoff + jitter
                            logger.warning(f"⚠️ Google API {response.status}; retrying in {wait_s:.1f}s")
                            await asyncio.sleep(wait_s)
                            continue
                        else:
                            error_text = await response.text()
                            logger.error(f"❌ Google Custom Search API error {response.status}: {error_text}")
                            break
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Google Custom Search timeout (attempt {attempt+1})")
                continue
            except asyncio.CancelledError:
                logger.warning(f"⚠️ Google Custom Search cancelled (attempt {attempt+1})")
                break  # Don't retry on cancellation
            except RuntimeError as e:
                # Session bound to a different/closed loop or connector closed – recreate and retry
                error_str = str(e).lower()
                if any(err in error_str for err in ['event loop is closed', 'attached to a different loop', 'connector is closed']):
                    logger.warning(f"⚠️ Google Custom Search session error: {e}")
                    # Longer backoff for connector issues
                    backoff = min(8, 2 ** attempt)
                    await asyncio.sleep(backoff)
                    # Recreate session next iteration
                    continue
            except Exception as e:
                logger.error(f"❌ Google Custom Search error (attempt {attempt+1}): {e}")
                continue
 
        return {"data": []}
    
    def _parse_google_results(self, data: Dict[str, Any], num_results: int) -> List[Dict[str, Any]]:
        """Parse Google Custom Search API response into standardized format"""
        results = []
        
        try:
            # Google returns results in 'items' field
            google_results = data.get("items", [])
            
            for item in google_results[:num_results]:
                # Extract URL and title
                url = item.get("link", "")
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                
                if not url or not isinstance(url, str):
                    continue
                
                # Filter out unwanted content types
                if self._should_skip_url(url):
                    continue
                
                # Extract additional metadata from pagemap if available
                pagemap = item.get("pagemap", {})
                metadata = {
                    "source": "google_custom_search",
                    "display_link": item.get("displayLink", ""),
                    "formatted_url": item.get("formattedUrl", ""),
                    "html_title": pagemap.get("metatags", [{}])[0].get("og:title", "") if pagemap.get("metatags") else "",
                    "html_description": pagemap.get("metatags", [{}])[0].get("og:description", "") if pagemap.get("metatags") else ""
                }
                
                results.append({
                    "url": self._normalize_url(url),
                    "title": title[:200] if title else "",
                    "snippet": snippet[:300] if snippet else title[:300] if title else "",
                    "metadata": metadata
                })
                
                if len(results) >= num_results:
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error parsing Google Custom Search results: {e}")
        
        return results

    def _normalize_url(self, url: str) -> str:
        try:
            p = urlparse(url)
            # Strip common tracking params
            qs = [(k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True)
                  if not (k.lower().startswith('utm_') or k.lower() in {'gclid', 'fbclid', 'mc_cid', 'mc_eid'})]
            new_query = urlencode(qs)
            # Remove fragments
            return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, ''))
        except Exception:
            return url

    def _normalize_and_cap(self, results: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        # Early domain diversity cap (max 2 per domain)
        capped: List[Dict[str, Any]] = []
        domain_counts: Dict[str, int] = {}
        for r in results:
            try:
                dom = urlparse(r.get('url', '')).netloc.lower()
            except Exception:
                dom = ''
            if dom:
                cnt = domain_counts.get(dom, 0)
                if cnt >= 2:
                    continue
                domain_counts[dom] = cnt + 1
            capped.append(r)
            if len(capped) >= limit:
                break
        return capped
    
    def _should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped based on content type"""
        try:
            from urllib.parse import urlparse
            path = urlparse(url).path.lower()
            
            # Skip binary/download files
            bad_exts = ('.pdf', '.zip', '.rar', '.7z', '.dmg', '.exe')
            if path.endswith(bad_exts):
                return True
            
            # Skip download paths
            if '/_/downloads/' in path:
                return True
                
            return False
            
        except Exception:
            return False

class DuckDuckGoSearchProvider(SearchProvider):
    """DuckDuckGo HTML search (no API key required)."""

    def __init__(self):
        # Use the HTML endpoint optimized for simple scraping
        self.base_url = "https://html.duckduckgo.com/html/"
        self.timeout = aiohttp.ClientTimeout(total=getattr(settings, 'google_custom_search_timeout', 15))
        self._cache: Dict[Tuple[str, int], Tuple[float, Dict[str, Any]]] = {}
        self._cache_ttl_seconds: int = 120
        self._max_retries: int = getattr(settings, 'max_retries', 3)
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_connector: Optional[aiohttp.TCPConnector] = None
        self._session_cache_key: Optional[Tuple[str, int]] = None
        self._session_loop: Optional[asyncio.AbstractEventLoop] = None

    async def close(self):
        """Ensure any cached session/connector are closed."""
        session = getattr(self, "_session", None)
        connector = getattr(self, "_session_connector", None)
        try:
            if session and not session.closed:
                await session.close()
        except Exception:
            pass
        try:
            if connector:
                await connector.close()
        except Exception:
            pass
        self._session = None
        self._session_connector = None
        self._session_cache_key = None
        self._session_loop = None
        self._session_loop = None

    def is_available(self) -> bool:
        # Always available (no key required)
        return True

    async def search(self, query: str, num_results: int) -> Dict[str, Any]:
        eff_results = min(max(1, num_results), getattr(settings, 'max_search_results', num_results))
        params = {"q": query, "kl": "us-en"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Cache
        cache_key = (query, eff_results)
        now = asyncio.get_event_loop().time()
        cached = self._cache.get(cache_key)
        if cached and cached[0] < now:
            self._cache.pop(cache_key, None)
        elif cached and cached[0] >= now:
            return cached[1]

        session_cache_key = getattr(self, "_session_cache_key", None)
        session_loop = getattr(self, "_session_loop", None)
        current_loop = asyncio.get_running_loop()
        cache_key_changed = session_cache_key != cache_key
        loop_changed = session_loop is not current_loop

        def build_connector():
            return aiohttp.TCPConnector(
                limit=5,
                limit_per_host=3,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )

        async def ensure_cached_session() -> aiohttp.ClientSession:
            session = self._session
            connector = self._session_connector
            if session is None or session.closed or cache_key_changed or loop_changed:
                if session and not session.closed:
                    try:
                        await session.close()
                    except Exception:
                        pass
                if connector:
                    try:
                        await connector.close()
                    except Exception:
                        pass
                new_connector = build_connector()
                self._session = aiohttp.ClientSession(
                    timeout=self.timeout,
                    headers=headers,
                    connector=new_connector,
                    connector_owner=True
                )
                self._session_connector = new_connector
                self._session_cache_key = cache_key
                self._session_loop = current_loop
            return self._session

        # Retry with exponential backoff + jitter
        for attempt in range(self._max_retries):
            try:
                session = await ensure_cached_session()
                async with session.post(self.base_url, data=params) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        results = self._parse_duckduckgo_results(html, eff_results)
                        # Normalize and cap domain diversity
                        for r in results:
                            r["url"] = GoogleCustomSearchProvider._normalize_url(self, r.get("url", ""))
                        results = GoogleCustomSearchProvider._normalize_and_cap(self, results, eff_results)
                        out = {"data": results}
                        self._cache[cache_key] = (now + self._cache_ttl_seconds, out)
                        logger.info(f"✅ duckduckgo search successful: {len(results)} results")
                        return out
                    elif resp.status in (429, 500, 502, 503, 504):
                        backoff = min(8, 2 ** attempt)
                        jitter = random.uniform(0.2, 0.8)
                        wait_s = backoff + jitter
                        logger.warning(f"⚠️ DuckDuckGo HTTP {resp.status}; retrying in {wait_s:.1f}s")
                        await asyncio.sleep(wait_s)
                        continue
                    else:
                        err = await resp.text()
                        logger.error(f"❌ DuckDuckGo HTTP {resp.status}: {err[:200]}")
                        break
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ DuckDuckGo search timeout (attempt {attempt+1})")
                continue
            except asyncio.CancelledError:
                logger.warning(f"⚠️ DuckDuckGo search cancelled (attempt {attempt+1})")
                break  # Don't retry on cancellation
            except RuntimeError as e:
                error_str = str(e).lower()
                if any(err in error_str for err in ['event loop is closed', 'attached to a different loop', 'connector is closed']):
                    logger.warning(f"⚠️ DuckDuckGo session error: {e}")
                    # Longer backoff for connector issues
                    backoff = min(8, 2 ** attempt)
                    await asyncio.sleep(backoff)
                    continue
            except Exception as e:
                logger.error(f"❌ DuckDuckGo search error (attempt {attempt+1}): {e}")
                continue
 
        return {"data": []}

    def _parse_duckduckgo_results(self, html: str, num_results: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # DuckDuckGo HTML results use 'result__a' links within 'result' containers
            containers = soup.select('div.result')
            for c in containers:
                a = c.select_one('a.result__a')
                if not a or not a.get('href'):
                    continue
                url = a['href']
                # Skip DDG redirect or internal links
                if url.startswith('/y.js') or url.startswith('#'):
                    continue
                # Title and snippet
                title = a.get_text(strip=True)[:200]
                snippet_el = c.select_one('.result__snippet') or c.select_one('.result__desc')
                snippet = (snippet_el.get_text(" ", strip=True) if snippet_el else title)[:300]
                # Basic filter for non-http links
                if not url.startswith('http'):
                    try:
                        url = urljoin('https://duckduckgo.com/', url)
                    except Exception:
                        continue
                # Filter out obvious non-HTML downloads
                try:
                    path = urlparse(url).path.lower()
                except Exception:
                    path = ''
                if path.endswith(('.pdf', '.zip', '.rar', '.7z', '.dmg', '.exe')):
                    continue
                results.append({
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                    "metadata": {"source": "duckduckgo"}
                })
                if len(results) >= num_results:
                    break
        except Exception as e:
            logger.error(f"❌ Error parsing DuckDuckGo results: {e}")
        return results

class SearchManager:
    """Manages multiple search providers with fallback logic"""
    
    def __init__(self):
        self.providers = {
            "google_custom_search": GoogleCustomSearchProvider(),
            "duckduckgo": DuckDuckGoSearchProvider(),
        }
        self.provider_order = self._determine_provider_order()
    
    def _determine_provider_order(self) -> List[str]:
        """Determine the order of providers based on configuration and availability"""
        if settings.search_provider == "google_custom_search":
            return ["google_custom_search", "duckduckgo"]
        elif settings.search_provider == "duckduckgo":
            return ["duckduckgo", "google_custom_search"]
        else:  # "auto" - determine by availability
            available_providers: List[str] = []
            # Prefer Google Custom Search first if available
            if self.providers["google_custom_search"].is_available():
                available_providers.append("google_custom_search")
            # Always include DuckDuckGo as a fallback (no key required)
            available_providers.append("duckduckgo")
            return available_providers
    
    async def search(self, query: str, num_results: int) -> Dict[str, Any]:
        """Search using available providers with fallback"""
        if not self.provider_order:
            logger.error("❌ No search providers available")
            return {"data": []}
        
        # Try providers in order until one succeeds
        for provider_name in self.provider_order:
            provider = self.providers[provider_name]
            
            if not provider.is_available():
                logger.warning(f"⚠️ Provider {provider_name} not available, skipping")
                continue
            
            try:
                logger.info(f"🔍 Searching with {provider_name}: {query}")
                results = await provider.search(query, num_results)
                
                if results.get("data"):
                    logger.info(f"✅ {provider_name} search successful: {len(results['data'])} results")
                    return results
                else:
                    logger.warning(f"⚠️ {provider_name} returned no results, trying next provider")
                    
            except asyncio.CancelledError:
                logger.warning(f"⚠️ {provider_name} search cancelled, trying next provider")
                continue
            except Exception as e:
                logger.error(f"❌ {provider_name} search failed: {e}, trying next provider")
                continue
        
        # All providers failed
        logger.error("❌ All search providers failed")
        return {"data": []}
    
    async def close(self):
        """Close all provider sessions"""
        try:
            await asyncio.gather(*[
                p.close() for p in self.providers.values()
            ], return_exceptions=True)
        except Exception:
            pass
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensure cleanup"""
        await self.close()
    
    def get_available_providers(self) -> List[str]:
        """Get list of available search providers"""
        return [name for name in self.provider_order if self.providers[name].is_available()]
    
    def get_provider_status(self) -> Dict[str, bool]:
        """Get status of all providers"""
        return {
            name: provider.is_available() 
            for name, provider in self.providers.items()
        }
