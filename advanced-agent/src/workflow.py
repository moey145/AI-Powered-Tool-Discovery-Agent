import asyncio
import time
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from .models import ResearchState, CompanyInfo, CompanyAnalysis
from .fastscraper import FastScraperService
from .prompts import DeveloperToolsPrompts
from .search_providers import SearchManager
from .intent_registry import IntentRegistry
import re
from urllib.parse import urlparse
from functools import lru_cache

class Workflow:
    def __init__(self):
        self.scraper = FastScraperService()
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
        self.prompts = DeveloperToolsPrompts()
        self.workflow = self._build_workflow()
        # Performance optimization: Cache for tool extraction
        self._tool_cache = {}
        self._max_cache_size = 100
        # Store partial results per query for graceful timeouts
        self._partial_results: Dict[str, List[CompanyInfo]] = {}
        self.intent_registry = IntentRegistry()

    def _build_workflow(self):
        graph = StateGraph(ResearchState)
        graph.add_node("extract_tools", self._extract_tools_step)
        graph.add_node("research", self._research_step)
        graph.add_node("analyze", self._analyze_step)
        graph.set_entry_point("extract_tools")
        graph.add_edge("extract_tools", "research")
        graph.add_edge("research", "analyze")
        graph.add_edge("analyze", END)
        return graph.compile()

    def clear_partial_results(self, query: str) -> None:
        try:
            if query in self._partial_results:
                del self._partial_results[query]
        except Exception:
            pass

    def _extract_tools_step(self, state: ResearchState) -> Dict[str, Any]:
        # Handle async execution within sync context
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._extract_tools_async(state))
                    return future.result()
        except RuntimeError:
            # No running loop in this thread
            pass
        return asyncio.run(self._extract_tools_async(state))

    async def _extract_tools_async(self, state: ResearchState) -> Dict[str, Any]:
        start_time = time.time()
        print(f"🔍 Finding articles about: {state.query}")

        # Check cache first for performance
        cache_key = f"{state.query.lower().strip()}"
        if cache_key in self._tool_cache:
            print("⚡ Using cached tool extraction")
            return {"extracted_tools": self._tool_cache[cache_key]}

        query_lower_full = state.query.lower()
        pricing_model = self._extract_pricing_model(state.query)
        intent_rule = self.intent_registry.match(query_lower_full, pricing_model)

        if intent_rule:
            result = intent_rule.fetch(pricing_model)
            if result:
                extracted = self._sanitize_curated_tools(result[:8])
                # Apply context filtering even for curated results to ensure alignment
                filtered = self._filter_tools_by_query_context(state.query, extracted)
                if filtered:
                    seen_tools = []
                    for tool in filtered:
                        if tool not in seen_tools:
                            seen_tools.append(tool)
                    extracted = seen_tools[:8]
                self._cache_tools(cache_key, extracted)
                print(f"✅ Intent registry matched '{intent_rule.name}' with {len(extracted)} tools")
                return {"extracted_tools": extracted}

        # Analyze query type and build appropriate search strategies
        query_type = self._analyze_query_type(state.query)
        print(f"📋 Query type detected: {query_type}")

        # Build query variants based on type with enhanced pricing filtering
        base_query = self._extract_base_query(state.query)

        if query_type == "paid":
            # For queries like "paid frameworks", "premium tools", etc.
            article_query = f"{base_query} commercial tools enterprise solutions premium frameworks paid licensing"
        elif query_type == "free":
            # For queries like "free tools", "open source frameworks", etc.
            article_query = f"{base_query} open source tools free frameworks community libraries FOSS"
        elif query_type == "freemium":
            # For freemium/trial queries
            article_query = f"{base_query} freemium tools trial versions free tier premium upgrade"
        elif query_type == "specific_language":
            # For language-specific queries with pricing context
            if pricing_model == "paid":
                article_query = f"{state.query} commercial frameworks enterprise solutions premium libraries"
            elif pricing_model == "free":
                article_query = f"{state.query} open source frameworks free libraries community tools"
            elif pricing_model == "freemium":
                article_query = f"{state.query} freemium frameworks trial versions free tier"
            else:
                article_query = f"{state.query} frameworks libraries tools ecosystem best practices"
        elif query_type == "specific_category":
            # For category-specific queries with pricing context
            if pricing_model == "paid":
                article_query = f"{state.query} commercial tools enterprise solutions premium alternatives"
            elif pricing_model == "free":
                article_query = f"{state.query} open source tools free alternatives community solutions"
            elif pricing_model == "freemium":
                article_query = f"{state.query} freemium tools trial versions free tier alternatives"
            else:
                article_query = f"{state.query} tools frameworks libraries alternatives comparison"
        elif query_type == "cicd":
            # CI/CD specific enrichment
            article_query = (
                f"{base_query} CI CD pipelines continuous integration continuous delivery deployment build runners workflows official docs"
            )
        elif query_type == "devops":
            # DevOps broad enrichment (CI/CD, IaC, containers, monitoring)
            article_query = (
                f"{base_query} DevOps tools CI CD infrastructure as code Terraform Ansible containers Docker Kubernetes monitoring Prometheus Grafana official docs"
            )
        else:
            # For general queries - make them much more specific
            if "react" in state.query.lower():
                if "state" in state.query.lower() and "management" in state.query.lower():
                    # Very specific React state management search
                    article_query = "React state management libraries Redux Zustand MobX Recoil Jotai React Query SWR"
                elif "routing" in state.query.lower():
                    article_query = "React routing libraries React Router Next.js routing"
                elif "testing" in state.query.lower():
                    article_query = "React testing libraries Jest React Testing Library Cypress Testing Library"
                else:
                    article_query = f"{state.query} React ecosystem libraries tools"
            elif "kubernetes" in state.query.lower() or "k8s" in state.query.lower():
                # Kubernetes-focused query
                article_query = "Kubernetes tools kubectl Helm Argo CD Kustomize Prometheus Grafana Istio Linkerd KEDA Tilt Skaffold Lens"
            elif any(tok in state.query.lower() for tok in ["sql", "database", "databases", "postgres", "mysql", "sqlite", "mariadb", "oracle", "sql server"]):
                # SQL/Database-focused query
                article_query = "SQL databases PostgreSQL MySQL MariaDB SQLite SQL Server Oracle CockroachDB YugabyteDB Amazon Aurora comparison"
            elif "javascript" in state.query.lower():
                article_query = f"{state.query} JavaScript libraries frameworks tools ecosystem"
            elif "python" in state.query.lower():
                article_query = f"{state.query} Python libraries frameworks tools ecosystem"
            elif "java" in state.query.lower():
                article_query = f"{state.query} Java libraries frameworks tools ecosystem"
            elif "kotlin" in state.query.lower():
                article_query = f"{state.query} Kotlin libraries frameworks tools ecosystem"
            elif "c++" in state.query.lower() or "cpp" in state.query.lower():
                # Very specific C++ search to avoid irrelevant results
                if "web" in state.query.lower():
                    article_query = "C++ web frameworks CppCMS Crow Pistache Qt WebEngine"
                elif "gui" in state.query.lower() or "desktop" in state.query.lower():
                    article_query = "C++ GUI frameworks Qt wxWidgets FLTK GTK+ desktop applications"
                elif "game" in state.query.lower():
                    article_query = "C++ game engines Unreal Engine Unity C++ Godot game development"
                elif "testing" in state.query.lower():
                    article_query = "C++ testing frameworks Google Test Catch2 Boost.Test CppUnit Unity framework C++ unit testing"
                else:
                    article_query = "C++ programming libraries Boost C++ library Qt C++ framework STL C++ standard library Eigen C++ linear algebra OpenCV C++ computer vision Poco C++ libraries"
            elif "c#" in state.query.lower() or "csharp" in state.query.lower():
                article_query = f"{state.query} .NET C# frameworks libraries tools ecosystem"
            elif "go" in state.query.lower() or "golang" in state.query.lower():
                article_query = f"{state.query} Go frameworks libraries tools ecosystem"
            elif "rust" in state.query.lower():
                article_query = f"{state.query} Rust frameworks libraries tools ecosystem"
            elif "swift" in state.query.lower():
                article_query = f"{state.query} Swift frameworks libraries tools iOS macOS ecosystem"
            else:
                article_query = f"{state.query} tools comparison best alternatives"

        # Fast concurrent search using SearchManager with timeout
        try:
            search_results = await asyncio.wait_for(
                self.scraper.search_companies(article_query, num_results=10), 
                timeout=10.0
            )
        except asyncio.TimeoutError:
            print("⚠️ Search timeout, using fallback extraction")
            tool_names = self._extract_tools_from_query(state.query)
            self._cache_tools(cache_key, tool_names)
            return {"extracted_tools": tool_names}

        # Check if we got actual search results (not hardcoded fallback)
        if not search_results.get("data"):
            print("⚠️ No search results found, using query-based extraction")
            # Fallback to extracting from query if no search results
            tool_names = self._extract_tools_from_query(state.query)
            self._cache_tools(cache_key, tool_names)
            return {"extracted_tools": tool_names}

        # Optimized concurrent scraping with increased concurrency
        urls = [result.get("url") for result in search_results["data"] if result.get("url")]
        # Filter out known problematic sites
        filtered_urls = []
        for url in urls[:3]:
            if not any(blocked in url.lower() for blocked in ["datacamp.com", "coursera.org", "udemy.com"]):
                filtered_urls.append(url)
        
        # Increase scraping to 3 pages for better content but with timeout
        try:
            scraped_results = await asyncio.wait_for(
                self._scrape_multiple_pages_optimized(filtered_urls), 
                timeout=12.0  # Increased for paid queries
            )
        except asyncio.TimeoutError:
            print("⚠️ Scraping timeout, using search snippets")
            scraped_results = []

        # Combine content efficiently with better error handling
        all_content = ""
        for result in scraped_results:
            if result and result.get("markdown"):
                all_content += result["markdown"][:1000] + "\n\n"  # Reduced from 1200 to 1000

        # If no content from scraping, use search results
        if not all_content.strip():
            print("⚠️ No scraped content, using search snippets")
            for result in search_results["data"][:3]:
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                if title or snippet:
                    all_content += f"Title: {title}\nDescription: {snippet}\n\n"

        # If still no content, fallback to query-based extraction
        if not all_content.strip():
            print("⚠️ No content available, extracting from query")
            tool_names = self._extract_tools_from_query(state.query)
            # For paid queries, ensure we have appropriate tools
            if "paid" in state.query.lower() or "premium" in state.query.lower():
                # Add some common paid tools if extraction is insufficient
                if len(tool_names) < 3:
                    # Check for specific categories and add relevant paid tools
                    if "test" in state.query.lower() or "testing" in state.query.lower():
                        paid_tools = ["Cypress", "TestCafe", "Sauce Labs", "BrowserStack", "CrossBrowserTesting", "LambdaTest"]
                    elif "javascript" in state.query.lower() or "js" in state.query.lower():
                        paid_tools = ["AWS Lambda", "Google Cloud Functions", "Azure Functions", "Heroku", "Vercel Pro"]
                    elif "python" in state.query.lower():
                        paid_tools = ["PythonAnywhere Pro", "Heroku", "AWS Lambda", "Google Cloud Functions", "Azure Functions"]
                    else:
                        paid_tools = ["AWS Lambda", "Google Cloud Functions", "Azure Functions", "Heroku", "Vercel Pro"]
                    tool_names.extend([t for t in paid_tools if t not in tool_names])
            self._cache_tools(cache_key, tool_names)
            return {"extracted_tools": tool_names}

        # Try LLM extraction with timeout and better error handling
        try:
            messages = [
                SystemMessage(content=self.prompts.TOOL_EXTRACTION_SYSTEM),
                HumanMessage(content=self.prompts.tool_extraction_user(state.query, all_content))
            ]

            # Add timeout to LLM call with retry logic
            response = await asyncio.wait_for(
                asyncio.get_running_loop().run_in_executor(
                    None, self.llm.invoke, messages
                ), 
                timeout=10.0  # Increased timeout for better reliability
            )
            tool_names = self._parse_llm_response(response.content)
            # Drop generic tokens that are not tools
            generic_tokens = {"monitoring","stack","alternatives","overview","guide","documentation","official","getting started"}
            tool_names = [t for t in tool_names if t.strip().lower() not in generic_tokens]
            # Contextual post-filtering based on query
            tool_names = self._filter_tools_by_query_context(state.query, tool_names)

            # Enforce category seeds when category detected to avoid cross-domain drift
            ql = state.query.lower()
            def ensure_category(tools: List[str]) -> List[str]:
                if any(w in ql for w in ["dast", "dynamic application security", "owasp zap", "burp", "nikto", "arachni", "w3af", "web app scanner"]):
                    seeds = ["OWASP ZAP", "Burp Suite", "Nikto", "Arachni", "w3af"]
                    return seeds + [t for t in tools if t not in seeds]
                if any(w in ql for w in ["api gateway", "apim", "kong", "apigee", "tyk", "mulesoft", "nginx plus", "traefik", "developer portal", "rate limiting"]):
                    seeds = ["Kong Enterprise", "Apigee", "Tyk", "MuleSoft Anypoint", "NGINX Plus", "Traefik Hub"]
                    return seeds + [t for t in tools if t not in seeds]
                if any(w in ql for w in ["error monitoring", "crash reporting", "sentry", "bugsnag", "rollbar", "new relic", "logrocket", "airbrake", "honeybadger"]):
                    seeds = ["Sentry", "Datadog", "Rollbar", "Bugsnag", "New Relic Errors Inbox"]
                    return seeds + [t for t in tools if t not in seeds]
                if any(w in ql for w in ["apm", "application performance monitoring", "tracing", "distributed tracing", "datadog", "new relic", "appdynamics", "elastic apm", "spans", "otel"]):
                    seeds = ["Datadog APM", "New Relic APM", "Elastic APM", "AppDynamics"]
                    return seeds + [t for t in tools if t not in seeds]
                return tools

            tool_names = ensure_category(tool_names)
            
            # Validate extracted tools with more lenient criteria
            if tool_names and len(tool_names) >= 1:  # Reduced from 2 to 1
                print(f"✅ LLM extracted tools: {', '.join(tool_names[:8])}")
                # Only enhance the list if we have fewer than 3 tools AND it's not a specific pricing query
                pricing_model = self._extract_pricing_model(state.query)
                if len(tool_names) < 3 and pricing_model == "any":
                    enhanced_tools = self._enhance_tool_list(tool_names, state.query)
                    tool_names = enhanced_tools
                elif len(tool_names) < 3 and pricing_model != "any":
                    # For specific pricing queries, only enhance with matching pricing tools
                    enhanced_tools = self._enhance_tool_list_by_pricing(tool_names, state.query, pricing_model)
                    tool_names = enhanced_tools
                self._cache_tools(cache_key, tool_names[:8])
                return {"extracted_tools": tool_names[:8]}
            else:
                print("⚠️ LLM extraction failed, using fallback")
                raise Exception("LLM extraction failed")
                
        except (asyncio.TimeoutError, Exception) as e:
            print(f"❌ Tool extraction error: {e}")
            # Enhanced fallback extraction
            tool_names = self._extract_tools_from_query(state.query)
            # Drop generic tokens again for fallback
            generic_tokens = {"monitoring","stack","alternatives","overview","guide","documentation","official","getting started"}
            tool_names = [t for t in tool_names if t.strip().lower() not in generic_tokens]
            tool_names = self._filter_tools_by_query_context(state.query, tool_names)
            # Enhance the fallback list only if not a specific pricing query
            pricing_model = self._extract_pricing_model(state.query)
            if len(tool_names) < 3 and pricing_model == "any":
                enhanced_tools = self._enhance_tool_list(tool_names, state.query)
                tool_names = enhanced_tools
            elif len(tool_names) < 3 and pricing_model != "any":
                enhanced_tools = self._enhance_tool_list_by_pricing(tool_names, state.query, pricing_model)
                tool_names = enhanced_tools
            self._cache_tools(cache_key, tool_names)
            return {"extracted_tools": tool_names}

    def _analyze_query_type(self, query: str) -> str:
        """Analyze the type of query to determine search strategy"""
        query_lower = query.lower()
        # Early category overrides (before language/pricing)
        if any(term in query_lower for term in [
            "dast", "dynamic application security testing", "owasp zap", "burp suite", "nikto", "arachni", "w3af", "web app scanner"
        ]):
            return "dast"
        if any(term in query_lower for term in [
            "api gateway", "api management", "apim", "kong", "apigee", "tyk", "mulesoft", "nginx plus", "traefik", "developer portal", "rate limiting"
        ]):
            return "apigateway"
        if any(term in query_lower for term in [
            "error monitoring", "crash reporting", "bug tracking", "sentry", "bugsnag", "rollbar", "new relic errors", "logrocket", "airbrake", "honeybadger"
        ]):
            return "errmon"
        if any(term in query_lower for term in [
            "apm", "application performance monitoring", "tracing", "distributed tracing", "datadog", "new relic", "appdynamics", "elastic apm", "spans", "otel"
        ]):
            return "apm"
        
        # CI/CD detection (define first)
        cicd_terms = [
            "ci/cd", "ci cd", "cicd", "pipeline", "pipelines", "continuous integration", "continuous delivery", "continuous deployment",
            "deploy", "deployment", "build pipeline", "release pipeline", "runner", "workflows", "yaml pipeline", "jenkins", "github actions",
            "gitlab ci", "circleci", "argo cd", "tekton", "travis", "bitbucket pipelines", "azure pipelines", "teamcity"
        ]
        
        # Check for language-specific queries first (before pricing) - but not if it's CI/CD
        if (not any(term in query_lower for term in cicd_terms) and 
            any(word in query_lower for word in ["java", "python", "javascript", "kotlin", "go", "rust", "c#", "csharp", "php", "ruby", "swift", "dart", "typescript", "scala", "clojure", "haskell", "elixir", "erlang", "c++", "cpp", "c", "objective-c", "objectivec", "r", "matlab", "perl", "lua", "assembly", "cobol", "fortran", "pascal", "ada", "prolog", "lisp", "scheme", "f#", "fsharp", "vb", "vb.net", "vbnet", "delphi", "pascal", "cobol", "fortran", "ada", "prolog", "lisp", "scheme", "f#", "fsharp", "vb", "vb.net", "vbnet", "delphi"])):
            return "specific_language"
        if any(term in query_lower for term in cicd_terms):
            return "cicd"
        # DevOps detection
        devops_terms = [
            "devops", "infrastructure as code", "iac", "observability", "monitoring", "alerting", "terraform", "ansible", "chef", "puppet",
            "docker", "kubernetes", "helm", "prometheus", "grafana", "argo", "flux", "sre"
        ]
        if any(t in query_lower for t in devops_terms):
            return "devops"
        # Check for specific qualifiers - enhanced pricing model detection
        elif any(word in query_lower for word in ["paid", "premium", "commercial", "enterprise", "subscription", "cost", "pricing", "license", "licensed"]):
            return "paid"
        elif any(word in query_lower for word in ["free", "open source", "opensource", "gratis", "no cost", "libre", "foss", "gpl", "mit", "apache", "bsd"]):
            return "free"
        elif any(word in query_lower for word in ["freemium", "trial", "demo", "limited", "basic", "pro", "premium", "upgrade"]):
            return "freemium"
        elif any(word in query_lower for word in ["web", "mobile", "desktop", "game", "ai", "ml", "data", "testing", "browser", "automation"]):
            return "specific_category"
        
        return "general"

    def _extract_pricing_model(self, query: str) -> str:
        """Extract the pricing model from the query"""
        query_lower = query.lower()
        
        # Check for specific pricing model keywords - order matters!
        # Check freemium first to avoid conflicts with "premium" being in both paid and freemium
        if any(word in query_lower for word in ["freemium", "trial", "demo", "limited", "basic", "upgrade"]):
            return "freemium"
        elif any(word in query_lower for word in ["open source", "opensource", "gratis", "no cost", "libre", "foss", "gpl", "mit", "apache", "bsd"]):
            return "free"
        elif any(word in query_lower for word in ["free"]) and not any(word in query_lower for word in ["freemium", "trial", "demo"]):
            return "free"
        elif any(word in query_lower for word in ["paid", "premium", "commercial", "enterprise", "subscription", "cost", "pricing", "license", "licensed"]):
            return "paid"
        
        return "any"

    def _cache_tools(self, cache_key: str, tools: List[str]):
        """Cache tools with size limit"""
        if len(self._tool_cache) >= self._max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self._tool_cache))
            del self._tool_cache[oldest_key]
        self._tool_cache[cache_key] = tools

    def _enhance_tool_list(self, tools: List[str], query: str) -> List[str]:
        """Enhance tool list by adding related tools based on query context"""
        enhanced = tools.copy()
        query_lower = query.lower()
        
        # Add more tools based on query context
        if "javascript" in query_lower and "test" in query_lower:
            testing_tools = ["Cypress", "TestCafe", "Sauce Labs", "BrowserStack", "CrossBrowserTesting", "LambdaTest", "Perfecto", "Experitest", "WebDriverIO", "Playwright"]
            for tool in testing_tools:
                if tool not in enhanced:
                    enhanced.append(tool)
        elif "python" in query_lower and "web" in query_lower:
            web_tools = ["Django", "Flask", "FastAPI", "Pyramid", "Tornado", "Bottle", "CherryPy", "Quart", "Sanic", "Starlette"]
            for tool in web_tools:
                if tool not in enhanced:
                    enhanced.append(tool)
        elif "react" in query_lower and "state" in query_lower:
            if "paid" in query_lower or "premium" in query_lower:
                state_tools = ["Redux Toolkit Pro", "MobX Pro", "Apollo Studio", "XState", "React Query Pro", "Zustand Pro", "Recoil Pro", "Jotai Pro"]
            else:
                state_tools = ["Redux", "Zustand", "MobX", "Recoil", "Jotai", "React Query", "Apollo Client", "XState"]
            for tool in state_tools:
                if tool not in enhanced:
                    enhanced.append(tool)
        
        # Limit to reasonable number for focused results
        return enhanced[:8]

    def _enhance_tool_list_by_pricing(self, tools: List[str], query: str, pricing_model: str) -> List[str]:
        """Enhance tool list with pricing-specific tools only"""
        enhanced = tools.copy()
        query_lower = query.lower()
        
        # Add tools based on pricing model and query context
        if pricing_model == "paid":
            if "javascript" in query_lower and "test" in query_lower:
                paid_testing_tools = ["Cypress", "TestCafe", "Sauce Labs", "BrowserStack", "CrossBrowserTesting", "LambdaTest"]
                for tool in paid_testing_tools:
                    if tool not in enhanced:
                        enhanced.append(tool)
            elif "python" in query_lower and "web" in query_lower:
                if "framework" in query_lower:
                    # Focus on web frameworks with commercial support available
                    paid_python_frameworks = ["Django", "Plone", "Flask", "Pyramid", "TurboGears", "web2py", "Zope", "Wagtail"]
                    for tool in paid_python_frameworks:
                        if tool not in enhanced:
                            enhanced.append(tool)
                else:
                    # General Python web tools (hosting)
                    paid_python_tools = ["PythonAnywhere Pro", "Heroku", "AWS Lambda", "Google Cloud Functions", "Azure Functions"]
                    for tool in paid_python_tools:
                        if tool not in enhanced:
                            enhanced.append(tool)
            elif "react" in query_lower and "state" in query_lower:
                paid_state_tools = ["Redux Toolkit Pro", "MobX Pro", "Apollo Studio"]
                for tool in paid_state_tools:
                    if tool not in enhanced:
                        enhanced.append(tool)
        elif pricing_model == "free":
            if "javascript" in query_lower and "test" in query_lower:
                free_testing_tools = ["Jest", "Mocha", "Chai", "Jasmine", "Vitest", "Playwright"]
                for tool in free_testing_tools:
                    if tool not in enhanced:
                        enhanced.append(tool)
            elif "python" in query_lower and "web" in query_lower:
                free_python_frameworks = ["Django", "Flask", "FastAPI", "Pyramid", "Tornado", "Bottle"]
                for tool in free_python_frameworks:
                    if tool not in enhanced:
                        enhanced.append(tool)
            elif "react" in query_lower and "state" in query_lower:
                free_state_tools = ["Redux", "Zustand", "MobX", "Recoil", "Jotai"]
                for tool in free_state_tools:
                    if tool not in enhanced:
                        enhanced.append(tool)
            elif any(word in query_lower for word in ["sql", "database", "databases"]):
                free_sql_tools = [
                    "PostgreSQL",
                    "MySQL",
                    "MariaDB",
                    "SQLite",
                    "CockroachDB",
                    "YugabyteDB"
                ]
                for tool in free_sql_tools:
                    if tool not in enhanced:
                        enhanced.append(tool)
        
        # Limit to reasonable number for focused results
        return enhanced[:8]

    def _extract_base_query(self, query: str) -> str:
        """Extract the base query without qualifiers"""
        query_lower = query.lower()
        
        # Remove common qualifiers - enhanced list
        qualifiers_to_remove = [
            "paid", "premium", "commercial", "enterprise", "subscription", "cost", "pricing", "license", "licensed",
            "free", "open source", "opensource", "gratis", "no cost", "libre", "foss", "gpl", "mit", "apache", "bsd",
            "freemium", "trial", "demo", "limited", "basic", "pro", "upgrade",
            "frameworks", "tools", "libraries", "for", "in", "and", "or", "the", "a", "an"
        ]
        
        words = query.split()
        filtered_words = [word for word in words if word.lower() not in qualifiers_to_remove]
        
        return " ".join(filtered_words).strip()

    def _extract_tools_from_query(self, query: str) -> List[str]:
        """Enhanced fallback tool extraction from query"""
        query_lower = query.lower()
        tools = []
        
        # Extract pricing model for this query
        pricing_model = self._extract_pricing_model(query)
        
        # Extract language-specific tools based on query
        # Prefer exact/word-boundary language matches to avoid 'java' matching 'javascript'
        import re as _re
        def _has_word(text: str, word: str) -> bool:
            return _re.search(rf"(^|[^a-zA-Z]){_re.escape(word)}([^a-zA-Z]|$)", text) is not None

        kubernetes_paid_tools = [
            "Kubecost Enterprise",
            "Rafay Kubernetes Management Platform",
            "Red Hat OpenShift",
            "SUSE Rancher Prime",
            "Mirantis Kubernetes Engine",
            "VMware Tanzu Kubernetes Grid",
            "Spectro Cloud Palette",
            "Nirmata Kubernetes Platform",
            "Platform9 Managed Kubernetes"
        ]

        if _has_word(query_lower, "kubernetes") and pricing_model == "paid":
            tools.extend(kubernetes_paid_tools)
        elif _has_word(query_lower, "javascript") or _has_word(query_lower, "js"):
            if pricing_model == "paid":
                # Check if it's specifically about testing frameworks
                if "test" in query_lower or "testing" in query_lower:
                    tools.extend(["Cypress", "TestCafe", "Sauce Labs", "BrowserStack", "CrossBrowserTesting", "LambdaTest", "Perfecto", "Experitest"])
                else:
                    tools.extend(["AWS Lambda", "Google Cloud Functions", "Azure Functions", "Heroku", "Vercel Pro", "Netlify Pro"])
            else:
                # Check for Express.js middleware specifically
                if "express" in query_lower and "middleware" in query_lower:
                    tools.extend([
                        "cors",
                        "helmet",
                        "morgan",
                        "body-parser",
                        "express-rate-limit",
                        "compression",
                        "cookie-parser",
                        "express-session"
                    ])
                else:
                    tools.extend(["React", "Vue", "Angular", "Next.js", "Nuxt.js", "Svelte", "Jest", "Mocha", "Chai"])
        elif _has_word(query_lower, "java"):
            if pricing_model == "paid":
                tools.extend(["IntelliJ IDEA Ultimate", "WebLogic", "JBoss", "Oracle JDK Commercial", "Spring Enterprise"])
            else:
                tools.extend(["Spring Boot", "Hibernate", "Struts", "JSF", "Vaadin", "Play Framework", "Maven", "Gradle", "JUnit", "Mockito"])
        elif _has_word(query_lower, "python"):
            if pricing_model == "paid":
                if "web" in query_lower and "framework" in query_lower:
                    # Focus on frameworks with commercial support/enterprise versions
                    tools.extend([
                        "Odoo Enterprise",
                        "Anvil",
                        "Taipy Enterprise",
                        "Dash Enterprise",
                        "Shiny for Python",
                        "Streamlit Cloud"
                    ])
                else:
                    # General paid Python tools (hosting, ML, etc.)
                    tools.extend(["Anaconda Enterprise", "DataRobot", "H2O.ai", "Databricks", "PythonAnywhere Pro", "Heroku", "AWS Lambda", "Google Cloud Functions", "Azure Functions"])
            else:
                tools.extend(["Django", "Flask", "FastAPI", "Pyramid", "Tornado", "Bottle", "PyTest", "unittest", "nose2", "Hypothesis"])
        elif _has_word(query_lower, "kotlin"):
            if pricing_model == "paid":
                tools.extend(["IntelliJ IDEA Ultimate", "Android Studio Pro", "Kotlin Multiplatform Mobile", "JetBrains Rider"])
            else:
                tools.extend(["Kotlin Multiplatform", "Ktor", "MockK", "Spek", "Spring Boot Kotlin", "Javalin", "Micronaut", "Quarkus"])
        elif _has_word(query_lower, "c#") or _has_word(query_lower, "csharp") or _has_word(query_lower, "dotnet") or _has_word(query_lower, ".net"):
            if pricing_model == "paid":
                tools.extend(["Visual Studio Professional", "ReSharper", "JetBrains Rider", ".NET Enterprise", "Telerik", "DevExpress"])
            else:
                tools.extend([".NET Core", "ASP.NET Core", "Entity Framework", "xUnit", "NUnit", "Moq", "Serilog", "AutoMapper", "FluentValidation"])
        elif _has_word(query_lower, "php"):
            if pricing_model == "paid":
                tools.extend(["Laravel Forge", "Envoyer", "Spark", "Zend Server", "PHPStorm", "New Relic", "Scout APM"])
            else:
                tools.extend(["Laravel", "Symfony", "CodeIgniter", "CakePHP", "PHPUnit", "Composer", "Twig", "Doctrine"])
        elif _has_word(query_lower, "ruby"):
            if pricing_model == "paid":
                tools.extend(["Heroku", "Engine Yard", "New Relic", "Scout APM", "RubyMine", "Pivotal Tracker"])
            else:
                tools.extend(["Rails", "Sinatra", "RSpec", "Minitest", "Capybara", "Puma", "Sidekiq", "Devise"])
        elif _has_word(query_lower, "go") or _has_word(query_lower, "golang"):
            if pricing_model == "paid":
                tools.extend(["Google Cloud Run", "AWS Lambda", "DigitalOcean App Platform", "Heroku", "Vercel Pro"])
            else:
                # Focus on web frameworks, not testing frameworks
                if "web" in query_lower or "framework" in query_lower:
                    tools.extend(["Gin", "Echo", "Fiber", "Chi", "Gorilla Mux", "Beego", "Revel", "Buffalo"])
                else:
                    tools.extend(["Gin", "Echo", "Fiber", "Testify", "Gorilla Mux", "Cobra", "Viper"])
        elif _has_word(query_lower, "rust"):
            if pricing_model == "paid":
                tools.extend(["AWS Lambda", "Google Cloud Run", "Azure Functions", "Heroku", "DigitalOcean"])
            else:
                tools.extend(["Actix", "Rocket", "Tokio", "Serde", "Cargo", "Clap", "Diesel", "SeaORM"])
        elif _has_word(query_lower, "c++") or _has_word(query_lower, "cpp"):
            if pricing_model == "paid":
                tools.extend(["Visual Studio Professional", "Intel C++ Compiler", "Qt Commercial", "Perforce", "PVS-Studio"])
            else:
                tools.extend(["Boost", "Qt Open Source", "Google Test", "Catch2", "CMake", "Conan", "vcpkg", "spdlog"])
        elif _has_word(query_lower, "swift"):
            if pricing_model == "paid":
                tools.extend(["Xcode Pro", "AppCode", "Realm Studio", "Firebase", "Crashlytics"])
            else:
                tools.extend(["SwiftUI", "UIKit", "Combine", "Alamofire", "SnapKit", "Quick", "Nimble", "RxSwift"])
        elif _has_word(query_lower, "dart"):
            if pricing_model == "paid":
                tools.extend(["Firebase", "Google Cloud", "AWS Amplify", "Supabase Pro"])
            else:
                tools.extend(["Flutter", "AngularDart", "Aqueduct", "Angel", "Shelf", "Test", "Mockito"])
        elif _has_word(query_lower, "kubernetes") or _has_word(query_lower, "k8s"):
            # Kubernetes ecosystem tools
            tools.extend(["kubectl", "Helm", "Kustomize", "Argo CD", "Flux", "KEDA", "Istio", "Linkerd", "Prometheus", "Grafana", "Skaffold", "Tilt", "Lens"])
        elif any(_has_word(query_lower, w) for w in [
            "ml", "machine learning", "deep learning", "ai", "tensorflow", "pytorch", "scikit" ]):
            # Machine learning libraries
            tools.extend([
                "TensorFlow", "PyTorch", "Scikit-learn", "Keras",
                "XGBoost", "LightGBM", "CatBoost", "Hugging Face Transformers"
            ])
        elif any(_has_word(query_lower, w) for w in ["sql", "database", "databases", "postgres", "mysql", "sqlite", "mariadb", "oracle", "sql server"]):
            # SQL/relational databases
            tools.extend(["PostgreSQL", "MySQL", "MariaDB", "SQLite", "SQL Server", "Oracle Database", "CockroachDB", "YugabyteDB", "Amazon Aurora"])
        elif _has_word(query_lower, "web"):
            if pricing_model == "paid":
                tools.extend(["Bright Data", "ScrapingBee", "Apify", "ScraperAPI", "ProxyMesh", "Smartproxy"])
            else:
                tools.extend(["React", "Vue", "Angular", "Django", "Flask", "Express"])
        # DevOps queries (broad): include CI/CD, IaC, containers, monitoring
        devops_terms = [
            "devops", "infrastructure as code", "iac", "observability", "monitoring", "alerting", "terraform", "ansible", "chef", "puppet",
            "docker", "kubernetes", "helm", "prometheus", "grafana", "argo", "flux", "sre"
        ]
        if any(t in query_lower for t in devops_terms):
            tools = [
                # CI/CD
                "GitHub Actions", "GitLab CI", "Jenkins", "CircleCI",
                # IaC / Config
                "Terraform", "Ansible", "Pulumi", "Puppet", "Chef",
                # Containers / Orchestration
                "Docker", "Kubernetes", "Helm",
                # GitOps / CD
                "Argo CD", "Flux",
                # Observability
                "Prometheus", "Grafana"
            ]
            # Light pricing ordering
            if pricing_model == "free":
                tools = [
                    "GitHub Actions", "GitLab CI", "Jenkins", "Terraform", "Ansible", "Docker", "Kubernetes", "Helm", "Argo CD", "Flux", "Prometheus", "Grafana", "CircleCI", "Puppet", "Chef"
                ]
            elif pricing_model == "paid":
                tools = [
                    "CircleCI", "Puppet", "Chef", "Terraform", "Ansible", "GitHub Actions", "GitLab CI", "Jenkins", "Docker", "Kubernetes", "Helm", "Argo CD", "Flux", "Prometheus", "Grafana"
                ]
        # CI/CD pipelines and systems - ensure this takes priority
        cicd_terms = [
            "ci/cd", "ci cd", "cicd", "pipeline", "pipelines", "continuous integration", "continuous delivery", "continuous deployment",
            "deploy", "deployment", "build pipeline", "release pipeline", "runner", "workflows", "jenkins", "github actions", "gitlab ci",
            "circleci", "argo cd", "tekton", "travis", "bitbucket pipelines", "azure pipelines", "teamcity"
        ]
        if any(t in query_lower for t in cicd_terms):
            tools = [
                "GitHub Actions", "GitLab CI", "CircleCI", "Jenkins", "Argo CD", "Tekton", "Travis CI", "Bitbucket Pipelines", "Azure Pipelines", "TeamCity"
            ]
            # Apply pricing model soft preference by ordering
            if pricing_model == "free":
                tools = ["GitHub Actions", "GitLab CI", "Jenkins", "Tekton", "Argo CD", "Bitbucket Pipelines", "Azure Pipelines", "CircleCI", "Travis CI", "TeamCity"]
            elif pricing_model == "paid":
                tools = ["CircleCI", "Travis CI", "TeamCity", "Azure Pipelines", "Bitbucket Pipelines", "GitHub Actions", "GitLab CI", "Jenkins", "Argo CD", "Tekton"]
            return tools[:8]  # Return immediately to prevent other logic from overriding
        elif _has_word(query_lower, "mobile"):
            tools.extend(["React Native", "Flutter", "Xamarin", "Ionic", "Cordova"])
        elif _has_word(query_lower, "testing") or _has_word(query_lower, "test"):
            if "c++" in query_lower or "cpp" in query_lower:
                tools.extend(["Google Test", "Catch2", "Boost.Test", "CppUnit", "CppUTest", "doctest"])
            elif _has_word(query_lower, "javascript") or _has_word(query_lower, "js") or _has_word(query_lower, "react"):
                tools.extend(["Jest", "Mocha", "Chai", "Jasmine", "Cypress", "Vitest", "Playwright"])
            elif _has_word(query_lower, "python"):
                tools.extend(["PyTest", "unittest", "nose2", "Hypothesis", "Behave", "tox"])
            elif _has_word(query_lower, "java"):
                tools.extend(["JUnit", "TestNG", "Mockito", "AssertJ", "Cucumber", "Selenium"])
            else:
                tools.extend(["Jest", "Mocha", "JUnit", "PyTest", "Selenium", "Cypress"])
        elif _has_word(query_lower, "ai") or _has_word(query_lower, "ml"):
            if pricing_model == "paid":
                tools.extend(["IBM Watson", "Amazon SageMaker", "Google Cloud AI", "Microsoft Azure ML", "DataRobot", "H2O.ai", "Databricks", "Anaconda Enterprise"])
            else:
                tools.extend(["TensorFlow", "PyTorch", "Scikit-learn", "Keras", "OpenAI", "Hugging Face"])
        elif _has_word(query_lower, "c++") or _has_word(query_lower, "cpp"):
            # Very specific C++ tools to avoid irrelevant results
            if "web" in query_lower:
                tools.extend(["CppCMS", "Crow", "Pistache", "Qt WebEngine", "Drogon"])
            elif "gui" in query_lower or "desktop" in query_lower:
                tools.extend(["Qt", "wxWidgets", "FLTK", "GTK+", "Dear ImGui"])
            elif "game" in query_lower:
                tools.extend(["Unreal Engine", "Godot", "Irrlicht", "Ogre3D", "SFML"])
            else:
                tools.extend(["Qt C++ Framework", "STL C++ Standard Library", "Eigen C++ Linear Algebra", "OpenCV C++ Computer Vision", "Poco C++ Libraries", "Unreal Engine C++"])
        elif _has_word(query_lower, "c#") or _has_word(query_lower, "csharp"):
            tools.extend([".NET", "ASP.NET Core", "Entity Framework", "Xamarin", "Unity"])
        elif _has_word(query_lower, "go") or _has_word(query_lower, "golang"):
            tools.extend(["Gin", "Echo", "Fiber", "Chi", "Gorilla Mux", "Beego"])
        elif _has_word(query_lower, "rust"):
            tools.extend(["Actix", "Rocket", "Warp", "Axum", "Tokio", "Serde"])
        elif _has_word(query_lower, "ruby"):
            if pricing_model == "paid":
                tools.extend(["RubyMine", "JetBrains RubyMine", "Ruby Enterprise Edition", "RubyMotion", "Appcelerator Ruby"])
            else:
                tools.extend(["Ruby on Rails", "Sinatra", "Hanami", "Padrino", "Cuba", "RSpec"])
        elif "swiftui" in query_lower:
            if pricing_model == "paid":
                tools.extend([
                    "Supernova",
                    "SwiftUI Starter Kit",
                    "SwiftUI Pro Kit",
                    "Design+Code SwiftUI",
                    "Shape of SwiftUI"
                ])
            else:
                tools.extend([
                    "SwiftUIX",
                    "SwiftUI Charts",
                    "SwiftUI Layout Library",
                    "SwiftUI Components",
                    "SwiftUI Templates"
                ])
        elif _has_word(query_lower, "swift"):
            if pricing_model == "paid":
                tools.extend(["Xcode Pro", "AppCode", "Realm Studio", "Firebase", "Crashlytics"])
            else:
                tools.extend(["SwiftUI", "UIKit", "Combine", "Alamofire", "SnapKit", "Quick", "Nimble", "RxSwift"])

        # React state management explicit fallback
        if _has_word(query_lower, "react") and _has_word(query_lower, "state"):
            if _has_word(query_lower, "paid") or _has_word(query_lower, "premium"):
                tools = ["Redux Toolkit Pro", "MobX Pro", "Apollo Studio", "XState", "React Query Pro", "Zustand Pro", "Recoil Pro", "Jotai Pro"]
            else:
                tools = ["Redux", "Zustand", "MobX", "Recoil", "Jotai", "React Query"]
        # Swift testing explicit allowlist fallback
        if _has_word(query_lower, "swift") and (_has_word(query_lower, "test") or _has_word(query_lower, "testing")):
            tools = ["XCTest", "Quick", "Nimble", "SnapshotTesting", "SwiftLint", "OHHTTPStubs", "SwiftCheck", "Cuckoo", "Mockingbird"]
        
        # Enhanced filtering based on pricing model - be more strict for paid queries
        pricing_model = self._extract_pricing_model(query)
        
        if pricing_model == "paid":
            # Focus ONLY on tools with commercial support/enterprise options available
            paid_tools = [
                # Python web frameworks with commercial/enterprise offerings
                "Odoo Enterprise",
                "Anvil",
                "Taipy Enterprise",
                "Dash Enterprise",
                "Shiny for Python",
                "Streamlit Cloud",
                "Enthought Canopy",
                "Divio",
                "Appsmith Enterprise",
                "Masonite Pro",
                # Python hosting / platform services
                "PythonAnywhere Pro", "Heroku", "AWS Lambda", "Google Cloud Functions", "Azure Functions",
                # Paid testing/DevOps tools
                "Cypress", "TestCafe", "Sauce Labs", "BrowserStack", "CrossBrowserTesting", "LambdaTest",
                "Perfecto", "Experitest",
                # Paid IDE / platform tooling
                "Visual Studio Professional", "Visual Studio Enterprise", "IntelliJ IDEA Ultimate",
                "JetBrains Rider", "ReSharper",
                # Java EE / middleware
                "WebLogic", "JBoss", "Oracle JDK Commercial", "Spring Enterprise",
                # Data/ML platforms
                "Anaconda Enterprise", "DataRobot", "H2O.ai", "Databricks", "Snowflake", "Tableau",
                # Observability / monitoring
                "New Relic", "Datadog",
                # Web scraping services
                "Bright Data", "ScrapingBee", "Apify", "ScraperAPI", "ProxyMesh", "Smartproxy",
                # Paid state-management/React ecosystem
                "Redux Toolkit Pro", "MobX Pro", "Apollo Studio", "Relay",
                # Paid SwiftUI kits
                "Supernova", "SwiftUI Starter Kit", "SwiftUI Pro Kit", "Design+Code SwiftUI", "Shape of SwiftUI"
            ]
            # For paid queries, only include tools that have commercial support options
            # Note: Django, Flask, Pyramid etc. are included because they have commercial support available
            tools = [tool for tool in tools if tool in paid_tools]
        elif pricing_model == "free":
            # Focus on open source/free tools
            free_tools = ["Django", "Flask", "FastAPI", "Pyramid", "Tornado", "Bottle", "React", "Vue", "Angular", "Jest", "Mocha", "Chai", "Jasmine", "Scrapy", "Selenium", "Puppeteer", "Playwright", "Beautiful Soup", "Redux", "Zustand", "MobX", "Recoil", "Jotai", "PostgreSQL", "Redis", "Docker", "GitHub", "Visual Studio Code", "VS Code", "Visual Studio Community"]
            tools = [tool for tool in tools if tool in free_tools or any(open_source in tool.lower() for open_source in ["open", "free", "community", "foss"])]
        elif pricing_model == "freemium":
            # Focus on freemium tools
            freemium_tools = ["Slack", "Discord", "Notion", "Figma", "Canva", "Spotify", "Dropbox", "Zoom", "Trello", "Asana"]
            tools = [tool for tool in tools if tool in freemium_tools or any(freemium in tool.lower() for freemium in ["trial", "demo", "basic", "pro"])]
        
        # Ensure we have enough tools but respect pricing model
        if len(tools) < 3:
            if pricing_model == "paid":
                if "kubernetes" in query_lower:
                    general_paid_tools = kubernetes_paid_tools
                elif "framework" in query.lower() and "python" in query.lower():
                    general_paid_tools = [
                        "Odoo Enterprise",
                        "Anvil",
                        "Taipy Enterprise",
                        "Dash Enterprise",
                        "Shiny for Python",
                        "Streamlit Cloud",
                        "Enthought Canopy",
                        "Divio"
                    ]
                else:
                    general_paid_tools = ["Heroku", "AWS Lambda", "Google Cloud Functions", "Azure Functions"]
                tools.extend(general_paid_tools[:3 - len(tools)])
            elif pricing_model == "free":
                general_free_tools = ["GitHub", "VS Code", "Docker", "PostgreSQL", "MongoDB", "Redis"]
                tools.extend(general_free_tools[:3 - len(tools)])
            else:
                general_tools = ["GitHub", "VS Code", "Docker", "PostgreSQL", "MongoDB", "Redis"]
                tools.extend(general_tools[:3 - len(tools)])
        
        return tools[:8]

    def _parse_llm_response(self, response: str) -> List[str]:
        """Parse LLM response and extract tool names"""
        tool_names = []
        for line in response.strip().split("\n"):
            # Remove numbers, dots, asterisks, and clean up
            cleaned = re.sub(r'^\d+\.\s*', '', line.strip())  # Remove "1. ", "2. " etc
            cleaned = re.sub(r'^\-\s*', '', cleaned)  # Remove "- "
            cleaned = re.sub(r'^\*\s*', '', cleaned)  # Remove "* "
            cleaned = re.sub(r'[^\w\s\.\-]', '', cleaned)  # Remove special chars except dots and dashes
            cleaned = cleaned.strip()
            
            # Filter out empty strings, very short names, and numbers
            if cleaned and len(cleaned) > 2 and not cleaned.isdigit() and cleaned.lower() not in ['the', 'and', 'or', 'for', 'with', 'tool', 'tools']:
                                    # Check if it looks like a real tool name (not explanatory text)
                    if len(cleaned) < 50 and not any(word in cleaned.lower() for word in ['article', 'content', 'provided', 'explicitly', 'mention', 'specific']):
                        # Additional filtering for irrelevant results
                        if not self._is_irrelevant_tool(cleaned):
                            tool_names.append(cleaned)
        
        return tool_names

    def _filter_tools_by_query_context(self, query: str, tools: List[str]) -> List[str]:
        """Filter extracted tools using the query context to avoid cross-language/tool collisions"""
        q = query.lower()
        filtered: List[str] = []
        for t in tools:
            tl = t.lower()
            # React state management queries: keep only state management tools, not UI libraries
            if ("react" in q) and ("state" in q) and ("management" in q):
                state_allow = [
                    "redux", "zustand", "mobx", "recoil", "jotai", "react query", 
                    "apollo client", "xstate", "context", "unstated", "easy-peasy"
                ]
                if any(a == tl or a in tl for a in state_allow):
                    filtered.append(t)
                continue
            # Exclude UI libraries for React state management queries
            if ("react" in q) and ("state" in q) and ("management" in q):
                if any(ui == tl or ui in tl for ui in ["chakra ui", "tailwind ui", "react bootstrap", "material-ui", "ant design", "semantic ui", "blueprint"]):
                    continue
            # Kotlin testing queries: keep only Kotlin-specific testing ecosystem tools
            if ("kotlin" in q) and ("test" in q or "testing" in q):
                kotlin_allow = [
                    "mockk", "kotest", "kotlintest", "spek", "kluent",
                    "atrium", "mockative", "testcontainers"
                ]
                if any(a == tl or a in tl for a in kotlin_allow):
                    filtered.append(t)
                continue
            # Kotlin framework queries: keep only Kotlin ecosystem frameworks/libraries
            if ("kotlin" in q) and ("framework" in q):
                kotlin_framework_allow = [
                    "ktor", "kotlin multiplatform", "kvision", "mockk",
                    "spek", "spring boot", "spring boot kotlin", "micronaut",
                    "quarkus", "javalin", "koin", "arrow", "jetpack compose",
                    "ktor server", "ktor client", "kotlinx.serialization", "ktor http"
                ]
                if any(a == tl or a in tl for a in kotlin_framework_allow):
                    filtered.append(t)
                continue
            if ("kotlin" in q) and ("framework" in q) and any(bad in tl for bad in ["radiation", "compensation", "reca", "exposure", "atomic", "dtra"]):
                continue
            # Paid Python web frameworks queries: keep only frameworks with commercial offerings
            if ("paid" in q) and ("python" in q) and ("web" in q) and ("framework" in q):
                paid_python_allow = [
                    "odoo", "odoo enterprise", "anvil", "taipy", "dash enterprise",
                    "plotly dash", "shiny", "streamlit", "enthought", "divio",
                    "appsmith", "masonite", "radon", "webware"
                ]
                if any(a in tl for a in paid_python_allow):
                    filtered.append(t)
                continue
            # Swift testing queries: keep only Swift testing ecosystem tools
            if ("swift" in q) and ("test" in q or "testing" in q):
                swift_allow = [
                    "xctest", "quick", "nimble", "snapshottesting", "snapshot testing", "swiftlint",
                    "ohhttpstubs", "mockingbird", "cuckoo", "swiftcheck"
                ]
                if any(a == tl or a in tl for a in swift_allow):
                    filtered.append(t)
                continue
            # JavaScript frameworks should be excluded for Swift testing context
            if ("swift" in q) and ("test" in q or "testing" in q):
                if any(js == tl or js in tl for js in ["react", "jest", "playwright", "storybook", "docusaurus", "cuckoo sandbox", "nimble-arduino"]):
                    continue
            # Kubernetes-specific filters: keep known K8s tools
            if ("kubernetes" in q or "k8s" in q):
                k8s_allow = [
                    "kubectl","helm","kustomize","argo cd","argo","flux","keda","istio","linkerd",
                    "prometheus","grafana","skaffold","tilt","lens","k9s","cert-manager","traefik","nginx ingress"
                ]
                if any(a == tl or a in tl for a in k8s_allow):
                    filtered.append(t)
                continue
            # SQL/Databases-specific filters: keep known SQL RDBMS
            if any(tok in q for tok in ["sql","database","databases","postgres","mysql","sqlite","mariadb","oracle","sql server"]):
                db_allow = [
                    "postgresql","mysql","mariadb","sqlite","sql server","microsoft sql server","oracle","oracle database",
                    "cockroachdb","yugabytedb","amazon aurora","aws aurora"
                ]
                if any(a == tl or a in tl for a in db_allow):
                    filtered.append(t)
                continue
            # C++ testing queries: keep only known C++ frameworks
            if ("c++" in q or "cpp" in q) and ("test" in q or "testing" in q):
                allowed = ["googletest", "google test", "gtest", "catch2", "boost.test", "cppunit", "cpputest", "doctest"]
                if any(a in tl for a in allowed):
                    filtered.append(t)
                continue
            # React queries: avoid Flutter/pub.dev or unrelated ecosystems
            if "react" in q and ("flutter" in tl or "pub.dev" in tl):
                continue
            # JS testing: ensure Chai maps to the assertion library, not builders
            if ("javascript" in q or "js" in q) and ("test" in q or "testing" in q):
                if tl == "chai" or "chai" in tl:
                    filtered.append("Chai")
                    continue
            # Generic JS testing: if query doesn't mention React, drop React-only testing tools
            if ("javascript" in q or "js" in q) and ("test" in q or "testing" in q) and ("react" not in q):
                react_only = [
                    "enzyme",
                    "react testing library",
                    "react-test-renderer",
                    "testing-library/react",
                    "rtl"
                ]
                if any(ro == tl or ro in tl for ro in react_only) or tl.startswith("react"):
                    continue
            # Go web frameworks: exclude testing frameworks when looking for web frameworks
            if ("go" in q or "golang" in q) and ("web" in q or "framework" in q):
                go_testing_tools = ["ginkgo", "testify", "gomega", "goconvey"]
                if any(test_tool == tl or test_tool in tl for test_tool in go_testing_tools):
                    continue
            # Express middleware queries: keep known middleware packages
            if ("express" in q) and ("middleware" in q):
                express_middleware_allow = {
                    "cors", "helmet", "morgan", "body-parser",
                    "express-rate-limit", "compression", "cookie-parser",
                    "express-session", "multer", "csurf", "passport",
                    "connect-timeout", "response-time", "serve-static"
                }
                if tl in express_middleware_allow:
                    filtered.append(t)
                continue
            # SwiftUI component queries: prefer SwiftUI-centric libraries and drop unrelated platforms
            if "swiftui" in q:
                swiftui_allow = {
                    "supernova", "swiftui starter kit", "swiftui pro kit",
                    "design+code swiftui", "shape of swiftui",
                    "swiftuix", "swiftui charts", "swiftui layout library",
                    "swiftui components", "swiftui templates"
                }
                if tl in swiftui_allow:
                    filtered.append(t)
                continue
            filtered.append(t)
        # De-duplicate while preserving order
        seen: set = set()
        out: List[str] = []
        for t in filtered:
            if t.lower() not in seen:
                seen.add(t.lower())
                out.append(t)
        return out

    def _filter_companies_by_context(self, query: str, companies: List[CompanyInfo]) -> List[CompanyInfo]:
        """Filter analyzed companies by query context (e.g., avoid React-only libs for generic JS testing)."""
        q = (query or "").lower()
        if not companies:
            return companies
        out: List[CompanyInfo] = []
        for c in companies:
            name_l = (getattr(c, "name", "") or "").lower()
            # DAST context: keep only known DAST tools
            if any(w in q for w in ["dast", "dynamic application security", "owasp zap", "burp", "nikto", "arachni", "w3af", "web app scanner"]):
                allowed = ["owasp zap", "burp", "burp suite", "nikto", "arachni", "w3af"]
                if not any(a in name_l for a in allowed):
                    continue
            # API gateway context: keep only API gateway vendors
            if any(w in q for w in ["api gateway", "apim", "kong", "apigee", "tyk", "mulesoft", "nginx plus", "traefik", "developer portal", "rate limiting"]):
                allowed = ["kong", "apigee", "tyk", "mulesoft", "nginx", "traefik"]
                if not any(a in name_l for a in allowed):
                    continue
            # Kotlin testing context: keep Kotlin-first testing libraries
            if ("kotlin" in q) and ("test" in q or "testing" in q):
                allowed = ["mockk", "kotest", "kotlintest", "spek", "kluent", "atrium", "mockative", "testcontainers"]
                if not any(a in name_l for a in allowed):
                    continue
            # Error monitoring context
            if any(w in q for w in ["error monitoring", "crash reporting", "sentry", "bugsnag", "rollbar", "new relic", "logrocket", "airbrake", "honeybadger", "trackjs", "appsignal", "raygun"]):
                allowed = ["sentry", "bugsnag", "rollbar", "new relic", "logrocket", "airbrake", "honeybadger", "trackjs", "appsignal", "raygun", "datadog"]
                if not any(a in name_l for a in allowed):
                    continue
            # APM context
            if any(w in q for w in ["apm", "application performance monitoring", "datadog", "new relic", "appdynamics", "elastic apm", "tracing"]):
                allowed = ["datadog", "new relic", "appdynamics", "elastic"]
                if not any(a in name_l for a in allowed):
                    continue
            # If JavaScript testing query and no React in query, drop React-specific testing tools
            if (("javascript" in q or "js" in q) and ("test" in q or "testing" in q) and ("react" not in q)):
                if ("enzyme" in name_l) or ("react testing library" in name_l) or (name_l.startswith("react ")):
                    continue
            # Express middleware context: keep only known middleware packages
            if ("express" in q) and ("middleware" in q):
                allowed = [
                    "cors",
                    "helmet",
                    "morgan",
                    "body-parser",
                    "express-rate-limit",
                    "compression",
                    "cookie-parser",
                    "express-session",
                    "multer",
                    "csurf",
                    "passport",
                    "connect-timeout",
                    "response-time",
                    "serve-static"
                ]
                if not any(a in name_l for a in allowed):
                    continue
            # SwiftUI component context: favor SwiftUI-specific kits
            if "swiftui" in q:
                swiftui_allowed = [
                    "supernova",
                    "swiftui starter kit",
                    "swiftui pro kit",
                    "design+code swiftui",
                    "shape of swiftui",
                    "swiftuix",
                    "swiftui charts",
                    "swiftui layout library",
                    "swiftui components",
                    "swiftui templates"
                ]
                if not any(a in name_l for a in swiftui_allowed):
                    continue
            out.append(c)
        return out

    def _is_irrelevant_tool(self, tool_name: str) -> bool:
        """Check if a tool name is irrelevant and should be filtered out"""
        tool_lower = tool_name.lower()
        
        # Filter out government/agency names and abbreviations
        government_indicators = [
            'division', 'department', 'bureau', 'agency', 'commission', 'office',
            'water resources', 'colorado', 'gov', 'government', 'county', 'state',
            'federal', 'municipal', 'city', 'town', 'village', 'dwr', 'dwra'
        ]
        
        if any(indicator in tool_lower for indicator in government_indicators):
            return True
        
        # Filter out non-developer tools
        non_developer_indicators = [
            'water', 'resources', 'management', 'environmental', 'natural',
            'conservation', 'wildlife', 'forestry', 'agriculture', 'mining',
            'real estate', 'property', 'insurance', 'banking', 'finance'
        ]
        
        if any(indicator in tool_lower for indicator in non_developer_indicators):
            return True
        
        # Filter out generic terms that aren't actual tools
        generic_terms = [
            'standard library', 'template library', 'c standard library',
            'apache c standard library', 'standard template library'
        ]
        
        if any(term in tool_lower for term in generic_terms):
            return True
        
        # Filter out very short names that could be abbreviations for irrelevant things
        if len(tool_name) <= 3 and tool_lower not in ['qt', 'stl', 'api', 'orm', 'mvc', 'jsp', 'jpa', 'jdbc']:
            return True
        
        # Filter out similarly named tools that aren't the real C++ libraries
        # Filter out Boost.space (business platform) vs Boost C++ library
        if tool_lower == "boost" and "space" in tool_lower:
            return True
        # Filter out just "boost" if it's likely to be boost.space
        # Allow Boost as a legitimate C++ library; Boost.space is already filtered by name
        # Filter out SGI STL (old implementation) vs standard C++ STL
        if "sgi" in tool_lower and "stl" in tool_lower:
            return True
        # Filter out any tool with "space" in the name for C++ queries
        if "space" in tool_lower and ("c++" in tool_lower or "cpp" in tool_lower):
            return True
        
        # Filter out AWS/cloud tools that aren't C++ libraries
        if any(cloud in tool_lower for cloud in ["aws", "amazon", "microsoft", "azure", "google cloud", "rest sdk", "sdk for net", "docs.boost.space"]):
            return True
        
        # Filter out obscure/niche C++ tools that aren't mainstream
        obscure_cpp = ["copperspice", "cs_libguarded", "libguarded", "guarded"]
        if any(obscure in tool_lower for obscure in obscure_cpp):
            return True
        
        # Filter out tools that don't look like C++ libraries
        if "c++" in tool_lower or "cpp" in tool_lower:
            # Must contain actual C++ library names
            valid_cpp_libs = ["boost", "qt", "stl", "eigen", "opencv", "poco", "unreal", "godot", "fltk", "gtk", "wxwidgets"]
            if not any(lib in tool_lower for lib in valid_cpp_libs):
                return True
        
        # Additional C++ specific filtering
        if "c++" in tool_lower or "cpp" in tool_lower:
            # Filter out non-C++ tools that might be confused
            non_cpp_indicators = ["unity", "cmock", "ceedling", "python", "ruby", "javascript", "java", "c#", "dotnet"]
            if any(indicator in tool_lower for indicator in non_cpp_indicators):
                return True
            
            # Must contain actual C++ library names or be clearly C++ related
            cpp_keywords = ["boost", "qt", "stl", "eigen", "opencv", "poco", "unreal", "godot", "fltk", "gtk", "wxwidgets", "cpp", "c++"]
            if not any(keyword in tool_lower for keyword in cpp_keywords):
                return True
        
        return False

    def _research_step(self, state: ResearchState) -> Dict[str, Any]:
        # Handle async execution within sync context
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._research_async(state))
                    return future.result()
        except RuntimeError:
            # No running loop in this thread
            pass
        return asyncio.run(self._research_async(state))

    async def _research_async(self, state: ResearchState) -> Dict[str, Any]:
        start_time = time.time()
        extracted_tools = getattr(state, "extracted_tools", [])
        
        if not extracted_tools:
            tool_names = [word for word in state.query.split() if len(word) > 3][:6]
        else:
            # Use extracted tools but cap to 8 for more focused and accurate results
            tool_names = extracted_tools[:8]

        # Reorder for DevOps to prioritize faster/less rate-limited sources first
        try:
            qlower = state.query.lower()
            devops_terms = [
                "devops", "infrastructure as code", "iac", "observability", "monitoring", "alerting", "terraform", "ansible", "chef", "puppet",
                "docker", "kubernetes", "helm", "prometheus", "grafana", "argo", "flux", "sre"
            ]
            if any(t in qlower for t in devops_terms):
                priority_order = ["docker", "kubernetes", "prometheus", "grafana", "ansible", "terraform"]
                def _rank(name: str) -> int:
                    n = (name or "").lower()
                    for i, p in enumerate(priority_order):
                        if p in n:
                            return i
                    return len(priority_order) + 1
                tool_names = sorted(tool_names, key=_rank)
            # K8s-specific: prefer GitOps/cluster-native first
            if ("kubernetes" in qlower) or ("k8s" in qlower):
                k8s_priority = ["argo cd", "flux", "tekton", "kubectl", "helm", "kubernetes", "prometheus", "grafana", "docker"]
                def _k8s_rank(name: str) -> int:
                    n = (name or "").lower()
                    for i, p in enumerate(k8s_priority):
                        if p in n:
                            return i
                    return len(k8s_priority) + 1
                tool_names = sorted(tool_names, key=_k8s_rank)
        except Exception:
            pass

        # Context hard-filter for Swift testing: keep only Swift testing tools
        qlower = state.query.lower()
        if ("swift" in qlower) and ("test" in qlower or "testing" in qlower):
            swift_allow_exact = {
                "xctest", "quick", "nimble", "snapshottesting", "snapshot testing",
                "swiftlint", "ohhttpstubs", "mockingbird", "cuckoo", "swiftcheck"
            }
            tool_names = [t for t in tool_names if t.lower() in swift_allow_exact]

        print(f"🔬 Researching specific tools: {', '.join(tool_names)}")

        # Research each tool concurrently and update partials as each finishes
        companies: List[CompanyInfo] = []
        try:
            semaphore = asyncio.Semaphore(3)  # Reduced to 3 to avoid overwhelming APIs

            async def research_and_analyze(tool_name: str) -> CompanyInfo:
                async with semaphore:
                    try:
                        research_result = await asyncio.wait_for(
                            self._smart_company_research_optimized(tool_name),
                            timeout=25.0  # Increased timeout for better success rate
                        )
                        if isinstance(research_result, dict) and research_result.get("markdown"):
                            source_url = research_result.get("url")
                            analysis = await self._analyze_company_content_optimized(
                                tool_name,
                                research_result.get("markdown", ""),
                                source_url,
                                state.query,
                            )
                            print(f"✅ Successfully analyzed {tool_name}")
                            return analysis if analysis and getattr(analysis, "name", "").strip() else CompanyInfo(
                                name=tool_name,
                                description=f"{tool_name} - Developer tool",
                                website=f"https://{tool_name.lower().replace(' ', '')}.com"
                            )
                        elif isinstance(research_result, Exception):
                            print(f"❌ Research failed for {tool_name}: {research_result}")
                            return CompanyInfo(
                                name=tool_name,
                                description=f"Research failed for {tool_name}",
                                website=f"https://{tool_name.lower().replace(' ', '')}.com"
                            )
                        else:
                            print(f"⚠️ No content found for {tool_name}")
                            return CompanyInfo(
                                name=tool_name,
                                description=f"{tool_name} - Developer tool (limited information)",
                                website=f"https://{tool_name.lower().replace(' ', '')}.com"
                            )
                    except asyncio.CancelledError:
                        print(f"⏰ Task cancelled for {tool_name}")
                        return CompanyInfo(
                            name=tool_name,
                            description=f"{tool_name} - Task cancelled",
                                website=f"https://{tool_name.lower().replace(' ', '')}.com"
                            )
                    except Exception as e:
                        print(f"❌ Error processing {tool_name}: {e}")
                        return CompanyInfo(
                            name=tool_name,
                            description=f"{tool_name} - Processing error",
                            website=f"https://{tool_name.lower().replace(' ', '')}.com"
                        )

            tasks = [asyncio.create_task(research_and_analyze(t)) for t in tool_names]

            pending: List[asyncio.Task] = tasks[:]
            try:
                for completed in asyncio.as_completed(tasks, timeout=40):  # Increased overall timeout
                    try:
                        company = await completed
                        if company and getattr(company, "name", "").strip():
                            companies.append(company)
                        if completed in pending:
                            pending.remove(completed)  # type: ignore[arg-type]
                    except asyncio.CancelledError:
                        print(f"⏰ Task cancelled during completion")
                        continue
                    except Exception as e:
                        print(f"⚠️ Task completion error: {e}")
                # Update partial results after each completion
                try:
                    valid_companies = [c for c in companies if getattr(c, "name", "").strip()]
                    self._partial_results[state.query] = valid_companies
                    print(f"📊 Updated partial results: {len(valid_companies)} companies stored")
                except Exception as e:
                    print(f"⚠️ Error updating partial results: {e}")
                    pass
            except asyncio.TimeoutError:
                print(f"⏰ Research timeout after 40 seconds")
                # Cancel remaining tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
            # Cancel any leftover tasks to free resources
            try:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                if any(not t.done() for t in tasks):
                    await asyncio.gather(*tasks, return_exceptions=True)
            except Exception:
                pass
        except Exception as e:
            print(f"❌ Research tasks failed: {e}")

        elapsed_time = time.time() - start_time
        print(f"📊 Research completed: {len(companies)} tools analyzed in {elapsed_time:.2f}s")
        return {"companies": companies}

    def get_partial_results(self, query: str) -> List[CompanyInfo]:
        try:
            results = self._partial_results.get(query, [])
            print(f"📊 Retrieved partial results: {len(results)} companies for query '{query}'")
            return results
        except Exception as e:
            print(f"⚠️ Error retrieving partial results: {e}")
            return []

    async def quick_recommendations(self, query: str, companies: List[CompanyInfo]) -> str:
        """Generate a high-quality, fast recommendation from available companies (for timeouts)."""
        # Apply the same pricing filter used by the full analysis for consistency
        try:
            filtered = self._filter_companies_by_pricing(companies or [], query)
        except Exception:
            filtered = companies or []

        # Apply context filters to keep category/language alignment
        try:
            filtered = self._filter_companies_by_context(query, filtered)
        except Exception:
            pass

        if not filtered:
            return "Recommendation pending more results."

        # Build richer company data (up to 8 items) for the prompt
        summaries: List[str] = []
        for company in filtered[:8]:
            summary = f"**{company.name}**: {self._safe_truncate((company.description or '').strip(), 220)}"
            if company.pricing_model:
                summary += f" (Pricing: {company.pricing_model})"
            if company.is_open_source is not None:
                summary += f" ({'Open Source' if company.is_open_source else 'Proprietary'})"
            if company.api_available:
                summary += " (API available)"
            if company.language_support:
                summary += f" (Lang: {', '.join(company.language_support[:2])})"
            if company.integration_capabilities:
                summary += f" (Integrations: {', '.join(company.integration_capabilities[:2])})"
            if company.tech_stack:
                summary += f" (Tech: {', '.join(company.tech_stack[:2])})"
            summaries.append(summary)
        company_data = "\n".join(summaries)

        messages = [
            SystemMessage(content=self.prompts.RECOMMENDATIONS_SYSTEM),
            HumanMessage(content=self.prompts.recommendations_user(query, company_data))
        ]
        try:
            response = await asyncio.wait_for(
                asyncio.get_running_loop().run_in_executor(None, self.llm.invoke, messages),
                timeout=3.0  # Reduced from 5s
            )
            return self._sanitize_summary(response.content)
        except Exception:
            # Deterministic fallback using scoring with clearer reasons and 3 alternatives
            best, runners = self._choose_best_company(query, filtered)
            if not best:
                return "Recommendation pending more results."
            parts: List[str] = []
            desc = self._safe_truncate((best.description or "").strip(), 160)
            pricing = self._normalize_pricing(best.pricing_model)
            parts.append(f"Best fit: {best.name} — {desc}.")
            if pricing:
                parts.append(f"Pricing: {pricing}.")
            if best.is_open_source is True:
                parts.append("Open source.")
            elif best.is_open_source is False:
                parts.append("Proprietary.")
            reason_bits: List[str] = []
            pm = self._extract_pricing_model(query)
            if pm != "any" and pricing:
                reason_bits.append(f"matches {pm}")
            if best.api_available:
                reason_bits.append("API available")
            if best.integration_capabilities:
                reason_bits.append("integrations present")
            if best.language_support:
                reason_bits.append(f"languages: {', '.join(best.language_support[:2])}")
            if reason_bits:
                parts.append("Reason: " + ", ".join(reason_bits) + ".")
            if runners:
                alt_bits = []
                for o in runners[:3]:
                    alt_p = self._normalize_pricing(o.pricing_model)
                    bit = o.name + (f" ({alt_p})" if alt_p else "")
                    alt_bits.append(bit)
                parts.append("Alternatives: " + ", ".join(alt_bits) + ".")
            return self._sanitize_summary(" ".join(parts))

    def _normalize_pricing(self, pricing: Optional[str]) -> str:
        if not pricing:
            return ""
        p = (pricing or "").strip().lower()
        mapping = {
            "paid": "Paid",
            "free": "Free",
            "freemium": "Freemium",
            "enterprise": "Enterprise",
            "unknown": ""
        }
        return mapping.get(p, pricing if pricing and pricing[0].isupper() else pricing.capitalize())

    def _safe_truncate(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        cut = text[:limit]
        # Avoid cutting mid-word
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        return cut.rstrip(".,;: ") + "…"

    def _choose_best_company(self, query: str, companies: List[CompanyInfo]) -> (Optional[CompanyInfo], List[CompanyInfo]):
        # Score companies by pricing match, API presence, integrations, language support, and description length
        pm = self._extract_pricing_model(query)
        scored: List[tuple] = []
        for c in companies:
            if not c or not getattr(c, 'name', None):
                continue
            score = 0
            pricing = (c.pricing_model or "").lower()
            if pm == "free" and pricing == "free":
                score += 4
            elif pm == "paid" and (pricing in ["paid", "enterprise"]):
                score += 4
            elif pm == "freemium" and pricing == "freemium":
                score += 4
            # API availability and integrations are strong developer signals
            if c.api_available:
                score += 2
            if c.integration_capabilities:
                score += 1
            if c.language_support:
                score += 1
            # Prefer richer descriptions
            if c.description and len(c.description) > 60:
                score += 1
            # Prefer known names in query context (simple contains check)
            try:
                if c.name and c.name.lower() in (query or "").lower():
                    score += 1
            except Exception:
                pass
            scored.append((score, c))
        if not scored:
            return None, []
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        runners = [c for _, c in scored[1:]]
        return best, runners

    def _sanitize_summary(self, text: str) -> str:
        """Remove log-like lines, URLs, and keep the summary concise (<= 3 sentences)."""
        try:
            import re as _re
            # Drop lines that look like logs or scraping traces
            cleaned_lines: List[str] = []
            for line in (text or "").splitlines():
                l = line.strip()
                if not l:
                    continue
                if l.startswith(("🌐", "✅", "⚠️", "❌", "⏰")):
                    continue
                if _re.search(r"https?://", l):
                    continue
                if _re.search(r"\d{4}-\d{2}-\d{2}", l):
                    continue
                if _re.search(r"\b(INFO|ERROR|WARNING)[: ]", l):
                    continue
                cleaned_lines.append(l)
            cleaned = " ".join(cleaned_lines)
            # Limit to 3 sentences
            sentences = _re.split(r"(?<=[.!?])\s+", cleaned)
            summary = " ".join(sentences[:3]).strip()
            # Trim length
            if len(summary) > 500:
                summary = summary[:500].rstrip() + "…"
            return summary or "Recommendation pending more results."
        except Exception:
            return (text or "").strip()[:500]

    def _filter_companies_by_pricing(self, companies: List[CompanyInfo], query: str) -> List[CompanyInfo]:
        """Filter companies based on pricing model from query"""
        pricing_model = self._extract_pricing_model(query)
        
        if pricing_model == "any":
            return companies
        
        filtered_companies = []
        editor_allow = [
            "visual studio code",
            "visual studio",
            "intellij",
            "pycharm",
            "webstorm",
            "rider",
            "sublime",
            "atom",
            "vscodium",
            "eclipse",
            "netbeans",
            "emacs",
            "vim"
        ]
        q_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        is_code_query = (
            "code editor" in query.lower()
            or "integrated development environment" in query.lower()
            or "ide" in q_tokens
            or "ides" in q_tokens
        )

        for company in companies:
            company_name_lower = (company.name or "").lower()

            # DAST context: keep only known DAST tools
            if any(word in company_name_lower for word in ["dast", "dynamic application security", "owasp zap", "burp", "nikto", "arachni", "w3af", "web app scanner"]):
                allowed = ["owasp zap", "burp", "burp suite", "nikto", "arachni", "w3af"]
                if not any(a in company_name_lower for a in allowed):
                    continue

            # Code editor context
            if is_code_query and not any(allow in company_name_lower for allow in editor_allow):
                continue

            # Special handling for Visual Studio tools
            if "visual studio" in company_name_lower:
                if any(word in company_name_lower for word in ["enterprise", "professional", "test professional"]):
                    filtered_companies.append(company)
                elif any(word in company_name_lower for word in ["code", "community"]):
                    filtered_companies.append(company)
                else:
                    filtered_companies.append(company)  # Base Visual Studio has free and paid tiers
                continue

            commercial_markers = [
                "commercial support",
                "enterprise support",
                "professional support",
                "managed support",
                "commercial licensing",
                "commercial licence",
                "enterprise licence",
                "enterprise license",
                "commercial services",
                "enterprise services",
                "paid plan",
                "premium support"
            ]
            if any(marker in company_name_lower for marker in commercial_markers):
                filtered_companies.append(company)
                continue

            # Check if company matches the pricing model
            if pricing_model == "paid":
                if company.pricing_model in ["Paid", "Enterprise"]:
                    filtered_companies.append(company)
                elif (
                    company.pricing_model == "Freemium"
                    and any(word in (company.description or "").lower() for word in ["premium", "pro", "enterprise", "paid", "subscription"])
                ):
                    filtered_companies.append(company)
                elif any(tool in company_name_lower for tool in [
                    "sauce labs", "browserstack", "lambdatest", "perfecto", "experitest",
                    "crossbrowsertesting", "cypress", "testcafe", "katalon", "testim",
                    "pythonanywhere pro", "heroku", "vercel pro", "netlify pro",
                    "redux toolkit pro", "mobx pro", "apollo studio", "relay", "xstate",
                    "react query pro", "swr pro", "zustand pro", "recoil pro", "jotai pro"
                ]):
                    filtered_companies.append(company)
            elif pricing_model == "free":
                if (
                    company.pricing_model == "Free"
                    or company.is_open_source is True
                    or any(word in (company.description or "").lower() for word in ["open source", "free", "foss", "community"])
                ):
                    filtered_companies.append(company)
            elif pricing_model == "freemium":
                if (
                    company.pricing_model == "Freemium"
                    or any(word in (company.description or "").lower() for word in ["freemium", "trial", "demo", "free tier", "basic", "pro"])
                ):
                    filtered_companies.append(company)

        if not filtered_companies and companies:
            print(f"⚠️ No companies found matching '{pricing_model}' pricing model, showing all results")
            return companies

        return filtered_companies

    def _analyze_step(self, state: ResearchState) -> Dict[str, Any]:
        """Final analysis step to generate recommendations"""
        companies = getattr(state, "companies", [])
        
        if not companies:
            return {"analysis": "No tools found for analysis."}

        # Filter companies based on pricing model from query
        filtered_companies = self._filter_companies_by_pricing(companies, state.query)
        pricing_model = self._extract_pricing_model(state.query)
        
        if pricing_model != "any" and len(filtered_companies) < len(companies):
            print(f"🔍 Filtered to {len(filtered_companies)} companies matching '{pricing_model}' pricing model")

        # Apply context filter before prompting (e.g., JS testing generic vs React-only)
        filtered_companies = self._filter_companies_by_context(state.query, filtered_companies)

        # Build company data for the prompt
        company_summaries = []
        for company in filtered_companies:
            summary = f"**{company.name}**: {company.description}"
            if company.pricing_model:
                summary += f" (Pricing: {company.pricing_model})"
            if company.is_open_source is not None:
                summary += f" ({'Open Source' if company.is_open_source else 'Proprietary'})"
            if company.tech_stack:
                summary += f" (Tech: {', '.join(company.tech_stack[:3])})"
            company_summaries.append(summary)

        company_data = "\n".join(company_summaries)

        # Build recommendation with small retry/backoff to mitigate transient APIConnectionError
        messages = [
            SystemMessage(content=self.prompts.RECOMMENDATIONS_SYSTEM),
            HumanMessage(content=self.prompts.recommendations_user(state.query, company_data))
        ]
        last_err = None
        for attempt in range(3):
            try:
                response = self.llm.invoke(messages)
                print("✅ Analysis generated successfully")
                return {"analysis": response.content}
            except Exception as e:
                last_err = e
                print(f"⚠️ Recommendation attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    import time
                    time.sleep(1 * (2 ** attempt))
        # Exhausted retries
        print(f"❌ Analysis generation error: {last_err}")
        print(f"❌ Error type: {type(last_err).__name__}")
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass
        return {"analysis": "Analysis generation failed, but individual tool information is available above."}

    def _analyze_company_content(self, company_name: str, content: str, source_url: str = "", query: str = "") -> CompanyInfo:
        """Fast analysis with structured output and pricing model prioritization"""
        try:
            structured_llm = self.llm.with_structured_output(CompanyAnalysis)

            # Enhanced prompt that includes pricing model context from query
            pricing_context = ""
            pricing_model = self._extract_pricing_model(query)
            if pricing_model != "any":
                pricing_context = f"\n\nIMPORTANT: The user is specifically looking for {pricing_model} tools. Pay extra attention to pricing and licensing information in the content."

            messages = [
                SystemMessage(content=f"Analyze this tool quickly and extract key information. Focus on factual details, especially pricing and licensing information.{pricing_context}"),
                HumanMessage(content=f"Tool: {company_name}\nContent: {content[:4000]}")
            ]

            analysis = structured_llm.invoke(messages)
            
            # Post-process to improve pricing model detection
            enhanced_pricing_model = self._enhance_pricing_model_detection(analysis.pricing_model, content, company_name)
            
            return CompanyInfo(
                name=analysis.name or company_name,
                description=analysis.description or f"{company_name} - Developer tool",
                website=(analysis.website or source_url or f"https://{company_name.lower().replace(' ', '')}.com"),
                pricing_model=enhanced_pricing_model,
                is_open_source=analysis.is_open_source,
                tech_stack=analysis.tech_stack[:5] if analysis.tech_stack else [],
                api_available=analysis.api_available,
                language_support=analysis.language_support[:5] if analysis.language_support else [],
                integration_capabilities=analysis.integration_capabilities[:5] if analysis.integration_capabilities else []
            )
        except Exception as e:
            print(f"❌ Analysis error for {company_name}: {e}")
            print(f"❌ Error type: {type(e).__name__}")
            print(f"❌ Content length: {len(content) if content else 0}")
            import traceback
            traceback.print_exc()
            # Return basic info even if analysis fails
            return CompanyInfo(
                name=company_name,
                description=f"{company_name} - Developer tool (analysis failed)",
                website=(source_url or f"https://{company_name.lower().replace(' ', '')}.com")
            )

    def _enhance_pricing_model_detection(self, detected_model: str, content: str, company_name: str) -> str:
        """Enhance pricing model detection based on content analysis"""
        content_lower = content.lower()
        company_lower = company_name.lower()
        
        # If model is already detected and not "Unknown", use it
        if detected_model and detected_model != "Unknown":
            return detected_model
        
        # Special handling for Visual Studio tools
        if "visual studio" in company_lower:
            if any(word in company_lower for word in ["enterprise", "professional", "test professional"]):
                return "Paid"
            elif any(word in company_lower for word in ["code", "community"]):
                return "Free"
            else:
                return "Freemium"  # Base Visual Studio has free and paid tiers
        
        # Special cases for known paid tools
        paid_tools = [
            "sauce labs", "browserstack", "lambdatest", "perfecto", "experitest", 
            "crossbrowsertesting", "cypress", "testcafe", "katalon", "testim",
            "pythonanywhere pro", "heroku", "vercel pro", "netlify pro",
            "redux toolkit pro", "mobx pro", "apollo studio", "relay", "xstate",
            "react query pro", "swr pro", "zustand pro", "recoil pro", "jotai pro"
        ]
        
        if any(tool in company_lower for tool in paid_tools):
            return "Paid"
        
        # Enhanced detection based on content keywords - order matters!
        # Check freemium first to avoid conflicts
        if any(word in content_lower for word in ["freemium", "free tier", "trial", "demo", "basic plan", "upgrade", "pro version"]):
            return "Freemium"
        elif any(word in content_lower for word in ["free", "open source", "mit license", "apache license", "gpl", "bsd", "community edition", "foss"]):
            return "Free"
        elif any(word in content_lower for word in ["subscription", "pricing", "cost", "license fee", "commercial license", "paid", "premium", "pro", "enterprise", "business", "professional"]):
            return "Paid"
        elif any(word in content_lower for word in ["enterprise", "business", "professional", "commercial", "corporate"]):
            return "Enterprise"
        
        # Company name-based detection
        if any(word in company_lower for word in ["enterprise", "pro", "premium", "commercial"]):
            return "Paid"
        elif any(word in company_lower for word in ["free", "open", "community"]):
            return "Free"
        
        return detected_model or "Unknown"

    # Helper methods
    async def _scrape_multiple_pages(self, urls):
        """Scrape multiple URLs concurrently"""
        if not urls:
            return []
        
        # Limit concurrent requests to avoid overwhelming servers
        semaphore = asyncio.Semaphore(3)
        
        async def scrape_with_semaphore(url):
            async with semaphore:
                try:
                    return await self.scraper.scrape_company_pages(url)
                except Exception as e:
                    print(f"❌ Scraping error for {url}: {e}")
                    return None
        
        tasks = [scrape_with_semaphore(url) for url in urls if url]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [result for result in results if isinstance(result, dict) and result.get("markdown")]

    async def _scrape_multiple_pages_optimized(self, urls):
        """Optimized scraping with increased concurrency and better error handling"""
        if not urls:
            return []
        
        # Increase concurrency for better performance
        semaphore = asyncio.Semaphore(5)  # Increased from 3 to 5
        
        async def scrape_with_retry(url, max_retries=2):
            async with semaphore:
                for attempt in range(max_retries + 1):
                    try:
                        result = await asyncio.wait_for(
                            self.scraper.scrape_company_pages(url), 
                            timeout=8.0  # Reduced from 15s
                        )
                        if result and result.get("markdown"):
                            return result
                        elif attempt < max_retries:
                            await asyncio.sleep(0.5)  # Brief delay before retry
                    except (asyncio.TimeoutError, Exception) as e:
                        if attempt < max_retries:
                            print(f"⚠️ Scraping attempt {attempt + 1} failed for {url}: {e}")
                            await asyncio.sleep(0.5)
                        else:
                            print(f"❌ Scraping failed for {url} after {max_retries + 1} attempts: {e}")
                return None
        
        tasks = [scrape_with_retry(url) for url in urls if url]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [result for result in results if isinstance(result, dict) and result.get("markdown")]

    async def _smart_company_research_optimized(self, tool_name: str):
        """Optimized research with better error handling and timeout"""
        search_query = f"{tool_name} official documentation site"
        try:
            async with SearchManager() as manager:
                search_results = await asyncio.wait_for(
                    manager.search(search_query, num_results=3),
                    timeout=8.0
                )
        except asyncio.TimeoutError:
            print(f"⏰ Research timeout for {tool_name}")
            return {"markdown": f"Research timeout for {tool_name}"}
        except Exception as e:
            print(f"❌ Research error for {tool_name}: {e}")
            return {"markdown": f"Research error for {tool_name}: {str(e)}"}

        if not search_results or not search_results.get("data"):
            print(f"⚠️ No search results found for {tool_name}")
            return {"markdown": f"No search results found for {tool_name}"}

        best_url = self._get_best_url_optimized(search_results["data"], tool_name)
        if best_url:
            print(f"🌐 Scraping {tool_name}: {best_url}")
            try:
                scraped_content = await asyncio.wait_for(
                    self.scraper.scrape_company_pages(best_url),
                    timeout=10.0
                )
                if scraped_content and scraped_content.get("markdown"):
                    print(f"✅ Successfully scraped content for {tool_name}")
                    return {"markdown": scraped_content["markdown"], "url": best_url}
                else:
                    print(f"⚠️ No scraped content, using search snippets")
                    return {"markdown": f"Using search snippets for {tool_name}", "url": best_url}
            except asyncio.TimeoutError:
                print(f"⏰ Research timeout for {tool_name}")
                return {"markdown": f"Timeout - using search snippets for {tool_name}", "url": best_url}
        print(f"❌ No valid URL found for {tool_name}")
        return {"markdown": f"No valid URL found for {tool_name}"}

    def _get_best_url_optimized(self, search_results: List[Dict], tool_name: str) -> Optional[str]:
        """Optimized URL selection with better prioritization"""
        if not search_results:
            return None
            
        urls_by_priority = []
        tool_lower = tool_name.lower()
        
        # Tool-specific allowlist for authoritative docs
        preferred_by_tool = {
            'boost': ["boost.org", "www.boost.org"],
            'qt': ["doc.qt.io", "qt.io"],
            'opencv': ["docs.opencv.org", "opencv.org"],
            'eigen': ["eigen.tuxfamily.org", "libeigen.gitlab.io"],
            'poco': ["pocoproject.org"],
            'wxwidgets': ["wxwidgets.org", "docs.wxwidgets.org"],
            'stl': ["en.cppreference.com", "cplusplus.com"],
            'google test': ["google.github.io", "github.com"],
            'catch2': ["github.com"],
            'cppunit': ["freedesktop.org", "github.com"],
            'jest': ["jestjs.io"],
            'cypress': ["docs.cypress.io"],
            'chai': ["chaijs.com"],
            'recoil': ["recoiljs.org"],
            'redux': ["redux.js.org"],
            'mobx': ["mobx.js.org"],
            'zustand': ["docs.pmnd.rs", "pmnd.rs", "github.com"],
            'enzyme': ["enzymejs.github.io", "github.com"],
            'exposed': ["jetbrains.github.io", "github.com/jetbrains/exposed", "github.com/JetBrains/Exposed"],
            # JavaScript testing frameworks
            'tape': ["github.com/substack/tape", "github.com"],
            'mocha': ["mochajs.org"],
            'jasmine': ["jasmine.github.io"],
            'vitest': ["vitest.dev"],
            'playwright': ["playwright.dev"],
            'webdriverio': ["webdriver.io"],
            'karma': ["karma-runner.github.io"],
            # React state management tools
            'relay': ["relay.dev", "facebook.github.io"],
            'swr': ["swr.vercel.app"],
            'swr pro': ["swr.vercel.app"],
            'apollo client': ["apollographql.com"],
            'react query': ["tanstack.com"],
            'react query pro': ["tanstack.com"],
            'tanstack query': ["tanstack.com"],
            'recoil': ["recoiljs.org"],
            'recoil pro': ["recoiljs.org"],
            'jotai': ["jotai.org"],
            'jotai pro': ["jotai.org"],
            'mobx pro': ["mobx.js.org"],
            # Go web frameworks
            'gin': ["gin-gonic.com"],
            'echo': ["echo.labstack.com"],
            'fiber': ["docs.gofiber.io", "gofiber.io"],
            'chi': ["go-chi.io"],
            'beego': ["beego.vip", "beego.me"],
            'revel': ["revel.github.io"],
            'buffalo': ["gobuffalo.io"],
            # Swift common libraries
            'alamofire': ["github.com", "alamofire.github.io"],
            'swiftui': ["developer.apple.com"],
            'uikit': ["developer.apple.com"],
            # Swift testing tools
            'xctest': ["developer.apple.com"],
            'quick': ["github.com", "quick.github.io"],
            'nimble': ["github.com", "quick.github.io"],
            'snapshottesting': ["github.com", "pointfreeco"],
            'swiftcheck': ["github.com"],
            'ohhttpstubs': ["github.com", "alisoftware.github.io"],
            'mockingbird': ["mockingbirdswift.com", "github.com"],
            'cuckoo': ["github.com/brightify/cuckoo", "github.com"],
            'swiftlint': ["github.com/realm/SwiftLint", "github.com"]
        }
        # CI/CD official docs allowlist
        preferred_by_tool.update({
            'github actions': ["docs.github.com"],
            'gitlab ci': ["docs.gitlab.com"],
            'circleci': ["circleci.com"],
            'jenkins': ["www.jenkins.io", "jenkins.io"],
            'argo cd': ["argo-cd.readthedocs.io", "argo-cd"],
            'tekton': ["tekton.dev"],
            'travis ci': ["travis-ci.com"],
            'bitbucket pipelines': ["support.atlassian.com", "bitbucket.org"],
            'azure pipelines': ["learn.microsoft.com"],
            'teamcity': ["www.jetbrains.com"],
            # DevOps IaC/containers/observability
            'terraform': ["developer.hashicorp.com", "registry.terraform.io", "terraform.io"],
            'ansible': ["docs.ansible.com"],
            'puppet': ["puppet.com/docs"],
            'chef': ["docs.chef.io"],
            'docker': ["docs.docker.com"],
            'kubernetes': ["kubernetes.io"],
            'helm': ["helm.sh"],
            'prometheus': ["prometheus.io"],
            'grafana': ["grafana.com/docs"],
            'flux': ["fluxcd.io"],
            'argo': ["argo-cd.readthedocs.io", "argoproj.github.io"]
        })
        # DAST / API gateway / Error monitoring / APM allowlists
        preferred_by_tool.update({
            # DAST
            'owasp zap': ["www.zaproxy.org", "zaproxy.org"],
            'burp suite': ["portswigger.net"],
            'nikto': ["cirt.net"],
            'arachni': ["arachni-scanner.com"],
            'w3af': ["w3af.org"],
            # API gateways
            'kong enterprise': ["docs.konghq.com"],
            'apigee': ["cloud.google.com/apigee"],
            'tyk': ["tyk.io"],
            'mulesoft anypoint': ["docs.mulesoft.com"],
            'nginx plus': ["docs.nginx.com"],
            'traefik hub': ["traefik.io"],
            # Error monitoring / crash reporting
            'sentry': ["docs.sentry.io"],
            'rollbar': ["docs.rollbar.com"],
            'bugsnag': ["docs.bugsnag.com"],
            'new relic errors inbox': ["docs.newrelic.com"],
            # APM
            'datadog apm': ["docs.datadoghq.com"],
            'new relic apm': ["docs.newrelic.com"],
            'elastic apm': ["www.elastic.co"],
            'appdynamics': ["docs.appdynamics.com"],
        })
        # Testing libraries and JS ecosystem preferred docs
        preferred_by_tool.update({
            'jasmine': ["jasmine.github.io"],
            'vitest': ["vitest.dev"],
            'playwright': ["playwright.dev"],
            'react query': ["tanstack.com"],
            'reactquery': ["tanstack.com"],
            'testing-libraryreact': ["testing-library.com"],
            'testing library react': ["testing-library.com"],
            'react testing library': ["testing-library.com"],
            'testing-librarydom': ["testing-library.com"],
            'testing library dom': ["testing-library.com"],
            'dom testing library': ["testing-library.com"],
            'scikit-learn': ["scikit-learn.org"],
            'scikitlearn': ["scikit-learn.org"],
            'selenium': ["selenium.dev", "www.selenium.dev", "docs.selenium.dev"],
            'beautiful soup': ["crummy.com"],
            'beautifulsoup': ["crummy.com"],
            'bs4': ["crummy.com"],
            'spek': ["spekframework.org"],
            'exposed': ["jetbrains.github.io", "github.com"],
            'travis ci': ["docs.travis-ci.com", "travis-ci.com"],
        })
        # Normalize keys for consistent matching (remove spaces/dashes, lower)
        def _norm_key(s: str) -> str:
            try:
                import re as _re
                return _re.sub(r"[\s\-]+", "", (s or "").lower())
            except Exception:
                return (s or "").lower()

        preferred_normalized = { _norm_key(k): v for k, v in preferred_by_tool.items() }

        for result in search_results:
            url = result.get("url", "")
            if not url:
                continue
                
            domain = urlparse(url).netloc.lower()
            
            # Check tool-specific preferences
            raw_key = tool_lower.strip()
            key = _norm_key(raw_key)
            if key in preferred_normalized and any(pref in domain for pref in preferred_normalized[key]):
                urls_by_priority.insert(0, url)
                continue

            # High priority: official-looking and docs/github
            if any(keyword in domain for keyword in ["docs.", "github.com"]) or domain.endswith((".org", ".dev")):
                urls_by_priority.append(url)
            else:
                urls_by_priority.append(url)
        
        # Prefer URLs that look like HTML docs (avoid download/pdf links)
        def is_probably_html(u: str) -> bool:
            try:
                path = urlparse(u).path.lower()
            except Exception:
                path = ""
            bad_exts = ('.pdf', '.zip', '.rar', '.7z', '.dmg', '.exe')
            return not path.endswith(bad_exts) and ('/_/downloads/' not in path)

        # Tool-specific exclusions to avoid common false positives
        def not_blacklisted(u: str) -> bool:
            parsed = urlparse(u)
            d = parsed.netloc.lower()
            p = parsed.path.lower()
            if key == 'spek':
                if any(wrong in d for wrong in ['unity.com', 'docs.unity3d.com', 'unity3d.com', 'unity3d']):
                    return False
            if key == 'quick':
                if any(wrong_domain in d for wrong_domain in ['gohugo.io', 'react.dev', 'docusaurus.io', 'facebook.github.io']):
                    return False
            if key == 'nimble':
                if any(wrong_domain in d for wrong_domain in ['h2zero', 'arduino', 'presscustomizr', 'nimble-page-builder', 'customizr']):
                    return False
            if key in ['snapshottesting', 'snapshot testing']:
                if 'playwright.dev' in d or 'jestjs.io' in d or 'storybook.js.org' in d:
                    return False
            if key == 'cuckoo':
                if 'cuckoosandbox' in d or ('github.com' in d and '/cuckoosandbox/' in p):
                    return False
            if key == 'mockingbird':
                if 'mockingbird.io' in d or 'gomockingbird' in d:
                    return False
            # JavaScript testing tool exclusions
            if key == 'tape':
                # Exclude government/census sites, focus on JavaScript testing library
                if any(gov_domain in d for gov_domain in ['census.gov', 'gov.', '.gov']):
                    return False
                if 'technical-documentation' in p or 'complete-technical-documents' in p:
                    return False
            if key == 'chai':
                # Exclude chatbot/AI tools, focus on assertion library
                if any(ai_domain in d for ai_domain in ['openai.com', 'chai.ml', 'chai-gpt']):
                    return False
            # React state management tool exclusions
            if key in ['mobxpro', 'mobx pro']:
                # Exclude MobaXterm (terminal software) - focus on MobX React library
                if 'mobaxterm' in d or 'mobatek' in d:
                    return False
            if key in ['swrpro', 'swr pro', 'swr']:
                # Exclude non-SWR sites like Prometric, satellite launcher guides, plumbing/industrial sites
                if any(wrong_domain in d for wrong_domain in ['prometric.com', 'satellitelauncher', 'ehelp', 'adspipe.com', 'plumbing', 'pipe', 'industrial', 'construction']):
                    return False
            if key == 'relay':
                # Exclude non-React Relay sites
                if any(wrong_domain in d for wrong_domain in ['relayhealth', 'relay.com', 'relaynetwork']):
                    return False
            if key in ['recoilpro', 'recoil pro', 'recoil']:
                # Exclude non-React Recoil sites (hoses, springs, mechanical parts)
                if any(wrong_domain in d for wrong_domain in ['ottersprings', 'hose', 'spring', 'mechanical', 'industrial']):
                    return False
            # Kotlin testing false positives
            if key == 'spek':
                if any(wrong_domain in d for wrong_domain in ['unity3d.com', 'unity.com', 'grafana.com', 'oasis-open.org', 'saml']):
                    return False
            if key == 'travisci':
                # Avoid homepage that can cause long headers or redirects; prefer docs
                if d == 'www.travis-ci.com' and not p.startswith('/docs'):
                    return False
            return True

        html_pref = [u for u in urls_by_priority if is_probably_html(u) and not_blacklisted(u)]

        # Path-level preferences for certain tools (prefer stable/latest or official guides)
        def path_score(u: str) -> int:
            try:
                parsed = urlparse(u)
                d = parsed.netloc.lower()
                p = parsed.path.lower()
            except Exception:
                d, p = "", ""
            # Defaults
            score = 10
            # scikit-learn: prefer /stable/
            if key in ['scikitlearn', 'scikit-learn'] and 'scikit-learn.org' in d:
                score = 0 if '/stable/' in p else 2
            # React Query: prefer tanstack.com/query/latest
            if key in ['reactquery', 'react query'] and 'tanstack.com' in d:
                score = 0 if '/query/latest' in p else 1
            # Testing Library React/DOM: prefer testing-library.com/docs/... paths
            if key in ['testinglibraryreact', 'testing library react', 'reacttestinglibrary'] and 'testing-library.com' in d:
                score = 0 if '/docs/react-testing-library' in p else 1
            if key in ['testinglibrarydom', 'testing library dom', 'domtestinglibrary'] and 'testing-library.com' in d:
                score = 0 if '/docs/dom-testing-library' in p else 1
            # Playwright: prefer /docs paths
            if key == 'playwright' and 'playwright.dev' in d:
                score = 0 if p.startswith('/docs') else 2
            # Vitest: prefer /guide
            if key == 'vitest' and 'vitest.dev' in d:
                score = 0 if p.startswith('/guide') else 2
            # Selenium: prefer selenium.dev/documentation
            if key == 'selenium' and ('selenium.dev' in d or 'www.selenium.dev' in d):
                score = 0 if '/documentation' in p else 2
            # Beautiful Soup: prefer crummy.com official bs4 docs
            if key in ['beautifulsoup', 'beautiful soup', 'bs4'] and 'crummy.com' in d:
                score = 0 if '/beautifulsoup/bs4/doc' in p or '/bs4/doc' in p else 2
            return score

        if html_pref:
            # Prefer best path among html candidates
            html_pref.sort(key=path_score)
            return html_pref[0]
        # Fallback: still respect blacklist
        filtered = [u for u in urls_by_priority if not_blacklisted(u)]
        if filtered:
            return filtered[0]

        fallback_by_tool = {
            'spek': 'https://spekframework.org/',
        }
        fallback_url = fallback_by_tool.get(key)
        if fallback_url:
            return fallback_url

        return urls_by_priority[0] if urls_by_priority else None

    async def _analyze_company_content_optimized(self, company_name: str, content: str, source_url: str = "", query: str = "") -> CompanyInfo:
        """Optimized analysis with timeout and better error handling"""
        try:
            structured_llm = self.llm.with_structured_output(CompanyAnalysis)

            # Enhanced prompt that includes pricing model context from query
            pricing_context = ""
            pricing_model = self._extract_pricing_model(query)
            if pricing_model != "any":
                pricing_context = f"\n\nIMPORTANT: The user is specifically looking for {pricing_model} tools. Pay extra attention to pricing and licensing information in the content."

            messages = [
                SystemMessage(content=f"Analyze this tool quickly and extract key information. Focus on factual details, especially pricing and licensing information.{pricing_context}"),
                HumanMessage(content=f"Tool: {company_name}\nContent: {content[:3000]}")  # Reduced from 4000 to 3000
            ]

            # Add timeout to analysis - fix async event loop issue
            analysis = await asyncio.wait_for(
                asyncio.get_running_loop().run_in_executor(
                    None, structured_llm.invoke, messages
                ), 
                timeout=12.0  # Increased timeout for better reliability
            )
            
            # Post-process to improve pricing model detection
            enhanced_pricing_model = self._enhance_pricing_model_detection(analysis.pricing_model, content, company_name)
            
            return CompanyInfo(
                name=analysis.name or company_name,
                description=analysis.description or f"{company_name} - Developer tool",
                website=(analysis.website or source_url or f"https://{company_name.lower().replace(' ', '')}.com"),
                pricing_model=enhanced_pricing_model,
                is_open_source=analysis.is_open_source,
                tech_stack=analysis.tech_stack[:5] if analysis.tech_stack else [],
                api_available=analysis.api_available,
                language_support=analysis.language_support[:5] if analysis.language_support else [],
                integration_capabilities=analysis.integration_capabilities[:5] if analysis.integration_capabilities else []
            )
        except asyncio.TimeoutError:
            print(f"⏰ Analysis timeout for {company_name}")
            # Return a minimal but valid CompanyInfo without timeout text
            safe_name = (company_name or "").strip() or "Unknown"
            return CompanyInfo(
                name=safe_name,
                description=(f"{safe_name} - Developer tool" if safe_name != "Unknown" else "Developer tool"),
                website=(source_url or (f"https://{safe_name.lower().replace(' ', '')}.com" if safe_name != "Unknown" else ""))
            )
        except Exception as e:
            print(f"❌ Analysis error for {company_name}: {e}")
            # Return basic info even if analysis fails
            return CompanyInfo(
                name=company_name,
                description=f"{company_name} - Developer tool (analysis failed)",
                website=(source_url or f"https://{company_name.lower().replace(' ', '')}.com")
            )

    async def _smart_company_research(self, tool_name: str):
        """Smart research for a specific tool with better URL prioritization"""
        try:
            # First, search for the tool with better query
            search_query = f"{tool_name} official documentation site"
            search_results = await self.scraper.search_companies(search_query, num_results=3)
            
            if not search_results.get("data"):
                print(f"⚠️ No search results found for {tool_name}")
                return {"markdown": f"No search results found for {tool_name}"}
            
            # Check if results are from hardcoded fallback
            source = search_results["data"][0].get("metadata", {}).get("source", "unknown")
            if source == "hardcoded":
                print(f"📋 Using hardcoded data for {tool_name}")
            else:
                print(f"🌐 Found live search results for {tool_name}")
            
            # Get the best URL with improved prioritization and HTML preference
            best_url = None
            urls_by_priority = []
            
            for result in search_results["data"]:
                url = result.get("url", "")
                if not url:
                    continue
                    
                domain = urlparse(url).netloc.lower()

                # Tool-specific allowlist for authoritative docs
                preferred_by_tool = {
                    'boost': ["boost.org", "www.boost.org"],
                    'qt': ["doc.qt.io", "qt.io"],
                    'opencv': ["docs.opencv.org", "opencv.org"],
                    'eigen': ["eigen.tuxfamily.org", "libeigen.gitlab.io"],
                    'poco': ["pocoproject.org"],
                    'wxwidgets': ["wxwidgets.org", "docs.wxwidgets.org"],
                    'stl': ["en.cppreference.com", "cplusplus.com"],
                    'google test': ["google.github.io", "github.com"],
                    'catch2': ["github.com"],
                    'cppunit': ["freedesktop.org", "github.com"]
                }
                # JS testing and React allowlist
                preferred_by_tool.update({
                    'jest': ["jestjs.io"],
                    'cypress': ["docs.cypress.io"],
                    'chai': ["chaijs.com"],
                    'recoil': ["recoiljs.org"],
                    'redux': ["redux.js.org"],
                    'mobx': ["mobx.js.org"],
                    'zustand': ["docs.pmnd.rs", "pmnd.rs", "github.com"],
                    # JavaScript testing frameworks
                    'tape': ["github.com/substack/tape", "github.com"],
                    'mocha': ["mochajs.org"],
                    'jasmine': ["jasmine.github.io"],
                    'vitest': ["vitest.dev"],
                    'playwright': ["playwright.dev"],
                    'webdriverio': ["webdriver.io"],
                    'karma': ["karma-runner.github.io"],
                    # React state management tools
                    'relay': ["relay.dev", "facebook.github.io"],
                    'swr': ["swr.vercel.app"],
                    'swr pro': ["swr.vercel.app"],
                    'apollo client': ["apollographql.com"],
                    'react query': ["tanstack.com"],
                    'react query pro': ["tanstack.com"],
                    'tanstack query': ["tanstack.com"],
                    'recoil': ["recoiljs.org"],
                    'recoil pro': ["recoiljs.org"],
                    'jotai': ["jotai.org"],
                    'jotai pro': ["jotai.org"],
                    'mobx pro': ["mobx.js.org"]
                })
                # Normalize tool key
                key = tool_name.lower().strip()
                # Map common names to keys
                if key in ["stl", "stl c++ standard library", "standard template library"]:
                    key = "stl"
                if key.startswith("boost"):
                    key = "boost"
                if key.startswith("qt"):
                    key = "qt"
                if key.startswith("opencv"):
                    key = "opencv"
                if key.startswith("eigen"):
                    key = "eigen"
                if key.startswith("poco"):
                    key = "poco"
                if key.startswith("wx"):
                    key = "wxwidgets"
                if key in preferred_by_tool and any(pref in domain for pref in preferred_by_tool[key]):
                    urls_by_priority.insert(0, url)
                    continue

                # High priority: official-looking and docs/github
                if any(keyword in domain for keyword in ["docs.", "github.com"]) or domain.endswith((".org", ".dev")):
                    urls_by_priority.append(url)
                else:
                    urls_by_priority.append(url)
            
            # Prefer URLs that look like HTML docs (avoid download/pdf links)
            def is_probably_html(u: str) -> bool:
                try:
                    path = urlparse(u).path.lower()
                except Exception:
                    path = ""
                bad_exts = ('.pdf', '.zip', '.rar', '.7z', '.dmg', '.exe')
                return not path.endswith(bad_exts) and ('/_/downloads/' not in path)

            html_pref = [u for u in urls_by_priority if is_probably_html(u)]
            best_url = (html_pref[0] if html_pref else (urls_by_priority[0] if urls_by_priority else None))

            if best_url:
                print(f"🌐 Scraping {tool_name}: {best_url}")
                scraped_content = await self.scraper.scrape_company_pages(best_url)
                if scraped_content and scraped_content.get("markdown"):
                    print(f"✅ Successfully scraped content for {tool_name}")
                    # Enrich by following a couple of internal doc links if available
                    enriched = scraped_content["markdown"]
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(enriched, 'html.parser')
                        extra_urls = []
                        # Can't parse links from markdown easily here; instead, re-scrape the page and parse anchors
                        # Use scraper directly to fetch HTML and then parse links
                        html_result = await self.scraper.scrape_company_pages(best_url)
                        if html_result and html_result.get("markdown"):
                            # Already enriched; just return
                            pass
                    except Exception:
                        pass
                    # Pass best_url to analysis
                    return {"markdown": enriched, "url": best_url}
                else:
                    print(f"❌ Failed to scrape content for {tool_name}")
                    return {"markdown": f"Failed to scrape content for {tool_name} from {best_url}", "url": best_url}
            else:
                print(f"❌ No valid URL found for {tool_name}")
                return {"markdown": f"No valid URL found for {tool_name}"}

        except Exception as e:
            print(f"❌ Research error for {tool_name}: {e}")
            return {"markdown": f"Research error for {tool_name}: {str(e)}"}

    # Main execution methods
    async def run_async(self, query: str) -> ResearchState:
        """Run the workflow asynchronously"""
        initial_state = ResearchState(query=query)
        # Offload blocking graph invocation to a thread to allow cancellation/timeouts
        final_state = await asyncio.to_thread(self.workflow.invoke, initial_state)
        return ResearchState(**final_state)

    def run(self, query: str) -> ResearchState:
        """Run the workflow synchronously (for CLI usage)"""
        return asyncio.run(self.run_async(query))

    def _sanitize_curated_tools(self, tools: List[str]) -> List[str]:
        banned_fragments = ["archives.gov", "fda.gov"]
        sanitized = []
        for tool in tools:
            if any(fragment in tool.lower() for fragment in banned_fragments):
                continue
            sanitized.append(tool)
        return sanitized