"""
API routes for Marketing Cortex
"""
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
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
    BlogSource,
    EntitySearchResponse,
    EntityResponse,
    EntityContextResponse,
    EntityExtractionRequest,
    EntityExtractionResponse
)
from src.knowledge.graph_schema import graph_schema
from src.core.memory import memory_manager
from src.core.cache import cache_manager
from src.integrations.tavily_client import tavily_client
from src.agents.marketing_strategy_advisor import marketing_strategy_advisor
from src.config import settings
from datetime import datetime
import logging
import uuid
import json

logger = logging.getLogger(__name__)

router = APIRouter()


# Health check endpoint
@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health & Status"],
    summary="Health Check",
    description="Check the health status of the API and all services"
)
async def health_check():
    """
    Health check endpoint that verifies all services are operational
    """
    services = {}
    
    # Check Neo4j
    try:
        await graph_schema.initialize_schema()
        services["neo4j"] = "healthy"
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        services["neo4j"] = f"unhealthy: {str(e)}"
    
    # Check Redis
    try:
        await cache_manager.ping()
        services["redis"] = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        services["redis"] = f"unhealthy: {str(e)}"
    
    # Check Zep (memory)
    try:
        # Simple check - try to get a test session
        await memory_manager.get_memory("health-check")
        services["zep"] = "healthy"
    except Exception as e:
        logger.error(f"Zep health check failed: {e}")
        services["zep"] = f"unhealthy: {str(e)}"
    
    return HealthResponse(
        status="healthy" if all("healthy" in v for v in services.values()) else "degraded",
        timestamp=datetime.utcnow(),
        services=services
    )


