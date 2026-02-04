"""
API routes for Marketing Cortex
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from src.api.models import (
    HealthResponse,
    AgentRequest,
    AgentResponse,
    CampaignCreate,
    AdSetCreate,
    CreativeCreate,
    PerformanceCreate,
    BlogIngestRequest,
    BlogIngestResponse,
    BlogRefreshRequest,
    BlogSourcesResponse,
    BlogSource
)
from src.knowledge.graph_schema import graph_schema
from src.core.memory import memory_manager
from src.core.cache import cache_manager
from src.integrations.tavily_client import tavily_client
from src.agents.research_assistant import research_assistant
from datetime import datetime
import logging
import uuid
import json

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Lazy initialization of blog ingestion client
_blog_ingestion_client = None

def get_blog_ingestion_client():
    """Lazy initialization of blog ingestion client"""
    global _blog_ingestion_client
    if _blog_ingestion_client is None:
        try:
            from src.integrations.blog_ingestion import BlogIngestionClient
            _blog_ingestion_client = BlogIngestionClient()
        except ImportError as e:
            logger.warning(f"Blog ingestion dependencies not available: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Blog ingestion service is not available. Please install required dependencies: feedparser, readability-lxml, beautifulsoup4, lxml"
            )
    return _blog_ingestion_client


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health & Status"],
    summary="Health Check",
    description="Health check endpoint. Returns service status for all components (API, Neo4j, Redis, Zep)."
)
async def health_check():
    """
    Health check endpoint
    
    Returns service status for all components
    """
    logger.info("[HEALTH] Health check requested")
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
    
    # Check Redis (synchronous)
    try:
        if cache_manager.redis_client:
            result = cache_manager.redis_client.ping()
            logger.debug(f"Redis ping result: {result}")
            services["redis"] = "healthy"
        else:
            logger.warning("Redis client is None")
            services["redis"] = "not_connected"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}", exc_info=True)
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


@router.post(
    "/run-agent",
    response_model=AgentResponse,
    tags=["Agent Operations"],
    summary="Run Agent Query (Non-Streaming)",
    description="Run agent query and get complete response. For streaming responses, use /api/agent/stream"
)
async def run_agent(request: AgentRequest):
    """
    Main endpoint to run agent workflows (non-streaming)
    
    For streaming responses, use /api/agent/stream
    """
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        # Get response from Research Assistant
        response_text = await research_assistant.get_response(
            query=request.query,
            session_id=session_id,
            metadata=request.metadata
        )
        
        return AgentResponse(
            response=response_text,
            agent_used="research_assistant",
            session_id=session_id,
            metadata={"phase": "2", "status": "complete"}
        )
        
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}"
        )


@router.post(
    "/agent/stream",
    tags=["Agent Operations"],
    summary="Stream Agent Response (SSE)",
    description="Stream agent responses using Server-Sent Events (SSE). Returns streaming tokens in SSE format.",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream with agent response tokens",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "example": "data: {\"type\": \"token\", \"content\": \"Hello\"}\n\n"
                    }
                }
            }
        },
        404: {"description": "Endpoint not found"},
        500: {"description": "Internal server error"}
    }
)
async def stream_agent(request: AgentRequest):
    """
    SSE endpoint for streaming agent responses
    
    Returns Server-Sent Events (SSE) stream with agent response tokens.
    Each event is a JSON object with type ('start', 'token', 'done', 'error') and content.
    """
    import json
    
    # Log that the endpoint was hit
    logger.info("=" * 60)
    logger.info("[STREAM] ENDPOINT HIT - /api/agent/stream")
    logger.info("=" * 60)
    
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    logger.info(f"[STREAM] Received request - Session: {session_id}, Query: {request.query[:100]}...")
    logger.debug(f"[STREAM] Full request: {request}")
    
    async def generate_stream():
        """Generator for SSE events"""
        try:
            logger.info(f"[STREAM] Starting stream for session: {session_id}")
            
            # Send initial event
            yield f"data: {json.dumps({'type': 'start', 'session_id': session_id})}\n\n"
            logger.debug(f"[STREAM] Sent start event for session: {session_id}")
            
            # Stream response from Research Assistant
            full_response = ""
            chunk_count = 0
            
            logger.info(f"[STREAM] Calling research_assistant.stream_response for query: {request.query[:50]}...")
            
            async for chunk in research_assistant.stream_response(
                query=request.query,
                session_id=session_id,
                metadata=request.metadata
            ):
                chunk_count += 1
                full_response += chunk
                
                # Log every 10th chunk to avoid spam
                if chunk_count % 10 == 0:
                    logger.debug(f"[STREAM] Chunk {chunk_count} - Total length: {len(full_response)}")
                
                # Send data event
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            
            logger.info(f"[STREAM] Completed streaming - Total chunks: {chunk_count}, Response length: {len(full_response)}")
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
            logger.debug(f"[STREAM] Sent done event for session: {session_id}")
            
        except Exception as e:
            logger.error(f"[STREAM] Error in SSE stream for session {session_id}: {e}", exc_info=True)
            # Send error event
            error_msg = str(e)
            logger.error(f"[STREAM] Sending error event: {error_msg}")
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
    
    logger.info(f"[STREAM] Returning StreamingResponse for session: {session_id}")
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post(
    "/campaigns",
    tags=["Campaign Management"],
    summary="Create Campaign",
    description="Create a new campaign in the knowledge graph"
)
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


@router.post(
    "/adsets",
    tags=["AdSet Management"],
    summary="Create AdSet",
    description="Create a new adset in the knowledge graph"
)
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


@router.post(
    "/creatives",
    tags=["Creative Management"],
    summary="Create Creative",
    description="Create a new creative in the knowledge graph"
)
async def create_creative(creative: CreativeCreate):
    """Create a new creative in the knowledge graph"""
    try:
        result = await graph_schema.create_creative(
            creative_id=creative.creative_id,
            adset_id=creative.adset_id,
            name=creative.name,
            copy=creative.ad_copy,
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


@router.post(
    "/performance",
    tags=["Performance Tracking"],
    summary="Add Performance Data",
    description="Create a new performance record in the knowledge graph"
)
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


@router.get(
    "/campaigns/{campaign_id}",
    tags=["Campaign Management"],
    summary="Get Campaign",
    description="Get campaign hierarchy with all related entities (adsets, creatives, performance)"
)
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


@router.get(
    "/high-performers",
    tags=["Performance Tracking"],
    summary="Query High Performers",
    description="Get high-performing creatives filtered by minimum ROAS"
)
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


@router.get(
    "/tavily/quota",
    tags=["Tavily Search & Rate Limiting"],
    summary="Get Tavily Quota Status",
    description="Get current Tavily API quota usage and status"
)
async def get_tavily_quota():
    """
    Get Tavily API quota status
    
    Returns:
        Current usage statistics and quota information
    """
    try:
        quota_status = await tavily_client.get_quota_status()
        return quota_status
    except Exception as e:
        logger.error(f"Error getting Tavily quota: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/tavily/search",
    tags=["Tavily Search & Rate Limiting"],
    summary="Tavily Search",
    description="Search using Tavily API with rate limiting and caching. Supports different search types (general, news, competitor, research) with different cache TTLs."
)
async def tavily_search(
    query: str,
    search_type: str = "general",
    max_results: int = 5,
    force_refresh: bool = False
):
    """
    Search using Tavily API with rate limiting and caching
    
    Args:
        query: Search query
        search_type: Type of search (general, news, competitor, research)
        max_results: Maximum number of results (default: 5)
        force_refresh: Skip cache and force new API call
        
    Returns:
        Search results with caching metadata
    """
    try:
        # Use fallback-enabled search
        results = await tavily_client.search_with_fallback(
            query=query,
            search_type=search_type,
            max_results=max_results
        )
        return results
    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete(
    "/tavily/cache",
    tags=["Tavily Search & Rate Limiting"],
    summary="Clear Tavily Cache",
    description="Clear Tavily cache entries. Omit search_type to clear all, or specify a specific search type."
)
async def clear_tavily_cache(search_type: str = None):
    """
    Clear Tavily cache
    
    Args:
        search_type: Specific search type to clear (optional)
        
    Returns:
        Number of cache entries cleared
    """
    try:
        cleared = await tavily_client.clear_cache(search_type)
        return {
            "cleared": cleared,
            "search_type": search_type or "all"
        }
    except Exception as e:
        logger.error(f"Error clearing Tavily cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/blogs/ingest",
    response_model=BlogIngestResponse,
    tags=["Blog Management"],
    summary="Ingest Blog Content",
    description="Fetch and ingest blog posts from an RSS feed into Pinecone vector store"
)
async def ingest_blog(request: BlogIngestRequest):
    """
    Ingest blog content from RSS feed
    
    Fetches RSS feed, extracts article content, chunks it, and stores in Pinecone.
    """
    try:
        blog_ingestion_client = get_blog_ingestion_client()
        logger.info(f"Ingesting blog: {request.blog_name} from {request.blog_url}")
        result = await blog_ingestion_client.ingest_blog(
            blog_name=request.blog_name,
            feed_url=request.blog_url,
            max_posts=request.max_posts
        )
        return BlogIngestResponse(**result)
    except Exception as e:
        logger.error(f"Error ingesting blog: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Blog ingestion failed: {str(e)}"
        )


@router.post(
    "/blogs/refresh",
    tags=["Blog Management"],
    summary="Refresh Blog Content",
    description="Refresh blog content by fetching new posts from RSS feeds. Specify blog_name or omit to refresh all."
)
async def refresh_blog(request: BlogRefreshRequest):
    """
    Refresh blog content
    
    Refreshes content for a specific blog or all configured blogs.
    """
    try:
        from src.config import settings
        from src.knowledge.vector_store import vector_store
        
        if request.blog_name:
            # Refresh specific blog
            blog_source = next(
                (b for b in settings.blog_sources if b["name"] == request.blog_name),
                None
            )
            if not blog_source:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Blog '{request.blog_name}' not found in configured sources"
                )
            
            blog_ingestion_client = get_blog_ingestion_client()
            logger.info(f"Refreshing blog: {request.blog_name}")
            result = await blog_ingestion_client.ingest_blog(
                blog_name=blog_source["name"],
                feed_url=blog_source["url"],
                max_posts=50
            )
            return result
        else:
            # Refresh all blogs
            blog_ingestion_client = get_blog_ingestion_client()
            logger.info("Refreshing all blogs")
            results = []
            for blog_source in settings.blog_sources:
                try:
                    result = await blog_ingestion_client.ingest_blog(
                        blog_name=blog_source["name"],
                        feed_url=blog_source["url"],
                        max_posts=50
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error refreshing blog {blog_source['name']}: {e}")
                    results.append({
                        "status": "error",
                        "blog_name": blog_source["name"],
                        "posts_ingested": 0,
                        "chunks_created": 0,
                        "errors": 1,
                        "message": str(e)
                    })
            
            return {
                "status": "complete",
                "blogs_refreshed": len(results),
                "results": results
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing blog: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Blog refresh failed: {str(e)}"
        )


@router.get(
    "/blogs/sources",
    response_model=BlogSourcesResponse,
    tags=["Blog Management"],
    summary="List Blog Sources",
    description="Get list of configured blog sources and their ingestion statistics"
)
async def list_blog_sources():
    """
    List all configured blog sources with statistics
    """
    try:
        from src.config import settings
        from src.knowledge.vector_store import vector_store
        
        sources = []
        for blog_source in settings.blog_sources:
            # Get stats for this blog
            stats = await vector_store.get_blog_stats(blog_name=blog_source["name"])
            
            sources.append(BlogSource(
                name=blog_source["name"],
                url=blog_source["url"],
                total_posts=stats.get("blog_vectors", 0),
                last_updated=None  # Could be enhanced to track last update time
            ))
        
        return BlogSourcesResponse(sources=sources)
        
    except Exception as e:
        logger.error(f"Error listing blog sources: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list blog sources: {str(e)}"
        )
