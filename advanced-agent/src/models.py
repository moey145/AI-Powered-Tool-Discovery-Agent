from enum import StrEnum
from typing import Literal, TypedDict

from pydantic import BaseModel, Field, field_validator

PricingPreference = Literal["any", "free", "freemium", "paid"]
ResearchStatus = Literal["success", "partial", "no_results"]
MaintenanceStatus = Literal["active", "slowing", "stale", "archived"]


class PricingModel(StrEnum):
    FREE = "Free"
    FREEMIUM = "Freemium"
    PAID = "Paid"
    ENTERPRISE = "Enterprise"
    UNKNOWN = "Unknown"


# LLM output schemas. Every field is required (nullable where the answer can be unknown)
# because OpenAI's strict structured output does not accept default values.
class ToolDiscovery(BaseModel):
    tools: list[str] = Field(description="Names of specific products named in the sources")
    pricing_preference: PricingPreference = Field(
        description="Pricing the user asked for, or 'any' if they did not ask"
    )


class ToolAnalysis(BaseModel):
    describes_requested_tool: bool = Field(
        description="False if the sources only describe a different product with the same name"
    )
    relevant_sources: list[str] = Field(
        description="Source labels, copied exactly, that are about the requested tool"
    )
    description: str = Field(description="One or two factual sentences on what the tool does")
    website: str | None = Field(description="Official website, only if present in the sources")
    pricing_model: PricingModel = Field(description="Use Unknown unless the sources say")
    is_open_source: bool | None = Field(description="Null unless the sources say")
    api_available: bool | None = Field(description="Null unless the sources say")
    tech_stack: list[str]
    language_support: list[str]
    integration_capabilities: list[str]


class CompanyInfo(BaseModel):
    name: str
    description: str
    website: str | None = None
    pricing_model: PricingModel = PricingModel.UNKNOWN
    is_open_source: bool | None = None
    api_available: bool | None = None
    tech_stack: list[str] = Field(default_factory=list)
    language_support: list[str] = Field(default_factory=list)
    integration_capabilities: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    github_url: str | None = None
    github_stars: int | None = None
    license: str | None = None
    last_commit: str | None = None
    maintenance: MaintenanceStatus | None = None


class ResearchResult(BaseModel):
    query: str
    companies: list[CompanyInfo] = Field(default_factory=list)
    analysis: str | None = None
    status: ResearchStatus = "success"
    unresearched: list[str] = Field(default_factory=list)
    pricing_preference: PricingPreference = "any"


class ResearchState(TypedDict, total=False):
    query: str
    tools: list[str]
    pricing_preference: PricingPreference
    companies: list[CompanyInfo]
    unresearched: list[str]
    analysis: str | None


class ResearchRequest(BaseModel):
    query: str

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        cleaned = " ".join("".join(ch for ch in value if ch.isprintable()).split())
        if len(cleaned) < 2:
            raise ValueError("Query must be at least 2 characters long")
        if len(cleaned) > 200:
            raise ValueError("Query must be 200 characters or fewer")
        return cleaned


class ResearchResponse(ResearchResult):
    request_id: str
    processing_time: float