# Agent endpoints
@router.post(
    "/run-agent",
    response_model=AgentResponse,
    tags=["Agent Operations"],
    summary="Run Agent (Non-Streaming)",
    description="Execute the Marketing Strategy Advisor agent and return complete response"
)
async def run_agent(request: AgentRequest):
    """
    Run the agent with a query and return the complete response
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        response_text = await marketing_strategy_advisor.get_response(
            query=request.query,
            session_id=session_id,
            metadata=request.metadata
        )
        
        return AgentResponse(
            response=response_text,
            agent_used="marketing_strategy_advisor",
            session_id=session_id,
            metadata=request.metadata
        )
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}"
        )


@router.post(
    "/agent/stream",
    tags=["Agent Operations"],
    summary="Stream Agent Response (SSE)",
    description="Stream agent responses using Server-Sent Events (SSE). Returns real-time updates including tool calls, query refinements, and token-by-token response streaming.",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream with agent response events",
            "content": {"text/event-stream": {}}
        },
        404: {"description": "Endpoint not found"},
        500: {"description": "Internal server error"}
    }
)
async def stream_agent(request: AgentRequest):
    """
    Stream agent response using Server-Sent Events (SSE)
    
    Event types:
    - start: Stream started
    - token: Text chunk
    - tool_call_start: Tool execution started
    - tool_call_result: Tool execution completed
    - query_refinement: Query was refined
    - synthesis_start: Synthesis started
    - done: Stream completed
    - error: Error occurred
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    async def generate_stream():
        try:
            chunk_count = 0
            full_response = ""
            
            async for event in marketing_strategy_advisor.stream_response(
                query=request.query,
                session_id=session_id,
                metadata=request.metadata
            ):
                event_type = event.get("type")
                event_content = event.get("content")
                
                if event_type == "token":
                    chunk_count += 1
                    full_response += event_content
                
                # Send event (tool calls, refinements, tokens, etc.)
                yield f"data: {json.dumps(event)}\n\n"
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'chunks': chunk_count})}\n\n"
            
        except Exception as e:
            logger.error(f"Error in agent stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': f'An error occurred: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# Campaign management endpoints
@router.post(
    "/campaigns",
    tags=["Campaign Management"],
    summary="Create Campaign",
    description="Create a new marketing campaign in the knowledge graph"
)
async def create_campaign(campaign: CampaignCreate):
    """
    Create a new campaign
    """
    try:
        result = await graph_schema.create_campaign(
            campaign_id=campaign.campaign_id,
            name=campaign.name,
            objective=campaign.objective,
            budget=campaign.budget,
            start_date=campaign.start_date,
            metadata=campaign.metadata
        )
        return result
    except Exception as e:
        logger.error(f"Error creating campaign: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Campaign creation failed: {str(e)}"
        )


@router.get(
    "/campaigns/{campaign_id}",
    tags=["Campaign Management"],
    summary="Get Campaign",
    description="Get campaign details with full hierarchy (adsets, creatives, performance)"
)
async def get_campaign(campaign_id: str):
    """
    Get campaign with full hierarchy
    """
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
        logger.error(f"Error getting campaign: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get campaign: {str(e)}"
        )


# AdSet endpoints
@router.post(
    "/adsets",
    tags=["AdSet Management"],
    summary="Create AdSet",
    description="Create a new adset linked to a campaign"
)
async def create_adset(adset: AdSetCreate):
    """
    Create a new adset
    """
    try:
        result = await graph_schema.create_adset(
            adset_id=adset.adset_id,
            campaign_id=adset.campaign_id,
            name=adset.name,
            targeting=adset.targeting,
            budget=adset.budget,
            metadata=adset.metadata
        )
        return result
    except Exception as e:
        logger.error(f"Error creating adset: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Adset creation failed: {str(e)}"
        )


# Creative endpoints
@router.post(
    "/creatives",
    tags=["Creative Management"],
    summary="Create Creative",
    description="Create a new creative linked to an adset"
)
async def create_creative(creative: CreativeCreate):
    """
    Create a new creative
    """
    try:
        result = await graph_schema.create_creative(
            creative_id=creative.creative_id,
            adset_id=creative.adset_id,
            name=creative.name,
            copy=creative.ad_copy,
            image_url=creative.image_url,
            metadata=creative.metadata
        )
        return result
    except Exception as e:
        logger.error(f"Error creating creative: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Creative creation failed: {str(e)}"
        )


# Performance endpoints
@router.post(
    "/performance",
    tags=["Performance Tracking"],
    summary="Add Performance Data",
    description="Add performance metrics for a creative"
)
async def add_performance(performance: PerformanceCreate):
    """
    Add performance data
    """
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
        return result
    except Exception as e:
        logger.error(f"Error adding performance: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performance creation failed: {str(e)}"
        )


@router.get(
    "/high-performers",
    tags=["Performance Tracking"],
    summary="Query High Performers",
    description="Get high-performing creatives based on ROAS threshold"
)
async def get_high_performers(
    min_roas: float = Query(2.0, description="Minimum ROAS threshold"),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=100)
):
    """
    Get high-performing creatives
    """
    try:
        results = await graph_schema.query_high_performers(
            min_roas=min_roas,
            limit=limit
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"Error querying high performers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query high performers: {str(e)}"
        )


# Tavily search endpoints
@router.get(
    "/tavily/quota",
    tags=["Tavily Search & Rate Limiting"],
    summary="Get Tavily Quota Status",
    description="Check current Tavily API quota usage and remaining requests"
)
async def get_tavily_quota():
    """
    Get Tavily quota status
    """
    try:
        quota_info = await tavily_client.get_quota_status()
        return quota_info
    except Exception as e:
        logger.error(f"Error getting Tavily quota: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quota status: {str(e)}"
        )


@router.post(
    "/tavily/search",
    tags=["Tavily Search & Rate Limiting"],
    summary="Tavily Web Search",
    description="Search using Tavily API with rate limiting and caching. Supports different search types (general, news, competitor, research) with different cache TTLs."
)
async def tavily_search(
    query: str = Query(..., description="Search query"),
    search_type: str = Query("general", description="Type of search: general, news, competitor, research"),
    max_results: int = Query(5, description="Maximum number of results", ge=1, le=10)
):
    """
    Search using Tavily API
    """
    try:
        result = await tavily_client.search_with_fallback(
            query=query,
            search_type=search_type,
            max_results=max_results
        )
        return result
    except Exception as e:
        logger.error(f"Error searching with Tavily: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tavily search failed: {str(e)}"
        )


