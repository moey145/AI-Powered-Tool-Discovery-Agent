import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional, Tuple
import time
from urllib.parse import urljoin, urlparse, quote_plus, unquote
import re
import json
import random
import os
from dataclasses import dataclass
from enum import Enum
from .config import settings
from .logger import get_logger
from .search_providers import SearchManager

# Setup logging
logger = get_logger('fastscraper')

class ScraperError(Exception):
    """Custom exception for scraper errors"""
    pass

class RateLimitError(ScraperError):
    """Raised when rate limited"""
    pass

class BlockedError(ScraperError):
    """Raised when blocked by website"""
    pass

@dataclass
class ScrapingResult:
    """Structured result for scraping operations"""
    success: bool
    content: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    response_time: Optional[float] = None

class CircuitBreaker:
    """Circuit breaker pattern for handling failures gracefully"""
    def __init__(self, failure_threshold=None, recovery_timeout=None):
        self.failure_threshold = failure_threshold or settings.failure_threshold
        self.recovery_timeout = recovery_timeout or settings.recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise ScraperError("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            
            raise e

# Enhanced FastScraperService with circuit breaker
class FastScraperService:
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(
            total=settings.scrape_timeout,
            connect=20
        )
        # Per-host throttling to reduce rate limits
        self._host_semaphores: Dict[str, asyncio.Semaphore] = {}
        self.max_retries = settings.max_retries
        self.circuit_breaker = CircuitBreaker()
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_connector: Optional[aiohttp.TCPConnector] = None
        self._session_loop: Optional[asyncio.AbstractEventLoop] = None
        self.session_pool: Optional[aiohttp.ClientSession] = None  # Backwards compatibility
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
        ]
        self._search_lock: Optional[Tuple[asyncio.Lock, asyncio.AbstractEventLoop]] = None
        
    def _build_ssl_context(self):
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    def _build_connector(self, ssl_context=None):
        return aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=12,
            limit_per_host=6,
            ttl_dns_cache=300,
            use_dns_cache=True,
            force_close=True,
            enable_cleanup_closed=True
        )

    async def _close_session(self):
        session = self._session
        connector = self._session_connector
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
        self._session = None
        self._session_connector = None
        self.session_pool = None

    async def __aenter__(self):
        """Async context manager for session management"""
        ssl_context = self._build_ssl_context()
        connector = self._build_connector(ssl_context)
        self._session = aiohttp.ClientSession(timeout=self.timeout, connector=connector)
        self._session_connector = connector
        self._session_loop = asyncio.get_running_loop()
        self.session_pool = self._session
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the scraper-specific HTTP session"""
        await self.close()

    async def close(self):
        await self._close_session()
        self._session_loop = None
        self._search_lock = None
        self._host_semaphores.clear()

    async def _get_search_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._search_lock is None or self._search_lock[1] is not loop:
            self._search_lock = (asyncio.Lock(), loop)
        return self._search_lock[0]

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have a valid session for the current event loop."""
        try:
            current_loop = asyncio.get_running_loop()
            session = self._session
            if (session is None or session.closed or self._session_loop is not current_loop):
                await self._close_session()
                ssl_context = self._build_ssl_context()
                new_connector = self._build_connector(ssl_context)
                session = aiohttp.ClientSession(timeout=self.timeout, connector=new_connector)
                self._session = session
                self._session_connector = new_connector
                self._session_loop = current_loop
                self.session_pool = session
        except Exception as e:
            logger.error(f"Error ensuring session: {e}")
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(timeout=self.timeout)
                self._session_connector = None
                self.session_pool = self._session
        return self._session

    async def scrape_with_circuit_breaker(self, url: str) -> ScrapingResult:
        """Scrape with circuit breaker protection"""
        start_time = time.time()
        
        try:
            result = await self.circuit_breaker.call(self._scrape_single_url, url)
            return ScrapingResult(
                success=True,
                content=result.get("markdown"),
                url=url,
                response_time=time.time() - start_time
            )
        except RateLimitError as e:
            return ScrapingResult(
                success=False,
                url=url,
                error=f"Rate limited: {str(e)}",
                response_time=time.time() - start_time
            )
        except BlockedError as e:
            return ScrapingResult(
                success=False,
                url=url,
                error=f"Blocked: {str(e)}",
                response_time=time.time() - start_time
            )
        except Exception as e:
            return ScrapingResult(
                success=False,
                url=url,
                error=f"Scraping failed: {str(e)}",
                response_time=time.time() - start_time
            )

    async def _scrape_single_url(self, url: str) -> Dict[str, str]:
        """Enhanced single URL scraping with better error handling"""
        session = await self._ensure_session()
        headers = self._get_enhanced_headers()
        
        # Add proxy rotation (if available)
        proxy = self._get_proxy()
        
        async with session.get(url, headers=headers, proxy=proxy) as response:
            if response.status == 429:
                raise RateLimitError(f"Rate limited by {url}")
            elif response.status == 403:
                raise BlockedError(f"Access forbidden by {url}")
            elif response.status != 200:
                raise ScraperError(f"HTTP {response.status} from {url}")
            
            html = await response.text()
            
            # Check for bot detection
            if self._is_bot_detected(html):
                raise BlockedError(f"Bot detection triggered on {url}")
            
            return self._extract_content_enhanced(html, url)

    def _get_enhanced_headers(self) -> Dict[str, str]:
        """Enhanced headers with better bot detection avoidance"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Charset': 'utf-8, iso-8859-1;q=0.5',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'Connection': 'keep-alive'
        }

    def _is_bot_detected(self, html: str) -> bool:
        """Enhanced bot detection checking"""
        bot_indicators = [
            "captcha",
            "unusual traffic",
            "robot",
            "automation",
            "blocked",
            "cloudflare",
            "access denied",
            "security check"
        ]
        
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in bot_indicators)

    def _get_proxy(self) -> Optional[str]:
        """Get proxy from pool (implement your proxy rotation logic)"""
        # Implement your proxy rotation logic here
        return None

    def _get_headers(self):
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Charset': 'utf-8, iso-8859-1;q=0.5',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        }

    async def search_companies(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        logger.info(f"🔍 Searching for: {query} (using SearchManager)")
        lock = await self._get_search_lock()
        async with lock:
            async with SearchManager() as manager:
                search_results = await manager.search(query, num_results)
        if not search_results.get("data"):
            logger.warning(f"❌ No results found for: {query}")
            return {"data": []}
        ranked = self._merge_and_rank(search_results["data"], query, limit=max(num_results, 6))
        logger.info(f"✅ Search found {len(ranked)} ranked results")
        return {"data": ranked[:num_results]}

    async def _search_google_enhanced(self, query: str, num_results: int) -> Dict[str, Any]:
        """Enhanced Google search with better bot detection avoidance"""
        session = await self._ensure_session()
        
        for attempt in range(self.max_retries):
            try:
                # Shorter delays between requests for faster processing
                if attempt > 0:
                    wait_time = random.uniform(3, 8)  # Reduced from 15-30s
                    logger.info(f"⏳ Waiting {wait_time:.1f}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    await asyncio.sleep(random.uniform(1, 3))  # Reduced from 3-8s
                
                headers = self._get_headers()
                
                # Use more natural search parameters
                encoded_query = quote_plus(query)
                
                # Try different Google domains and parameters
                search_options = [
                    f"https://www.google.com/search?q={encoded_query}&num={num_results}",
                    f"https://www.google.co.uk/search?q={encoded_query}&num={num_results}",
                    f"https://www.google.ca/search?q={encoded_query}&num={num_results}",
                    f"https://www.google.com.au/search?q={encoded_query}&num={num_results}",
                    f"https://www.google.de/search?q={encoded_query}&num={num_results}"
                ]
                
                search_url = random.choice(search_options)
                logger.info(f"🌐 Attempting Google search (attempt {attempt + 1}): {search_url[:80]}...")
                
                session = await self._ensure_session()
                async with session.get(search_url, headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Check if we got a real Google results page
                        if self._is_blocked_response(html):
                            logger.warning(f"⚠️ Google blocked/redirected request (attempt {attempt + 1})")
                            continue
                        
                        results = self._parse_google_results_enhanced(html, query, num_results)
                        
                        if results and len(results) > 0:
                            logger.info(f"✅ Google search successful: found {len(results)} results")
                            return {"data": results}
                        else:
                            logger.warning(f"⚠️ Google returned page but no valid results parsed")
                            
                    elif response.status == 429:
                        logger.warning(f"⚠️ Google rate limited (429)")
                        await asyncio.sleep(random.uniform(5, 10))  # Reduced from 30-60s
                        continue
                    elif response.status == 403:
                        logger.warning(f"⚠️ Google blocked request (403)")
                        await asyncio.sleep(random.uniform(20, 40))
                        continue
                    else:
                        logger.warning(f"⚠️ Google search failed with status: {response.status}")
                        continue
                            
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Google search timeout (attempt {attempt + 1})")
                continue
            except Exception as e:
                logger.warning(f"⚠️ Google search error (attempt {attempt + 1}): {str(e)[:100]}")
                continue
        
        logger.error("❌ All Google search attempts failed")
        return {"data": []}

    def _is_blocked_response(self, html: str) -> bool:
        blocked_indicators = [
            "if you are not redirected",
            "unusual traffic",
            "captcha",
            "blocked",
            "robot",
            "automation"
        ]
        html_lower = html.lower()
        for indicator in blocked_indicators:
            if indicator in html_lower:
                return True
        # Only treat as blocked if *both* small and few links
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all('a', href=True)
        if len(html) < 5000 and len(links) < 5:
            return True
        return False

    def _parse_google_results_enhanced(self, html: str, query: str, num_results: int) -> List[Dict]:
        """Enhanced Google results parsing with multiple strategies"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            # Save debug info only on failures
            # with open('debug_google.html', 'w', encoding='utf-8') as f:
            #     f.write(html)
            
            # Strategy 1: Look for modern Google result containers
            result_containers = soup.find_all(['div'], class_=re.compile(r'g\b'))
            
            for container in result_containers[:num_results * 2]:  # Get more than needed
                try:
                    # Find the main link
                    link_elem = container.find('a', href=True)
                    if not link_elem:
                        continue
                    
                    href = link_elem.get('href', '')
                    clean_url = self._clean_google_url(href)
                    
                    if not clean_url or not clean_url.startswith('http'):
                        continue
                    
                    if not self._is_relevant_url(clean_url, query):
                        continue
                    
                    # Get title from h3 or link text
                    title = ""
                    h3 = container.find('h3')
                    if h3:
                        title = h3.get_text(strip=True)
                    else:
                        title = link_elem.get_text(strip=True)
                    
                    if not title or len(title) < 3:
                        title = urlparse(clean_url).netloc
                    
                    # Get snippet from description spans
                    snippet = title
                    desc_spans = container.find_all(['span', 'div'], string=True)
                    for span in desc_spans:
                        text = span.get_text(strip=True)
                        if len(text) > 30 and len(text) < 300:
                            snippet = text
                            break
                    
                    # Avoid duplicates
                    if any(r['url'] == clean_url for r in results):
                        continue
                    
                    results.append({
                        'url': clean_url,
                        'title': title[:200],
                        'snippet': snippet[:300],
                        'metadata': {
                            'title': title,
                            'source': 'google'
                        }
                    })
                    
                    if len(results) >= num_results:
                        break
                        
                except Exception as e:
                    continue
            
            # Strategy 2: Fallback to finding all links if Strategy 1 failed
            if len(results) == 0:
                logger.info("🔄 Trying fallback link extraction...")
                all_links = soup.find_all('a', href=True)
                
                for link in all_links:
                    href = link.get('href', '')
                    clean_url = self._clean_google_url(href)
                    
                    if not clean_url or not clean_url.startswith('http'):
                        continue
                    
                    if not self._is_relevant_url(clean_url, query):
                        continue
                    
                    # Avoid duplicates
                    if any(r['url'] == clean_url for r in results):
                        continue
                    
                    title = link.get_text(strip=True) or urlparse(clean_url).netloc
                    
                    results.append({
                        'url': clean_url,
                        'title': title[:200],
                        'snippet': title[:300],
                        'metadata': {
                            'title': title,
                            'source': 'google'
                        }
                    })
                    
                    if len(results) >= num_results:
                        break
            
            logger.info(f"📊 Successfully parsed {len(results)} results from Google")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error parsing Google results: {e}")
            return []

    def _clean_google_url(self, href: str) -> str:
        try:
            if href.startswith('/url?q='):
                url_part = href.split('/url?q=')[1].split('&')[0]
                return unquote(url_part)
            elif href.startswith('/search?') or href.startswith('#'):
                return ""
            elif href.startswith('http'):
                if 'google.com' in href and '/url?q=' not in href:
                    return ""
                return href
            elif href.startswith('//'):
                return 'https:' + href
            else:
                return ""
        except Exception:
            return ""

    def _is_relevant_url(self, url: str, query: str) -> bool:
        """More lenient URL relevance checking"""
        try:
            domain = urlparse(url).netloc.lower()
            path = urlparse(url).path.lower()
            
            # Skip obvious unwanted domains
            skip_domains = ['google.com', 'bing.com', 'yahoo.com', 'facebook.com', 'twitter.com', 'youtube.com']
            if any(skip in domain for skip in skip_domains):
                return False
            
            # Skip URL shorteners
            skip_patterns = ['bit.ly', 'tinyurl', 't.co', 'goo.gl']
            if any(pattern in domain for pattern in skip_patterns):
                return False
            
            # Skip likely binary or download links (pdf, zip, etc.)
            bad_exts = ('.pdf', '.zip', '.rar', '.7z', '.dmg', '.exe')
            if path.endswith(bad_exts) or '/_ /downloads/'.replace(' ','') in path:
                return False
            
            q = (query or '').lower()
            # Context-aware quick rejects to avoid off-topic/mirrors
            if ("c++" in q or "cpp" in q):
                # Avoid mirrors/old docs for C++ queries
                if any(bad in domain for bad in [
                    'qtcentre.org',  # community mirror
                    'stlab.adobe.com',  # stale STL mirror
                    'boost.space'  # business platform
                ]):
                    return False
                # Prefer official docs; allow but we'll down-rank in scoring otherwise
            # React queries should not land on Flutter's pub.dev
            if 'react' in q and 'pub.dev' in domain:
                return False
            # Chai JS library should not be chaibuilder.com
            if 'chai' in q and 'chaibuilder.com' in domain:
                return False

            # Swift testing queries: enforce allowlist and reject unrelated domains
            if 'swift' in q and ('test' in q or 'testing' in q):
                allowed_swift_domains = [
                    'developer.apple.com', 'swift.org', 'quick.github.io', 'mockingbirdswift.com', 'pointfreeco',
                    'github.com'
                ]
                bad_swift = [
                    'gohugo.io', 'playwright.dev', 'wordpress', 'presscustomizr.com', 'jestjs.io', 'react.dev',
                    'storybook.js.org', 'docusaurus.io', 'cuckoosandbox', 'readthedocs.io', 'nimble-arduino'
                ]
                if any(bad in domain for bad in bad_swift):
                    return False
                # Disambiguate GitHub repos: only allow known Swift testing repos
                if 'github.com' in domain:
                    allowed_paths = [
                        '/quick/quick', '/quick/nimble', '/pointfreeco/swift-snapshot-testing', '/realm/swiftlint',
                        '/alisoftware/ohhttpstubs', '/brightify/cuckoo', '/typelift/swiftcheck'
                    ]
                    if not any(ap in path for ap in allowed_paths):
                        return False
                # Disambiguate Nimble vs NimBLE-Arduino
                if 'h2zero' in domain or 'arduino' in domain or 'nimble-arduino' in path:
                    return False
                # Disambiguate Quick vs Hugo quick-start
                if 'gohugo.io' in domain:
                    return False
                # Disambiguate SnapshotTesting vs Jest/Storybook snapshot testing
                if any(b in domain for b in ['jestjs.io', 'playwright.dev', 'storybook.js.org']):
                    return False

            # Be more lenient - allow most domains
            return True
            
        except Exception:
            return False

    # ... rest of your existing methods remain the same ...
    async def scrape_company_pages(self, url: str) -> Optional[Dict[str, str]]:
        """Enhanced page scraping with retry logic and better error handling"""
        session = await self._ensure_session()

        for attempt in range(self.max_retries + 1):
            try:
                headers = self._get_headers()
                # Add random delay between requests
                if attempt > 0:
                    await asyncio.sleep(random.uniform(2, 4))
                
                # Acquire per-host semaphore
                parsed = urlparse(url)
                host = (parsed.netloc or "").lower()
                if host not in self._host_semaphores:
                    # limit 2 concurrent requests per host
                    self._host_semaphores[host] = asyncio.Semaphore(2)
                host_sem = self._host_semaphores[host]

                async with host_sem:
                    async with session.get(url, headers=headers) as response:
                        # Reject non-HTML early (e.g., PDFs)
                        ctype = response.headers.get('Content-Type', '')
                        if 'text/html' not in ctype.lower():
                            if attempt == self.max_retries:
                                logger.warning(f"Non-HTML content for {url}: {ctype}")
                                return None
                            else:
                                return None
                        if response.status == 403:
                            logger.warning(f"Access forbidden for {url}, trying with different headers")
                            continue
                        elif response.status == 429:
                            # Exponential backoff with jitter
                            backoff = min(8, 2 ** attempt)
                            jitter = random.uniform(0, 1)
                            wait_s = backoff + jitter
                            logger.warning(f"Rate limited for {url}, waiting {wait_s:.1f}s before retry")
                            await asyncio.sleep(wait_s)
                            continue
                        elif response.status != 200:
                            if attempt == self.max_retries:
                                logger.error(f"Failed to scrape {url}: HTTP {response.status}")
                                return None
                            continue
                        
                        html = await response.text()
                        base_content = self._extract_content_enhanced(html, url)
                        
                        # If GitHub repo page, try to fetch README to enrich content
                        try:
                            parsed = urlparse(url)
                            if parsed.netloc.lower() == 'github.com':
                                parts = [p for p in parsed.path.split('/') if p]
                                if len(parts) >= 2:
                                    owner, repo = parts[0], parts[1]
                                    readme_md = await self._try_fetch_github_readme(session, owner, repo)
                                    if readme_md:
                                        combined = (readme_md + "\n\n" + (base_content.get('markdown') or '')).strip()
                                        return {"markdown": combined[:settings.max_content_length]}
                        except Exception:
                            pass
                        
                        return base_content
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout for {url} (attempt {attempt + 1})")
                if attempt == self.max_retries:
                    return None
            except Exception as e:
                logger.error(f"Scraping error for {url} (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries:
                    return None
                
    async def _search_serper(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        url = "https://google.serper.dev/search"
        api_key = settings.serper_api_key
        if not api_key:
            logger.error("⚠️ SERPER_API_KEY not set; skipping Serper call")
            return {"data": []}
        
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        # Use richer Serper params to improve result quality and localization
        payload = {
            "q": query,
            "num": max(10, num_results),
            "hl": "en",
            "gl": "us",
            "autocorrect": True,
            "page": 1,
            # Filter similar results; Serper respects Google's filter param (1 = filter near-duplicates)
            "filter": 1
        }
        try:
            session = await self._ensure_session()
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    # Collect organic results primarily; optionally include knowledge graph/answer box later
                    for item in data.get("organic", [])[: max(20, num_results * 2)]:
                        link = item.get("link")
                        if not link or not isinstance(link, str):
                            continue
                        # Filter non-HTML/download links early
                        try:
                            path = urlparse(link).path.lower()
                        except Exception:
                            path = ""
                        if path.endswith((".pdf", ".zip", ".rar", ".7z", ".dmg", ".exe")) or "/_/downloads/" in path:
                            continue
                        if not self._is_relevant_url(link, query):
                            continue
                        results.append({
                            "url": link,
                            "title": item.get("title"),
                            "snippet": item.get("snippet"),
                            "metadata": {"source": "serper", "query": query}
                        })
                    return {"data": results}
                else:
                    logger.error(f"Serper API error: {resp.status}")
                    return {"data": []}
        except Exception as e:
            logger.error(f"Serper API exception: {e}")
            return {"data": []}

    def _extract_content_enhanced(self, html: str, url: str) -> Dict[str, str]:
        """Enhanced content extraction with better selectors and filtering"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'header', 
                        'advertisement', 'cookie', 'popup', 'modal', 'sidebar', 'form', 'iframe']):
            tag.decompose()
        
        # Enhanced content selectors with priority
        content_selectors = [
            'main', 'article', '[role="main"]',
            '.content', '#content', '.main-content', '.post-content', 
            '.entry-content', '.article-content', '.page-content',
            '.docs-content', '.documentation', '.readme', '.markdown-body',
            '.product-description', '.feature-list', '.pricing',
            'body'
        ]
        
        main_content = None
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content and len(main_content.get_text(strip=True)) > settings.min_content_length:
                break
        
        if not main_content:
            main_content = soup.find('body') or soup
        
        # Extract structured information
        structured_data = self._extract_structured_info(soup, url)
        
        # Get clean text content with better formatting
        text_content = self._clean_text_content(main_content)
        
        # Combine structured data with text content
        final_content = ""
        if structured_data:
            final_content += structured_data + "\n\n"
        final_content += text_content

        # Detect JS-required/empty pages and discard to avoid bad entries
        lowered = (final_content or "").lower()
        js_required_indicators = [
            "this page requires javascript",
            "please enable javascript",
            "requires javascript to view",
            "noscript"
        ]
        if any(ind in lowered for ind in js_required_indicators) or len(final_content.strip()) < settings.min_content_length:
            return None
        
        return {"markdown": final_content[:settings.max_content_length]}

    async def _try_fetch_github_readme(self, session: aiohttp.ClientSession, owner: str, repo: str) -> Optional[str]:
        """Try to fetch README.md from a GitHub repository to enrich content."""
        raw_urls = [
            f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md",
            f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md",
            f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md",
        ]
        for raw_url in raw_urls:
            try:
                async with session.get(raw_url) as resp:
                    if resp.status == 200 and 'text/plain' in resp.headers.get('Content-Type', '').lower():
                        md = await resp.text()
                        if md and len(md) > 200:
                            return md
            except Exception:
                continue
        return None

    # ---------- Intent-aware search helpers ----------
    def _build_serper_queries(self, query: str) -> List[str]:
        base = query.strip()
        lower = base.lower()
        is_category = any(tok in lower for tok in ["tools", "libraries", "frameworks", "platforms", "alternatives", "compare", "best", "top"])
        # Build intent-aware variants
        variants = []
        if is_category:
            variants.extend([
                f"{base} best for developers",
                f"{base} comparison",
                f"{base} alternatives",
                f"{base} overview",
                f"{base} open source",
            ])
        else:
            # Likely a specific tool/product name
            variants.extend([
                f"{base} official website",
                f"{base} documentation",
                f"{base} docs",
                f"{base} getting started",
                f"{base} api documentation",
                f"{base} pricing",
                f"{base} features",
                f"site:github.com {base}",
                f"site:readthedocs.io {base}",
                f"site:docs.* {base}",
            ])
        # Always include the raw query as-is as a baseline
        variants.append(base)
        seen = set()
        uniq = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                uniq.append(v)
        return uniq

    def _primary_keywords(self, text: str) -> List[str]:
        words = re.findall(r"[A-Za-z0-9\-\.]{3,}", text.lower())
        stops = {"the","and","for","with","from","this","that","best","tools","tool","site","official"}
        uniq = []
        for w in words:
            if w in stops:
                continue
            if w not in uniq:
                uniq.append(w)
        return uniq[:3]

    def _context_keywords(self, query: str) -> List[str]:
        text = query.lower()
        terms: List[str] = []
        if "test" in text:
            terms.extend(["test", "testing", "unit", "assert", "runner"])
        if "framework" in text:
            terms.append("framework")
        if "javascript" in text or "js" in text:
            terms.extend(["javascript", "js", "node"])
        if "api" in text:
            terms.append("api")
        # De-duplicate and keep concise
        seen = set()
        out = []
        for t in terms:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out[:6]

    def _score_domain(self, url: str, query: str, title: str, snippet: str) -> float:
        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            domain = ""
        score = 0.0
        
        # Query type detection for better scoring
        query_lower = query.lower()
        is_paid_query = any(word in query_lower for word in ["paid", "premium", "commercial", "enterprise"])
        is_free_query = any(word in query_lower for word in ["free", "open source", "opensource"])
        is_language_query = any(word in query_lower for word in ["java", "python", "javascript", "kotlin", "go", "rust"])
        
        # Domain-based signals
        if domain.startswith("docs.") or ".readthedocs." in domain:
            score += 8
        if "github.com" in domain:
            score += 6
        if domain.endswith(".dev") or domain.endswith(".org"):
            score += 3
        if domain.endswith(".io") or domain.endswith(".ai") or domain.endswith(".com"):
            score += 1
            
        # Penalize listicle/aggregator domains
        bads = [
            "medium.com","reddit.com","quora.com","pinterest.","apkpure","apkcombo",
            "top10","top-10","bestof","guru99","geeksforgeeks","udemy","coursera",
            "capterra","g2.com","slant.co","alternativeto.net","ai-directory","listicle"
        ]
        if any(b in domain for b in bads):
            score -= 6
            
        # Path-based signals
        path = urlparse(url).path.lower()
        if any(seg in path for seg in ["/docs", "/documentation", "/guide", "/getting-started", "/quickstart", "/api"]):
            score += 5
        if "/blog" in path:
            score += 0.5
        if any(seg in path for seg in ["/news", "/forum", "/community"]):
            score -= 0.5
            
        # Penalize binary/download links
        if path.endswith(('.pdf', '.zip', '.rar', '.7z', '.dmg', '.exe')):
            score -= 8
            
        # Query-specific scoring
        if is_paid_query:
            # Boost commercial/enterprise domains for paid queries
            if any(word in domain for word in ["enterprise", "commercial", "premium", "business"]):
                score += 3
            if any(word in path for word in ["/pricing", "/enterprise", "/business", "/commercial"]):
                score += 2
        elif is_free_query:
            # Boost open source domains for free queries
            if "github.com" in domain:
                score += 2
            if domain.endswith(".org"):
                score += 1
            if any(word in path for word in ["/opensource", "/free", "/community"]):
                score += 1
                
        # Language-specific scoring
        if is_language_query:
            if "java" in query_lower and any(word in domain for word in ["spring", "hibernate", "apache"]):
                score += 2
            elif "python" in query_lower and any(word in domain for word in ["django", "flask", "fastapi", "python"]):
                score += 2
            elif "javascript" in query_lower and any(word in domain for word in ["react", "vue", "angular", "node"]):
                score += 2
            elif "go" in query_lower or "golang" in query_lower:
                if any(word in domain for word in ["gin-gonic", "labstack.com", "gofiber.io", "go.dev", "golang.org"]):
                    score += 3
            elif "swift" in query_lower:
                if any(word in domain for word in ["developer.apple.com", "alamofire.github.io", "swift.org", "github.com"]):
                    score += 3
            # Disambiguate Enzyme (React testing) from Enzyme Finance
            if 'enzyme' in query_lower and ('javascript' in query_lower or 'react' in query_lower or 'testing' in query_lower):
                if any(p in domain for p in ["enzymejs.github.io", "github.com"]):
                    score += 10
                if any(fin in domain for fin in ["enzyme.finance", "enzyme.fi", "enzyme.finance"]):
                    score -= 15
            elif "kotlin" in query_lower and any(word in domain for word in ["kotlin", "jetbrains", "spring"]):
                score += 2
        
        # Primary keyword matching
        for kw in self._primary_keywords(query):
            if kw and kw in domain:
                score += 5
                
        # Text content scoring
        text = f"{title or ''} {snippet or ''}".lower()
        bonuses = ["official","documentation","docs","api","pricing","features","getting started","quickstart"]
        for b in bonuses:
            if b in text:
                score += 1.5
                
        # Contextual match: boost if query terms appear
        for ck in self._context_keywords(query):
            if ck in text:
                score += 1.2
                
        # If none of the context keywords appear, lightly penalize to avoid off-topic
        if self._context_keywords(query) and not any(ck in text for ck in self._context_keywords(query)):
            score -= 1.5
            
        # HEAVILY penalize completely off-topic domains
        if "react" in query_lower and any(off_topic in domain for off_topic in ["aws", "amazon", "microsoft", "google", "oracle", "salesforce"]):
            score -= 20  # Massive penalty for off-topic cloud providers
        if "javascript" in query_lower and any(off_topic in domain for off_topic in ["aws", "amazon", "microsoft", "google", "oracle", "salesforce"]):
            score -= 20
        if "python" in query_lower and any(off_topic in domain for off_topic in ["aws", "amazon", "microsoft", "google", "oracle", "salesforce"]):
            score -= 20
        if "c++" in query_lower or "cpp" in query_lower:
            # Heavy penalties for C++ queries that return irrelevant results
            if any(off_topic in domain for off_topic in ["aws", "amazon", "microsoft", "google", "oracle", "salesforce", "gov", "county", "recorder", "realestate", "property"]):
                score -= 25  # Even heavier penalty for C++ queries
            # Boost C++ specific domains
            if any(cpp_domain in domain for cpp_domain in ["cpp", "boost", "qt", "stl", "unreal", "godot", "fltk", "gtk", "wxwidgets"]):
                score += 10
            # Strongly boost authoritative C++ doc domains
            preferred_cpp = [
                'doc.qt.io', 'qt.io',
                'boost.org', 'www.boost.org',
                'docs.opencv.org', 'opencv.org',
                'en.cppreference.com',
                'pocoproject.org', 'docs.pocoproject.org',
                'wxwidgets.org', 'docs.wxwidgets.org',
                'eigen.tuxfamily.org', 'libeigen.gitlab.io'
            ]
            if any(p in domain for p in preferred_cpp):
                score += 12
            # Penalize known mirrors/low-quality sources for C++
            if any(bad in domain for bad in ['qtcentre.org', 'stlab.adobe.com', 'boost.space']):
                score -= 12

        # JS testing specific adjustments
        if ("javascript" in query_lower or "js" in query_lower or "react" in query_lower) and ("test" in query_lower or "testing" in query_lower or "testing frameworks" in query_lower):
            # Prefer the official Chai site when 'chai' appears
            if 'chai' in query_lower:
                if 'chaijs.com' in domain:
                    score += 8
                if 'chaibuilder.com' in domain:
                    score -= 12
            # Prefer official Jest site; avoid archive unless nothing else
            if 'jest' in query_lower:
                if 'jestjs.io' in domain:
                    score += 8
                if 'archive.jestjs.io' in domain:
                    score -= 6
            # Prefer official Cypress docs; avoid sorry-cypress mirrors
            if 'cypress' in query_lower:
                if 'docs.cypress.io' in domain:
                    score += 10
                if 'sorry-cypress.dev' in domain:
                    score -= 8
            # Prefer React Testing Library and Enzyme official docs
            if 'react testing library' in query_lower or 'testing library' in query_lower:
                if 'testing-library.com' in domain:
                    score += 10
            if 'enzyme' in query_lower:
                if 'enzymejs.github.io' in domain:
                    score += 10
                if any(fin in domain for fin in ["enzyme.finance", "enzyme.fi"]):
                    score -= 15
        # Swift testing disambiguation and boosts
        if 'swift' in query_lower and ("test" in query_lower or "testing" in query_lower):
            preferred = [
                'developer.apple.com',  # XCTest
                'quick.github.io', 'github.com/Quick/Quick',
                'github.com/Quick/Nimble',
                'github.com/pointfreeco/swift-snapshot-testing', 'pointfreeco',
                'github.com/realm/SwiftLint', 'mockingbirdswift.com',
                'github.com/AliSoftware/OHHTTPStubs',
                'github.com/typelift/SwiftCheck',
                'github.com/Brightify/Cuckoo'
            ]
            if any(p in domain for p in preferred):
                score += 12
            # Penalize unrelated results like Hugo, Playwright docs, WordPress, etc.
            unrelated = ['gohugo.io', 'playwright.dev', 'wordpress', 'presscustomizr.com', 'jestjs.io', 'react.dev', 'storybook.js.org']
            if any(u in domain for u in unrelated):
                score -= 12
            # Disambiguate NimBLE-Arduino and Cuckoo Sandbox
            if 'nimble' in query_lower and 'h2zero' in domain:
                score -= 15
            if 'cuckoo' in query_lower and 'cuckoosandbox' in domain:
                score -= 15
            # Disambiguate Mockingbird (Swift) vs web wireframing tools
            if 'mockingbird' in query_lower and any(b in domain for b in ['gomockingbird', 'mockingbird.io']):
                score -= 15

        # React-specific adjustments
        if 'react' in query_lower:
            # Avoid Flutter domains when React is requested
            if 'pub.dev' in domain:
                score -= 10

        # Doctest ambiguity: prefer C++ doctest docs; penalize Python doctest
        if 'doctest' in query_lower and ('c++' in query_lower or 'cpp' in query_lower or 'testing' in query_lower):
            if any(p in domain for p in ['doctest.sourceforge.net', 'doctest.dev']):
                score += 10
            if 'docs.python.org' in domain and '/doctest' in path:
                score -= 15
        if "c#" in query_lower or "csharp" in query_lower:
            if any(off_topic in domain for off_topic in ["aws", "amazon", "microsoft", "google", "oracle", "salesforce"]):
                score -= 20
        if "go" in query_lower or "golang" in query_lower:
            if any(off_topic in domain for off_topic in ["aws", "amazon", "microsoft", "google", "oracle", "salesforce"]):
                score -= 20
        if "rust" in query_lower:
            if any(off_topic in domain for off_topic in ["aws", "amazon", "microsoft", "google", "oracle", "salesforce"]):
                score -= 20
            
        return score

    def _merge_and_rank(self, items: List[Dict[str, Any]], query: str, limit: int = 10) -> List[Dict[str, Any]]:
        dedup: Dict[str, Dict[str, Any]] = {}
        domain_counts: Dict[str, int] = {}
        for it in items:
            url = it.get("url") or it.get("link")
            title = it.get("title") or ""
            snippet = it.get("snippet") or ""
            if not url or not isinstance(url, str):
                continue
            # Limit multiple results from the same domain to improve diversity
            try:
                dom = urlparse(url).netloc.lower()
            except Exception:
                dom = ""
            if dom:
                cnt = domain_counts.get(dom, 0)
                if cnt >= 2:
                    continue
                domain_counts[dom] = cnt + 1
            if url not in dedup:
                dedup[url] = {
                    "url": url,
                    "title": title[:200],
                    "snippet": snippet[:300],
                    "metadata": it.get("metadata", {})
                }
        ranked = []
        for it in dedup.values():
            s = self._score_domain(it["url"], query, it.get("title",""), it.get("snippet",""))
            ranked.append((s, it))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in ranked[:limit]]

    def _extract_structured_info(self, soup: BeautifulSoup, url: str) -> str:
        """Extract structured information from common page elements"""
        info_parts = []
        
        # Try to extract title
        title = soup.find('title')
        if title:
            info_parts.append(f"# {title.get_text(strip=True)}")
        
        # Try to extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            info_parts.append(f"Description: {meta_desc.get('content').strip()}")

        # Extract Open Graph and Twitter card summaries
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            info_parts.append(f"OG Title: {og_title.get('content').strip()}")
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            info_parts.append(f"OG Description: {og_desc.get('content').strip()}")
        tw_desc = soup.find('meta', attrs={'name': 'twitter:description'})
        if tw_desc and tw_desc.get('content'):
            info_parts.append(f"Twitter: {tw_desc.get('content').strip()}")

        # Extract simple JSON-LD Organization/Product/SoftwareApplication summaries
        try:
            for script in soup.find_all('script', type='application/ld+json'):
                txt = script.string
                if not txt:
                    continue
                data = json.loads(txt)
                if isinstance(data, list):
                    candidates = data
                else:
                    candidates = [data]
                for node in candidates:
                    t = (node.get('@type') or node.get('type') or '').lower()
                    if any(k in t for k in ['softwareapplication','product','organization','website']):
                        name = node.get('name') or ''
                        desc = node.get('description') or ''
                        if name or desc:
                            info_parts.append(f"JSON-LD: {name} {desc}".strip())
        except Exception:
            pass
        
        return "\n".join(info_parts)

    def _clean_text_content(self, content_element) -> str:
        """Clean and format text content"""
        lines = []
        for element in content_element.descendants:
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = element.get_text(strip=True)
                if text:
                    lines.append(f"\n## {text}\n")
            elif element.name in ['p', 'div']:
                text = element.get_text(strip=True)
                if text and len(text) > 10:
                    lines.append(text)
            elif element.name in ['li']:
                text = element.get_text(strip=True)
                if text and len(text) > 5:
                    lines.append(f"- {text}")
            elif element.name in ['code', 'pre']:
                text = element.get_text('\n', strip=True)
                if text and len(text) > 10:
                    lines.append(f"\n```\n{text[:500]}\n```\n")
            elif element.name == 'table':
                # Flatten simple tables to text rows
                rows = []
                for tr in element.find_all('tr'):
                    cols = [c.get_text(' ', strip=True) for c in tr.find_all(['td', 'th'])]
                    if cols:
                        rows.append(' | '.join(cols))
                if rows:
                    lines.append('\n' + '\n'.join(rows[:20]) + '\n')
        
        content = '\n'.join(lines)
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r' {2,}', ' ', content)
        
        return content

    async def scrape_multiple_pages(self, urls):
        """Scrape multiple URLs concurrently, but keep concurrency low for speed and politeness"""
        if not urls:
            return []
        semaphore = asyncio.Semaphore(settings.max_concurrent_scrapes)
        async def run(url):
            async with semaphore:
                return await self.scrape_company_pages(url)
        tasks = [run(url) for url in urls if url]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [result for result in results if isinstance(result, dict)]

    async def smart_company_research(self, tool_name: str):
        """Smart research for a specific tool"""
        search_results = await self.search_companies(f"{tool_name} official documentation", num_results=3)
        
        if not search_results.get("data"):
            return {"markdown": f"No results found for {tool_name}"}
        
        # Get the best URL (prioritize official sites)
        best_url = None
        for result in search_results["data"]:
            url = result.get("url", "")
            if any(keyword in url.lower() for keyword in [tool_name.lower(), "github.com", "docs.", ".org"]):
                best_url = url
                break
        
        if not best_url:
            best_url = search_results["data"][0].get("url")
        
        if best_url:
            scraped_content = await self.scrape_company_pages(best_url)
            return scraped_content or {"markdown": f"Failed to scrape content for {tool_name}"}
        
        return {"markdown": f"No valid URL found for {tool_name}"}

async def search_multiple_sources(self, query: str, num_results: int = 5) -> Dict[str, Any]:
    """Search across multiple sources for better results"""
    search_tasks = [
        self._search_serper(query, num_results),
        self._search_github(query, num_results),
        self._search_stackoverflow(query, num_results),
        self._search_google_enhanced(query, num_results)
    ]
    
    results = await asyncio.gather(*search_tasks, return_exceptions=True)
    
    # Combine and deduplicate results
    all_results = []
    seen_urls = set()
    
    for result in results:
        if isinstance(result, dict) and result.get("data"):
            for item in result["data"]:
                url = item.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)
    
    return {"data": all_results[:num_results * 2]}

async def _search_github(self, query: str, num_results: int) -> Dict[str, Any]:
    """Search GitHub repositories"""
    try:
        headers = {
            "Authorization": f"token {settings.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        url = f"https://api.github.com/search/repositories?q={quote_plus(query)}&sort=stars&order=desc"
        
        session = await self._ensure_session()
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                results = []
                
                for repo in data.get("items", [])[:num_results]:
                    results.append({
                        "url": repo["html_url"],
                        "title": repo["name"],
                        "snippet": repo["description"] or "No description",
                        "metadata": {
                            "source": "github",
                            "stars": repo["stargazers_count"],
                            "language": repo["language"]
                        }
                    })
                
                return {"data": results}
            else:
                return {"data": []}
    except Exception as e:
        logger.error(f"GitHub search error: {e}")
        return {"data": []}

async def _search_stackoverflow(self, query: str, num_results: int) -> Dict[str, Any]:
    """Search Stack Overflow questions"""
    try:
        url = f"https://api.stackexchange.com/2.3/search/advanced"
        params = {
            "order": "desc",
            "sort": "votes",
            "q": query,
            "site": "stackoverflow",
            "pagesize": num_results
        }
        
        session = await self._ensure_session()
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                results = []
                
                for question in data.get("items", [])[:num_results]:
                    results.append({
                        "url": question["link"],
                        "title": question["title"],
                        "snippet": question.get("excerpt", "").replace("&quot;", '"'),
                        "metadata": {
                            "source": "stackoverflow",
                            "score": question["score"],
                            "answers": question["answer_count"]
                        }
                    })
                
                return {"data": results}
            else:
                return {"data": []}
    except Exception as e:
        logger.error(f"Stack Overflow search error: {e}")
        return {"data": []}