from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

class PricingModel(str, Enum):
    FREE = "Free"
    FREEMIUM = "Freemium"
    PAID = "Paid"
    ENTERPRISE = "Enterprise"
    UNKNOWN = "Unknown"

class OpenSourceStatus(str, Enum):
    OPEN_SOURCE = "Open Source"
    PROPRIETARY = "Proprietary"
    UNKNOWN = "Unknown"

class CompanyAnalysis(BaseModel):
    name: Optional[str] = Field(None, description="Company/tool name")
    description: Optional[str] = Field(None, description="Brief description")
    website: Optional[str] = Field(None, description="Official website")
    pricing_model: Optional[PricingModel] = Field(None, description="Pricing model")
    is_open_source: Optional[bool] = Field(None, description="Open source status")
    tech_stack: List[str] = Field(default_factory=list, description="Supported technologies")
    api_available: Optional[bool] = Field(None, description="API availability")
    language_support: List[str] = Field(default_factory=list, description="Supported languages")
    integration_capabilities: List[str] = Field(default_factory=list, description="Integration options")
    
    @validator('website')
    def validate_website(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            return f"https://{v}"
        return v

class CompanyInfo(BaseModel):
    name: str = Field(..., description="Company/tool name")
    description: str = Field(..., description="Description")
    website: str = Field(..., description="Website URL")
    pricing_model: Optional[PricingModel] = Field(None, description="Pricing model")
    is_open_source: Optional[bool] = Field(None, description="Open source status")
    tech_stack: List[str] = Field(default_factory=list, description="Technology stack")
    competitors: List[str] = Field(default_factory=list, description="Competitors")
    api_available: Optional[bool] = Field(None, description="API availability")
    language_support: List[str] = Field(default_factory=list, description="Language support")
    integration_capabilities: List[str] = Field(default_factory=list, description="Integrations")
    developer_experience_rating: Optional[str] = Field(None, description="Developer experience rating")
    
    # Enhanced metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Analysis timestamp")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Analysis confidence")
    
    @validator('website')
    def validate_website(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            return f"https://{v}"
        return v

class ResearchState(BaseModel):
    query: str = Field(..., description="Original search query")
    extracted_tools: List[str] = Field(default_factory=list, description="Extracted tool names")
    companies: List[CompanyInfo] = Field(default_factory=list, description="Analyzed companies")
    search_results: List[Dict[str, Any]] = Field(default_factory=list, description="Raw search results")
    analysis: Optional[str] = Field(None, description="Final analysis")
    
    # Enhanced tracking
    workflow_stages: List[str] = Field(default_factory=list, description="Completed workflow stages")
    errors: List[str] = Field(default_factory=list, description="Errors encountered")
    processing_time: Optional[float] = Field(None, description="Total processing time")
    
    @validator('query')
    def validate_query(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Query must be at least 2 characters long")
        return v.strip()

class SearchResult(BaseModel):
    """Enhanced search result model"""
    url: str = Field(..., description="Result URL")
    title: str = Field(..., description="Result title")
    snippet: str = Field(..., description="Result snippet")
    source: str = Field(..., description="Data source")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    relevance_score: Optional[float] = Field(None, ge=0, le=1, description="Relevance score")
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v