@router.delete(
    "/tavily/cache",
    tags=["Tavily Search & Rate Limiting"],
    summary="Clear Tavily Cache",
    description="Clear cached Tavily search results. Optionally filter by query pattern."
)
async def clear_tavily_cache(
    pattern: Optional[str] = Query(None, description="Optional pattern to match cache keys")
):
    """
    Clear Tavily cache
    """
    try:
        cleared = await tavily_client.clear_cache(pattern=pattern)
        return {"cleared": cleared, "message": f"Cleared {cleared} cache entries"}
    except Exception as e:
        logger.error(f"Error clearing Tavily cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )


# Queue management endpoints
@router.get(
    "/queue/status",
    tags=["Queue Management"],
    summary="Get Queue Status",
    description="Get status of all request queues including active tasks and statistics"
)
async def get_queue_status():
    """
    Get queue status information
    """
    try:
        # Return configuration info for parallel processing
        return {
            "max_concurrent_posts": settings.max_concurrent_posts,
            "entity_extraction_concurrent": 3,  # From EntityExtractor semaphore
            "message": "Queue system is active. Blog ingestion uses parallel processing with concurrency limits."
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {str(e)}"
        )


# Groq token usage endpoints
@router.get(
    "/groq/token-usage",
    tags=["Groq Rate Limiting"],
    summary="Get Groq Token Usage",
    description="Check current Groq API token usage and rate limit status for entity extraction"
)
async def get_groq_token_usage():
    """
    Get Groq token usage status
    """
    try:
        from src.knowledge.entity_extractor import EntityExtractor
        
        extractor = EntityExtractor()
        is_within_limit, tokens_used = await extractor._check_token_usage()
        
        # Get rate limit status
        rate_limit_status = cache_manager.get(extractor._get_rate_limit_key())
        
        return {
            "tokens_used": tokens_used,
            "daily_limit": extractor.daily_token_limit,
            "tokens_remaining": max(0, extractor.daily_token_limit - tokens_used),
            "usage_percentage": round((tokens_used / extractor.daily_token_limit) * 100, 2) if extractor.daily_token_limit > 0 else 0,
            "is_within_limit": is_within_limit,
            "rate_limit_status": rate_limit_status,
            "model": settings.groq_model
        }
    except Exception as e:
        logger.error(f"Error getting Groq token usage: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get token usage: {str(e)}"
        )


# Blog ingestion endpoints
def get_blog_ingestion_client():
    """Lazy import to avoid errors if dependencies not installed"""
    try:
        from src.integrations.blog_ingestion import BlogIngestionClient
        return BlogIngestionClient()
    except ImportError as e:
        logger.warning(f"Blog ingestion dependencies not available: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Blog ingestion service is not available. Please install required dependencies: feedparser, readability-lxml, beautifulsoup4, lxml"
        )


@router.post(
    "/blogs/ingest/stream",
    tags=["Blog Management"],
    summary="Ingest Blog Content (SSE Stream)",
    description="Stream blog ingestion progress via Server-Sent Events with real-time updates",
    response_class=StreamingResponse
)
async def ingest_blog_stream(request: BlogIngestRequest):
    """
    SSE endpoint for streaming blog ingestion progress.
    
    Streams events with 'type' (start, progress, complete, error) and 'content' (JSON string).
    Progress events include stage, message, progress percentage, current post, total posts, etc.
    """
    import asyncio

    async def generate_stream():
        try:
            blog_ingestion_client = get_blog_ingestion_client()
            logger.info(f"Streaming blog ingestion: {request.blog_name} from {request.blog_url}")
            
            yield f"data: {json.dumps({'type': 'start', 'message': f'Starting ingestion of {request.blog_name}...'})}\n\n"
            
            progress_queue = asyncio.Queue()
            
            async def progress_callback_internal(progress_data: Dict[str, Any]):
                await progress_queue.put(progress_data)
            
            async def run_ingestion():
                try:
                    result = await blog_ingestion_client.ingest_blog(
                        blog_name=request.blog_name,
                        feed_url=request.blog_url,
                        max_posts=request.max_posts,
                        progress_callback=progress_callback_internal
                    )
                    await progress_queue.put({"type": "done", "result": result})
                except Exception as e:
                    await progress_queue.put({"type": "error", "error": str(e)})
            
            ingestion_task = asyncio.create_task(run_ingestion())
            
            while True:
                try:
                    progress_data = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    
                    if progress_data.get("type") == "done":
                        final_result = progress_data.get("result")
                        yield f"data: {json.dumps({'type': 'complete', 'result': final_result})}\n\n"
                        break
                    elif progress_data.get("type") == "error":
                        yield f"data: {json.dumps({'type': 'error', 'error': progress_data.get('error')})}\n\n"
                        break
                    else:
                        event = {
                            "type": "progress",
                            **progress_data
                        }
                        yield f"data: {json.dumps(event)}\n\n"
                        
                except asyncio.TimeoutError:
                    if ingestion_task.done():
                        break
                    continue
            
            await ingestion_task
            
        except Exception as e:
            logger.error(f"Error in blog ingestion stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post(
    "/blogs/refresh",
    tags=["Blog Management"],
    summary="Refresh Blog Content",
    description="Refresh blog content from RSS feeds. Optionally refresh a specific blog or all blogs."
)
async def refresh_blogs(request: BlogRefreshRequest):
    """
    Refresh blog content
    """
    try:
        blog_ingestion_client = get_blog_ingestion_client()
        
        if request.blog_name:
            # Refresh specific blog
            blog_source = next(
                (bs for bs in settings.blog_sources if bs["name"] == request.blog_name),
                None
            )
            if not blog_source:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Blog '{request.blog_name}' not found in sources"
                )
            
            result = await blog_ingestion_client.ingest_blog(
                blog_name=blog_source["name"],
                feed_url=blog_source["url"],
                max_posts=50
            )
            return result
        else:
            # Refresh all blogs
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
                    logger.error(f"Error refreshing {blog_source['name']}: {e}")
                    results.append({
                        "status": "error",
                        "blog_name": blog_source["name"],
                        "error": str(e)
                    })
            
            return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing blogs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Blog refresh failed: {str(e)}"
        )


@router.get(
    "/blogs/sources",
    response_model=BlogSourcesResponse,
    tags=["Blog Management"],
    summary="List Blog Sources",
    description="Get list of all configured blog sources with ingestion statistics"
)
async def list_blog_sources():
    """
    List all blog sources with statistics
    """
    try:
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


# Knowledge Graph endpoints
@router.get(
    "/graph/entities",
    response_model=EntitySearchResponse,
    tags=["Knowledge Graph"],
    summary="Search Marketing Entities",
    description="Search for marketing entities in the knowledge graph by name or type"
)
async def search_entities(
    query: str = Query(..., description="Search query for entities"),
    entity_types: Optional[str] = Query(None, description="Comma-separated entity types to filter"),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=50)
):
    """
    Search for marketing entities in the knowledge graph
    """
    try:
        from src.knowledge.graph_schema import graph_schema
        
        entity_types_list = None
        if entity_types:
            entity_types_list = [t.strip() for t in entity_types.split(",")]
        
        entities = await graph_schema.find_entities_by_query(
            query_text=query,
            entity_types=entity_types_list,
            limit=limit
        )
        
        return EntitySearchResponse(
            entities=[
                EntityResponse(
                    id=e.get("id", ""),
                    name=e.get("name", ""),
                    entity_type=e.get("entity_type", ""),
                    confidence=e.get("confidence", 1.0),
                    metadata=e.get("metadata")
                )
                for e in entities
            ]
        )
    except Exception as e:
        logger.error(f"Error searching entities: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Entity search failed: {str(e)}"
        )


@router.get(
    "/graph/entity/{entity_id}",
    response_model=EntityContextResponse,
    tags=["Knowledge Graph"],
    summary="Get Entity Context",
    description="Get comprehensive context for an entity including related entities and blog posts"
)
async def get_entity_context(
    entity_id: str,
    include_blog_posts: bool = Query(True, description="Include linked blog posts"),
    max_related: int = Query(5, description="Maximum related entities", ge=1, le=20),
    max_blog_posts: int = Query(10, description="Maximum blog posts", ge=1, le=50)
):
    """
    Get comprehensive context for an entity
    """
    try:
        from src.knowledge.graph_schema import graph_schema
        
        context = await graph_schema.get_entity_context(
            entity_id=entity_id,
            include_blog_posts=include_blog_posts,
            max_related=max_related,
            max_blog_posts=max_blog_posts
        )
        
        entity_data = context.get("entity")
        entity_response = None
        if entity_data:
            entity_response = EntityResponse(
                id=entity_data.get("id", ""),
                name=entity_data.get("name", ""),
                entity_type=entity_data.get("entity_type", ""),
                confidence=entity_data.get("confidence", 1.0),
                metadata=entity_data.get("metadata")
            )
        
        return EntityContextResponse(
            entity=entity_response,
            related_entities=context.get("related_entities", []),
            blog_posts=context.get("blog_posts", [])
        )
    except Exception as e:
        logger.error(f"Error getting entity context: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get entity context: {str(e)}"
        )


@router.get(
    "/graph/relationships",
    tags=["Knowledge Graph"],
    summary="Get Entity Relationships",
    description="Get relationships for a specific entity"
)
async def get_entity_relationships(
    entity_id: str = Query(..., description="Entity ID"),
    relationship_types: Optional[str] = Query(None, description="Comma-separated relationship types to filter"),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=50)
):
    """
    Get relationships for an entity
    """
    try:
        from src.knowledge.graph_schema import graph_schema
        
        # Get entity context which includes relationships
        context = await graph_schema.get_entity_context(
            entity_id=entity_id,
            include_blog_posts=False,
            max_related=limit,
            max_blog_posts=0
        )
        
        relationships = context.get("related_entities", [])
        
        # Filter by relationship types if provided
        if relationship_types:
            rel_types = [t.strip() for t in relationship_types.split(",")]
            relationships = [
                rel for rel in relationships
                if rel.get("relationship_type") in rel_types
            ]
        
        return {
            "entity_id": entity_id,
            "relationships": relationships[:limit]
        }
    except Exception as e:
        logger.error(f"Error getting relationships: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get relationships: {str(e)}"
        )


@router.post(
    "/graph/extract",
    response_model=EntityExtractionResponse,
    tags=["Knowledge Graph"],
    summary="Extract Entities from Content",
    description="Manually trigger entity extraction from provided content"
)
async def extract_entities(request: EntityExtractionRequest):
    """
    Extract entities and relationships from content
    """
    try:
        from src.knowledge.entity_extractor import EntityExtractor
        
        extractor = EntityExtractor()
        result = await extractor.extract_entities(
            content=request.content,
            url=request.url
        )
        
        return EntityExtractionResponse(
            entities=[
                {
                    "name": e.name,
                    "type": e.type,
                    "confidence": e.confidence
                }
                for e in result.entities
            ],
            relationships=[
                {
                    "source": r.source,
                    "target": r.target,
                    "type": r.type,
                    "confidence": r.confidence
                }
                for r in result.relationships
            ]
        )
    except Exception as e:
        logger.error(f"Error extracting entities: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Entity extraction failed: {str(e)}"
        )
