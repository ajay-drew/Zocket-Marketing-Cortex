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
    copy: str
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
