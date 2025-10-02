from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import List, Optional
from dotenv import load_dotenv
from src.workflow import Workflow
from src.models import CompanyInfo
from src.config import settings
from src.logger import setup_logger, get_logger, log_request_start, log_request_complete
from src.validators import validate_search_query, sanitize_query
from contextlib import asynccontextmanager
import time
import uuid
import os
import certifi
import asyncio

load_dotenv()

# Ensure outbound HTTPS trusts system CAs reliably (fixes intermittent SSL/APIConnectionError)
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()

# Setup logging
logger = setup_logger()
api_logger = get_logger('api')

# Metrics tracking
search_counter = 0
search_success_counter = 0
search_failure_counter = 0
start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global workflow
    try:
        workflow = Workflow()
        api_logger.info("✅ Workflow initialized successfully")
    except Exception as e:
        api_logger.error(f"❌ Failed to initialize workflow: {e}")
        raise
    yield
    # Shutdown cleanup: close scraper session pool
    try:
        if workflow and hasattr(workflow, 'scraper'):
            await workflow.scraper.close()
    except Exception:
        pass

app = FastAPI(
    title="AI Research Agent API", 
    version="1.0.0", 
    lifespan=lifespan,
    description="AI-powered research agent for developer tools and technologies"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=False,  # Must be False when allow_origins is ["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Request/Response models
class ResearchRequest(BaseModel):
    query: str
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        is_valid, error_msg = validate_search_query(v)
        if not is_valid:
            raise ValueError(error_msg)
        return sanitize_query(v)

class CompanyResponse(BaseModel):
    name: str
    description: str
    website: str
    pricing_model: Optional[str] = None
    is_open_source: Optional[bool] = None
    tech_stack: List[str] = []
    api_available: Optional[bool] = None
    language_support: List[str] = []
    integration_capabilities: List[str] = []

class ResearchResponse(BaseModel):
    query: str
    companies: List[CompanyResponse]
    analysis: Optional[str] = None
    status: str = "success"
    request_id: str
    processing_time: float

class HealthResponse(BaseModel):
    status: str
    workflow_ready: bool
    uptime: float
    openai_key_set: bool
    google_custom_search_key_set: bool
    google_search_engine_id_set: bool
    search_providers: List[str]
    search_config: Optional[str]
    version: str = "1.0.0"

class MetricsResponse(BaseModel):
    total_searches: int
    successful_searches: int
    failed_searches: int
    success_rate: float
    uptime: float

# Initialize workflow reference
workflow = None

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Enhanced health check with configuration status"""
    if workflow and hasattr(workflow, 'scraper') and hasattr(workflow.scraper, 'search_manager'):
        available_providers = workflow.scraper.search_manager.get_available_providers()
    else:
        available_providers = []
    
    return HealthResponse(
        status="healthy",
        workflow_ready=workflow is not None,
        uptime=time.time() - start_time,
        openai_key_set=bool(settings.openai_api_key),
        google_custom_search_key_set=bool(settings.google_custom_search_api_key),
        google_search_engine_id_set=bool(settings.google_search_engine_id),
        search_providers=available_providers,
        search_config=settings.search_provider
    )

@app.get("/health/detailed")
async def detailed_health():
    """Detailed health check for debugging"""
    if workflow and hasattr(workflow, 'scraper') and hasattr(workflow.scraper, 'search_manager'):
        search_status = workflow.scraper.search_manager.get_provider_status()
        available_providers = workflow.scraper.search_manager.get_available_providers()
    else:
        search_status = {}
        available_providers = []
    
    return {
        "status": "healthy",
        "workflow_ready": workflow is not None,
        "openai_key_set": bool(settings.openai_api_key),
        "google_custom_search_key_set": bool(settings.google_custom_search_api_key),
        "google_search_engine_id_set": bool(settings.google_search_engine_id),
        "uptime": time.time() - start_time,
        "search_providers": {
            "available": available_providers,
            "status": search_status,
            "config": settings.search_provider
        },
        "config": {
            "max_search_results": settings.max_search_results,
            "max_concurrent_scrapes": settings.max_concurrent_scrapes,
            "scrape_timeout": settings.scrape_timeout
        }
    }

@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get API usage metrics"""
    total = search_counter
    success_rate = (search_success_counter / total * 100) if total > 0 else 0
    
    return MetricsResponse(
        total_searches=total,
        successful_searches=search_success_counter,
        failed_searches=search_failure_counter,
        success_rate=round(success_rate, 2),
        uptime=time.time() - start_time
    )

@app.post("/research", response_model=ResearchResponse)
async def research_tools(request: ResearchRequest, http_request: Request):
    """Enhanced research endpoint with validation, logging, and metrics"""
    global search_counter, search_success_counter, search_failure_counter
    
    search_counter += 1
    request_start = time.time()
    
    if not workflow:
        search_failure_counter += 1
        log_request_complete(api_logger, success=False, error="Workflow not initialized")
        raise HTTPException(status_code=503, detail="Workflow not initialized")
    
    # Log request start
    request_id = log_request_start(request.query, api_logger)
    
    try:
        api_logger.info(f"🔍 Processing research request: {request.query}")
        
        # Enforce a global timeout for the entire research flow
        try:
            result = await asyncio.wait_for(workflow.run_async(request.query), timeout=45.0)
        except asyncio.TimeoutError:
            processing_time = time.time() - request_start
            api_logger.warning("⏰ Research timed out at 45s; returning partial response")
            # Fetch partial results accumulated so far
            partial_companies = workflow.get_partial_results(request.query) if workflow else []
            companies = [
                CompanyResponse(
                    name=c.name,
                    description=c.description,
                    website=c.website,
                    pricing_model=c.pricing_model,
                    is_open_source=c.is_open_source,
                    tech_stack=c.tech_stack,
                    api_available=c.api_available,
                    language_support=c.language_support,
                    integration_capabilities=c.integration_capabilities
                ) for c in partial_companies
            ]
            # Try quick recommendations within a slightly larger budget
            quick_analysis = None
            try:
                quick_analysis = await asyncio.wait_for(workflow.quick_recommendations(request.query, partial_companies), timeout=3.0)  # Reduced from 5s
            except Exception:
                quick_analysis = "Timed out after 45 seconds; showing partial results."
            # Purge partial cache for this query
            try:
                workflow.clear_partial_results(request.query)
            except Exception:
                pass

            return ResearchResponse(
                query=request.query,
                companies=companies,
                analysis=quick_analysis,
                status="partial",
                request_id=request_id,
                processing_time=round(processing_time, 2)
            )
        
        companies = [
            CompanyResponse(
                name=company.name,
                description=company.description,
                website=company.website,
                pricing_model=company.pricing_model,
                is_open_source=company.is_open_source,
                tech_stack=company.tech_stack,
                api_available=company.api_available,
                language_support=company.language_support,
                integration_capabilities=company.integration_capabilities
            )
            for company in result.companies
        ]
        
        processing_time = time.time() - request_start
        search_success_counter += 1
        
        # Single consolidated success log to avoid duplication
        api_logger.info(f"✅ Research completed successfully in {processing_time:.2f}s")
        
        # Purge partial cache for this query on success
        try:
            workflow.clear_partial_results(request.query)
        except Exception:
            pass

        return ResearchResponse(
            query=result.query,
            companies=companies,
            analysis=result.analysis,
            request_id=request_id,
            processing_time=round(processing_time, 2)
        )
        
    except Exception as e:
        search_failure_counter += 1
        processing_time = time.time() - request_start
        
        api_logger.error(f"❌ Research failed: {str(e)}")
        log_request_complete(api_logger, success=False, error=str(e))
        
        raise HTTPException(
            status_code=500, 
            detail=f"Research failed: {str(e)}"
        )

@app.get("/examples")
async def get_example_queries():
    """Get example search queries"""
    return {
        "examples": [
            "Python web frameworks",
            "JavaScript testing tools", 
            "React state management libraries",
            "Database management tools",
            "CI/CD platforms",
            "API development tools",
            "Machine learning libraries",
            "DevOps automation tools"
        ]
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for better error reporting"""
    api_logger.error(f"Unhandled exception: {str(exc)}")
    return HTTPException(
        status_code=500,
        detail="Internal server error"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )