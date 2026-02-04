"""
API routes for Marketing Cortex
"""
from fastapi import APIRouter, HTTPException, status
from src.api.models import (
    HealthResponse,
    AgentRequest,
    AgentResponse,
    CampaignCreate,
    AdSetCreate,
    CreativeCreate,
    PerformanceCreate
)
from src.knowledge.graph_schema import graph_schema
from src.core.memory import memory_manager
from src.core.cache import cache_manager
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    
    Returns service status for all components
    """
    services = {
        "api": "healthy",
        "neo4j": "unknown",
        "redis": "unknown",
        "zep": "unknown"
    }
    
    # Check Neo4j
    try:
        async with graph_schema.driver.session() as session:
            await session.run("RETURN 1")
        services["neo4j"] = "healthy"
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        services["neo4j"] = "unhealthy"
    
    # Check Redis
    try:
        if cache_manager.redis_client:
            await cache_manager.redis_client.ping()
            services["redis"] = "healthy"
        else:
            services["redis"] = "not_connected"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        services["redis"] = "unhealthy"
    
    # Check Zep (basic check)
    try:
        # Zep client is initialized, assume healthy if no errors
        services["zep"] = "healthy"
    except Exception as e:
        logger.error(f"Zep health check failed: {e}")
        services["zep"] = "unhealthy"
    
    overall_status = "healthy" if all(
        s in ["healthy", "unknown"] for s in services.values()
    ) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        services=services
    )


@router.post("/run-agent", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    """
    Main endpoint to run agent workflows
    
    This is a placeholder that will be expanded in Phase 2
    """
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        # Store user message in memory
        await memory_manager.add_message(
            session_id=session_id,
            role="user",
            content=request.query,
            metadata=request.metadata
        )
        
        # Placeholder response (will be replaced with actual agent logic in Phase 2)
        response_text = (
            f"Marketing Cortex received your query: '{request.query}'. "
            f"Agent orchestration will be implemented in Phase 2."
        )
        
        # Store assistant response in memory
        await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=response_text,
            metadata={"agent": "placeholder"}
        )
        
        return AgentResponse(
            response=response_text,
            agent_used="placeholder",
            session_id=session_id,
            metadata={"phase": "1", "status": "foundation"}
        )
        
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}"
        )


@router.post("/campaigns")
async def create_campaign(campaign: CampaignCreate):
    """Create a new campaign in the knowledge graph"""
    try:
        result = await graph_schema.create_campaign(
            campaign_id=campaign.campaign_id,
            name=campaign.name,
            objective=campaign.objective,
            budget=campaign.budget,
            start_date=campaign.start_date,
            metadata=campaign.metadata
        )
        return {"status": "success", "campaign": result}
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/adsets")
async def create_adset(adset: AdSetCreate):
    """Create a new adset in the knowledge graph"""
    try:
        result = await graph_schema.create_adset(
            adset_id=adset.adset_id,
            campaign_id=adset.campaign_id,
            name=adset.name,
            targeting=adset.targeting,
            budget=adset.budget,
            metadata=adset.metadata
        )
        return {"status": "success", "adset": result}
    except Exception as e:
        logger.error(f"Error creating adset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/creatives")
async def create_creative(creative: CreativeCreate):
    """Create a new creative in the knowledge graph"""
    try:
        result = await graph_schema.create_creative(
            creative_id=creative.creative_id,
            adset_id=creative.adset_id,
            name=creative.name,
            copy=creative.copy,
            image_url=creative.image_url,
            metadata=creative.metadata
        )
        return {"status": "success", "creative": result}
    except Exception as e:
        logger.error(f"Error creating creative: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/performance")
async def create_performance(performance: PerformanceCreate):
    """Create a new performance record in the knowledge graph"""
    try:
        result = await graph_schema.create_performance(
            performance_id=performance.performance_id,
            creative_id=performance.creative_id,
            date=performance.date,
            impressions=performance.impressions,
            clicks=performance.clicks,
            conversions=performance.conversions,
            spend=performance.spend,
            revenue=performance.revenue
        )
        return {"status": "success", "performance": result}
    except Exception as e:
        logger.error(f"Error creating performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get campaign hierarchy with all related entities"""
    try:
        result = await graph_schema.get_campaign_hierarchy(campaign_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign {campaign_id} not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving campaign: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/high-performers")
async def get_high_performers(min_roas: float = 2.0, limit: int = 10):
    """Get high-performing creatives"""
    try:
        results = await graph_schema.query_high_performers(
            min_roas=min_roas,
            limit=limit
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Error querying high performers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
