"""
Advanced Query Expansion and Synonym Detection System
Enhances search queries with synonyms, related terms, and technology-specific expansions
"""

import re
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from enum import Enum

class QueryType(Enum):
    LANGUAGE_SPECIFIC = "language_specific"
    FRAMEWORK_SPECIFIC = "framework_specific"
    TOOL_SPECIFIC = "tool_specific"
    CATEGORY_SPECIFIC = "category_specific"
    COMPARISON = "comparison"
    TUTORIAL = "tutorial"
    DOCUMENTATION = "documentation"
    GENERAL = "general"

@dataclass
class ExpandedQuery:
    original: str
    expanded_terms: List[str]
    query_type: QueryType
    confidence: float
    search_strategies: List[str]

class QueryExpansionEngine:
    """Advanced query expansion with technology-specific knowledge"""
    
    def __init__(self):
        self.synonym_maps = self._build_synonym_maps()
        self.technology_patterns = self._build_technology_patterns()
        self.search_strategies = self._build_search_strategies()
        
    def _build_synonym_maps(self) -> Dict[str, List[str]]:
        """Build comprehensive synonym maps for developer tools and technologies"""
        return {
            # Programming Languages
            "javascript": ["js", "ecmascript", "nodejs", "node.js", "typescript", "ts"],
            "python": ["py", "python3", "python2"],
            "java": ["jvm", "jdk", "jre"],
            "c++": ["cpp", "cplusplus", "cxx"],
            "c#": ["csharp", "dotnet", ".net", "dotnetcore"],
            "go": ["golang"],
            "rust": ["rustlang"],
            "php": ["php7", "php8"],
            "ruby": ["rb", "ruby-on-rails", "rails"],
            "swift": ["swiftui"],
            "kotlin": ["kt"],
            "dart": ["flutter"],
            
            # Frameworks & Libraries
            "react": ["reactjs", "react.js", "jsx"],
            "vue": ["vuejs", "vue.js"],
            "angular": ["angularjs", "angular2", "ng"],
            "django": ["djangoproject"],
            "flask": ["flask-python"],
            "express": ["expressjs", "express.js"],
            "spring": ["springboot", "spring-boot", "springframework"],
            "laravel": ["laravel-php"],
            "rails": ["ruby-on-rails", "ror"],
            "asp.net": ["aspnet", "aspnetcore"],
            
            # Testing
            "testing": ["test", "tests", "unit-testing", "integration-testing", "e2e", "end-to-end"],
            "jest": ["jestjs", "jest.js"],
            "mocha": ["mochajs", "mocha.js"],
            "cypress": ["cypress.io"],
            "selenium": ["selenium-webdriver"],
            "pytest": ["py.test", "python-testing"],
            "junit": ["junit5", "junit4"],
            "vitest": ["vitestjs"],
            "playwright": ["playwrightjs"],
            
            # Databases
            "database": ["db", "databases", "sql", "nosql"],
            "postgresql": ["postgres", "postgresql"],
            "mysql": ["mysql-server"],
            "mongodb": ["mongo", "mongodb"],
            "redis": ["redis-cache"],
            "sqlite": ["sqlite3"],
            
            # Cloud & DevOps
            "aws": ["amazon-web-services", "amazon-aws"],
            "azure": ["microsoft-azure"],
            "gcp": ["google-cloud", "google-cloud-platform"],
            "docker": ["docker-container", "dockerfile"],
            "kubernetes": ["k8s", "kube"],
            "terraform": ["terraform-aws"],
            
            # Web Development
            "web": ["web-development", "webdev", "frontend", "backend", "fullstack"],
            "frontend": ["front-end", "client-side", "ui", "ux"],
            "backend": ["back-end", "server-side", "api"],
            "api": ["rest-api", "graphql", "web-api"],
            "responsive": ["mobile-friendly", "responsive-design"],
            
            # Mobile Development
            "mobile": ["mobile-development", "mobile-app", "ios", "android"],
            "react-native": ["reactnative", "rn"],
            "flutter": ["flutter-dart"],
            "xamarin": ["xamarin-forms"],
            "ionic": ["ionic-framework"],
            
            # AI/ML
            "ai": ["artificial-intelligence", "machine-learning", "ml"],
            "machine-learning": ["ml", "deep-learning", "neural-networks"],
            "tensorflow": ["tf", "tensorflow-js"],
            "pytorch": ["torch"],
            "scikit-learn": ["sklearn"],
            
            # Tools & Utilities
            "ide": ["integrated-development-environment", "code-editor"],
            "vscode": ["visual-studio-code", "vs-code"],
            "git": ["git-version-control", "github", "gitlab"],
            "npm": ["node-package-manager"],
            "yarn": ["yarn-package-manager"],
            "webpack": ["webpack-bundler"],
            "babel": ["babeljs"],
            
            # Pricing Models
            "free": ["open-source", "opensource", "gratis", "no-cost", "foss"],
            "paid": ["premium", "commercial", "enterprise", "subscription", "licensed"],
            "freemium": ["trial", "demo", "basic", "pro", "upgrade"],
        }
    
    def _build_technology_patterns(self) -> Dict[str, List[str]]:
        """Build patterns for detecting technology-specific queries"""
        return {
            "web_frameworks": [
                "react", "vue", "angular", "svelte", "nextjs", "nuxt", "gatsby",
                "django", "flask", "fastapi", "express", "koa", "hapi",
                "spring", "struts", "play", "spark", "laravel", "symfony",
                "rails", "sinatra", "hanami", "asp.net", "blazor"
            ],
            "testing_frameworks": [
                "jest", "mocha", "chai", "cypress", "playwright", "selenium",
                "pytest", "unittest", "nose", "behave", "junit", "testng",
                "mockito", "assertj", "cucumber", "specflow", "vitest"
            ],
            "databases": [
                "postgresql", "mysql", "mongodb", "redis", "sqlite", "oracle",
                "sqlserver", "mariadb", "cassandra", "elasticsearch", "neo4j"
            ],
            "cloud_platforms": [
                "aws", "azure", "gcp", "heroku", "vercel", "netlify", "digitalocean",
                "linode", "vultr", "cloudflare", "firebase", "supabase"
            ],
            "mobile_frameworks": [
                "react-native", "flutter", "xamarin", "ionic", "cordova", "phonegap",
                "swift", "kotlin", "objective-c", "dart"
            ],
            "ai_ml_tools": [
                "tensorflow", "pytorch", "scikit-learn", "keras", "opencv",
                "pandas", "numpy", "matplotlib", "seaborn", "plotly"
            ]
        }
    
    def _build_search_strategies(self) -> Dict[QueryType, List[str]]:
        """Build search strategies for different query types"""
        return {
            QueryType.LANGUAGE_SPECIFIC: [
                "official documentation",
                "getting started guide", 
                "tutorial",
                "best practices",
                "ecosystem tools",
                "libraries frameworks"
            ],
            QueryType.FRAMEWORK_SPECIFIC: [
                "official docs",
                "tutorial guide",
                "examples",
                "comparison",
                "alternatives",
                "migration guide"
            ],
            QueryType.TOOL_SPECIFIC: [
                "official website",
                "documentation",
                "features",
                "pricing",
                "alternatives",
                "reviews"
            ],
            QueryType.CATEGORY_SPECIFIC: [
                "best tools",
                "comparison",
                "alternatives",
                "overview",
                "guide",
                "recommendations"
            ],
            QueryType.COMPARISON: [
                "vs comparison",
                "alternatives",
                "pros cons",
                "differences",
                "which to choose",
                "benchmark"
            ],
            QueryType.TUTORIAL: [
                "tutorial",
                "getting started",
                "beginner guide",
                "step by step",
                "examples",
                "how to"
            ],
            QueryType.DOCUMENTATION: [
                "official docs",
                "documentation",
                "api reference",
                "guide",
                "manual",
                "specification"
            ],
            QueryType.GENERAL: [
                "overview",
                "introduction",
                "guide",
                "best practices",
                "tools",
                "alternatives"
            ]
        }
    
    def expand_query(self, query: str) -> ExpandedQuery:
        """Expand a query with synonyms, related terms, and search strategies"""
        query_lower = query.lower().strip()
        
        # Detect query type
        query_type = self._detect_query_type(query_lower)
        
        # Extract base terms
        base_terms = self._extract_base_terms(query_lower)
        
        # Expand with synonyms
        expanded_terms = self._expand_with_synonyms(base_terms)
        
        # Add technology-specific terms
        tech_terms = self._add_technology_terms(query_lower, query_type)
        expanded_terms.extend(tech_terms)
        
        # Add search strategies
        strategies = self._get_search_strategies(query_type)
        
        # Calculate confidence based on expansion quality
        confidence = self._calculate_confidence(query_lower, expanded_terms, query_type)
        
        return ExpandedQuery(
            original=query,
            expanded_terms=expanded_terms,
            query_type=query_type,
            confidence=confidence,
            search_strategies=strategies
        )
    
    def _detect_query_type(self, query: str) -> QueryType:
        """Detect the type of query to determine expansion strategy"""
        query_lower = query.lower()
        
        # Language-specific queries
        languages = ["javascript", "python", "java", "c++", "c#", "go", "rust", "php", "ruby", "swift", "kotlin", "dart", "typescript"]
        if any(lang in query_lower for lang in languages):
            return QueryType.LANGUAGE_SPECIFIC
        
        # Framework-specific queries
        frameworks = ["react", "vue", "angular", "django", "flask", "express", "spring", "laravel", "rails", "asp.net"]
        if any(fw in query_lower for fw in frameworks):
            return QueryType.FRAMEWORK_SPECIFIC
        
        # Tool-specific queries (specific tool names)
        if any(word in query_lower for word in ["jest", "mocha", "cypress", "selenium", "docker", "kubernetes", "aws", "azure"]):
            return QueryType.TOOL_SPECIFIC
        
        # Comparison queries
        if any(word in query_lower for word in ["vs", "versus", "compare", "comparison", "better", "best", "alternatives"]):
            return QueryType.COMPARISON
        
        # Tutorial queries
        if any(word in query_lower for word in ["tutorial", "learn", "guide", "how to", "getting started", "beginner"]):
            return QueryType.TUTORIAL
        
        # Documentation queries
        if any(word in query_lower for word in ["docs", "documentation", "api", "reference", "manual"]):
            return QueryType.DOCUMENTATION
        
        # Category-specific queries
        if any(word in query_lower for word in ["testing", "database", "cloud", "mobile", "ai", "ml", "web", "devops"]):
            return QueryType.CATEGORY_SPECIFIC
        
        return QueryType.GENERAL
    
    def _extract_base_terms(self, query: str) -> List[str]:
        """Extract base terms from query, removing common qualifiers"""
        # Remove common qualifiers
        qualifiers = {
            "paid", "free", "open source", "premium", "commercial", "enterprise",
            "best", "top", "popular", "recommended", "tools", "libraries", 
            "frameworks", "platforms", "alternatives", "for", "in", "and", "or",
            "the", "a", "an", "how", "to", "what", "is", "are", "do", "does"
        }
        
        words = re.findall(r'\b\w+\b', query.lower())
        base_terms = [word for word in words if word not in qualifiers and len(word) > 2]
        
        return base_terms
    
    def _expand_with_synonyms(self, base_terms: List[str]) -> List[str]:
        """Expand base terms with synonyms"""
        expanded = set(base_terms)
        
        for term in base_terms:
            if term in self.synonym_maps:
                expanded.update(self.synonym_maps[term])
        
        return list(expanded)
    
    def _add_technology_terms(self, query: str, query_type: QueryType) -> List[str]:
        """Add technology-specific terms based on query type"""
        tech_terms = []
        
        if query_type == QueryType.LANGUAGE_SPECIFIC:
            # Add ecosystem terms
            if "javascript" in query:
                tech_terms.extend(["nodejs", "npm", "yarn", "webpack", "babel"])
            elif "python" in query:
                tech_terms.extend(["pip", "conda", "virtualenv", "pytest"])
            elif "java" in query:
                tech_terms.extend(["maven", "gradle", "jvm", "jdk"])
            elif "c++" in query:
                tech_terms.extend(["cmake", "make", "gcc", "clang"])
            elif "go" in query:
                tech_terms.extend(["go modules", "gofmt", "golang"])
            elif "rust" in query:
                tech_terms.extend(["cargo", "crates", "rustup"])
        
        elif query_type == QueryType.FRAMEWORK_SPECIFIC:
            # Add related frameworks and tools
            if "react" in query:
                tech_terms.extend(["jsx", "hooks", "redux", "nextjs"])
            elif "vue" in query:
                tech_terms.extend(["vuex", "nuxt", "vue-cli"])
            elif "angular" in query:
                tech_terms.extend(["typescript", "rxjs", "angular-cli"])
            elif "django" in query:
                tech_terms.extend(["django-rest", "django-admin", "django-orm"])
            elif "flask" in query:
                tech_terms.extend(["jinja2", "werkzeug", "flask-restful"])
        
        elif query_type == QueryType.TESTING:
            # Add testing-related terms
            tech_terms.extend(["unit testing", "integration testing", "e2e testing", "tdd", "bdd"])
        
        return tech_terms
    
    def _get_search_strategies(self, query_type: QueryType) -> List[str]:
        """Get search strategies for the query type"""
        return self.search_strategies.get(query_type, self.search_strategies[QueryType.GENERAL])
    
    def _calculate_confidence(self, query: str, expanded_terms: List[str], query_type: QueryType) -> float:
        """Calculate confidence score for the expansion"""
        base_score = 0.5
        
        # Boost for specific query types
        if query_type in [QueryType.LANGUAGE_SPECIFIC, QueryType.FRAMEWORK_SPECIFIC, QueryType.TOOL_SPECIFIC]:
            base_score += 0.2
        
        # Boost for good expansion
        if len(expanded_terms) > len(query.split()):
            base_score += 0.2
        
        # Boost for technology pattern matches
        for pattern_name, patterns in self.technology_patterns.items():
            if any(pattern in query for pattern in patterns):
                base_score += 0.1
                break
        
        return min(base_score, 1.0)
    
    def generate_search_queries(self, expanded_query: ExpandedQuery, max_queries: int = 5) -> List[str]:
        """Generate multiple search query variants"""
        queries = []
        
        # Original query
        queries.append(expanded_query.original)
        
        # Expanded terms query
        if expanded_query.expanded_terms:
            expanded_query_str = " ".join(expanded_query.expanded_terms[:10])  # Limit to 10 terms
            queries.append(expanded_query_str)
        
        # Strategy-based queries
        for strategy in expanded_query.search_strategies[:max_queries-2]:
            strategy_query = f"{expanded_query.original} {strategy}"
            queries.append(strategy_query)
        
        # Technology-specific queries
        if expanded_query.query_type == QueryType.LANGUAGE_SPECIFIC:
            queries.append(f"{expanded_query.original} ecosystem tools libraries")
        elif expanded_query.query_type == QueryType.FRAMEWORK_SPECIFIC:
            queries.append(f"{expanded_query.original} alternatives comparison")
        elif expanded_query.query_type == QueryType.TOOL_SPECIFIC:
            queries.append(f"{expanded_query.original} official documentation")
        
        return queries[:max_queries]

# Example usage and testing
if __name__ == "__main__":
    engine = QueryExpansionEngine()
    
    test_queries = [
        "JavaScript testing frameworks",
        "Paid Kotlin tools",
        "Free Python web frameworks",
        "React vs Vue comparison",
        "Docker tutorial",
        "AWS documentation",
        "Machine learning libraries"
    ]
    
    for query in test_queries:
        expanded = engine.expand_query(query)
        search_queries = engine.generate_search_queries(expanded)
        
        print(f"\nOriginal: {query}")
        print(f"Type: {expanded.query_type.value}")
        print(f"Confidence: {expanded.confidence:.2f}")
        print(f"Expanded terms: {expanded.expanded_terms[:5]}")
        print(f"Search queries: {search_queries}")
