"""
Pydantic models for API requests and responses
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    services: Dict[str, str]


class AgentRequest(BaseModel):
    """Request to run an agent"""
    query: str = Field(..., description="User query for the agent")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_id: Optional[str] = Field(None, description="User identifier")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class AgentResponse(BaseModel):
    """Response from an agent"""
    response: str = Field(..., description="Agent's response")
    agent_used: str = Field(..., description="Which agent handled the request")
    session_id: str = Field(..., description="Session identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CampaignCreate(BaseModel):
    """Request to create a campaign"""
    campaign_id: str
    name: str
    objective: str
    budget: float
    start_date: str
    metadata: Optional[Dict] = None


class AdSetCreate(BaseModel):
    """Request to create an adset"""
    adset_id: str
    campaign_id: str
    name: str
    targeting: Dict
    budget: float
    metadata: Optional[Dict] = None


class CreativeCreate(BaseModel):
    """Request to create a creative"""
    creative_id: str
    adset_id: str
    name: str
    ad_copy: str = Field(..., description="The advertising copy text")
    image_url: Optional[str] = None
    metadata: Optional[Dict] = None


class PerformanceCreate(BaseModel):
    """Request to create a performance record"""
    performance_id: str
    creative_id: str
    date: str
    impressions: int
    clicks: int
    conversions: int
    spend: float
    revenue: float


class BlogIngestRequest(BaseModel):
    """Request to ingest blog content"""
    blog_url: str = Field(..., description="RSS feed URL")
    blog_name: str = Field(..., description="Name of the blog")
    max_posts: int = Field(50, description="Maximum number of posts to ingest")


class BlogIngestResponse(BaseModel):
    """Response from blog ingestion"""
    status: str
    blog_name: str
    posts_ingested: int
    chunks_created: int
    errors: int
    total_entries: Optional[int] = None
    message: Optional[str] = None


class BlogRefreshRequest(BaseModel):
    """Request to refresh blog content"""
    blog_name: Optional[str] = Field(None, description="Blog name to refresh, or None for all blogs")


class BlogSource(BaseModel):
    """Blog source information"""
    name: str
    url: str
    total_posts: int = 0
    last_updated: Optional[str] = None


class BlogSourcesResponse(BaseModel):
    """Response with list of blog sources"""
    sources: List[BlogSource]


class EntitySearchRequest(BaseModel):
    """Request to search entities"""
    query: str = Field(..., description="Search query for entities")
    entity_types: Optional[List[str]] = Field(None, description="Optional entity type filters")
    limit: int = Field(10, description="Maximum number of results")


class EntityResponse(BaseModel):
    """Entity information"""
    id: str
    name: str
    entity_type: str
    confidence: float
    metadata: Optional[Dict[str, Any]] = None


class EntitySearchResponse(BaseModel):
    """Response with entity search results"""
    entities: List[EntityResponse]


class EntityContextResponse(BaseModel):
    """Response with entity context"""
    entity: Optional[EntityResponse] = None
    related_entities: List[Dict[str, Any]] = Field(default_factory=list)
    blog_posts: List[Dict[str, Any]] = Field(default_factory=list)


class EntityExtractionRequest(BaseModel):
    """Request to manually trigger entity extraction"""
    content: str = Field(..., description="Content to extract entities from")
    url: Optional[str] = Field(None, description="Optional URL for linking")


class EntityExtractionResponse(BaseModel):
    """Response from entity extraction"""
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)