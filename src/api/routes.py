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
    BlogIngestRequest,
    BlogIngestResponse,
    BlogRefreshRequest,
    BlogSourcesResponse,
    BlogSource,
    EntitySearchResponse,
    EntityResponse,
    EntityContextResponse,
    EntityExtractionRequest,
    EntityExtractionResponse,
    ErrorResponse
)
from src.knowledge.graph_schema import graph_schema
from src.core.memory import memory_manager
from src.core.cache import cache_manager
from src.integrations.tavily_client import tavily_client
from src.agents.marketing_strategy_advisor import marketing_strategy_advisor
from src.config import settings
from src.observability import (
    get_structured_logger,
    set_request_id,
    get_request_id,
    get_alert_manager,
    get_langsmith_client,
)
from src.observability.circuit_breaker import get_circuit_breaker
from src.observability.circuit_breaker import CircuitBreakerOpenError
from datetime import datetime
import logging
import uuid
import json
import httpx

logger = get_structured_logger(__name__)
alert_manager = get_alert_manager()


def create_error_response(
    error_code: str,
    error_message: str,
    error_type: str = "server_error",
    details: Optional[Dict[str, Any]] = None,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
) -> HTTPException:
    """
    Create a structured error response
    
    Args:
        error_code: Error code for programmatic handling
        error_message: Human-readable error message
        error_type: Error type (validation, server, client, etc.)
        details: Additional error details
        status_code: HTTP status code
        
    Returns:
        HTTPException with structured error response
    """
    from datetime import datetime
    
    # Ensure details is a dict and convert datetime to string
    if details is None:
        details = {}
    else:
        details = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in details.items()}
    error_response = ErrorResponse(
        error_code=error_code,
        error_message=error_message,
        error_type=error_type,
        details=details or {},
        request_id=get_request_id()
    )
    return HTTPException(
        status_code=status_code,
        detail=error_response.model_dump(mode='json')  # Use mode='json' to serialize datetime
    )

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
    Includes circuit breaker status, observability platform status, and performance metrics
    """
    services = {}
    
    # Check Neo4j (simple connection test, not full schema init)
    try:
        async with graph_schema.driver.session(database=settings.neo4j_database) as session:
            result = await session.run("RETURN 1 as test")
            await result.consume()  # Consume result to complete query
        services["neo4j"] = "healthy"
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        services["neo4j"] = f"unhealthy: {str(e)}"
    
    # Check Redis
    try:
        is_healthy = await cache_manager.ping()
        services["redis"] = "healthy" if is_healthy else "unhealthy: connection failed"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        services["redis"] = f"unhealthy: {str(e)}"
    
    # Check Zep (memory) - async version
    try:
        # Simple check - try to get a test session (async)
        test_memory = await memory_manager.get_memory_async("health-check")
        services["zep"] = "healthy"
    except Exception as e:
        logger.error(f"Zep health check failed: {e}")
        services["zep"] = f"unhealthy: {str(e)}"
    
    # Get circuit breaker status
    circuit_breakers = {}
    for cb_name in ["tavily", "pinecone", "zep"]:
        try:
            cb = get_circuit_breaker(cb_name)
            circuit_breakers[cb_name] = cb.get_status()
        except Exception as e:
            circuit_breakers[cb_name] = {"error": str(e)}
    
    # Get observability platform status
    observability = {}
    try:
        langsmith_client = get_langsmith_client()
        observability["langsmith"] = "connected" if langsmith_client else "not_configured"
    except Exception as e:
        observability["langsmith"] = f"error: {str(e)}"
    
    # Get performance metrics (simplified - in production, this would query metrics store)
    performance = {
        "p50_latency": 0.0,  # Placeholder - would be calculated from recent requests
        "p95_latency": 0.0,
        "p99_latency": 0.0
    }
    
    return HealthResponse(
        status="healthy" if all("healthy" in v for v in services.values()) else "degraded",
        timestamp=datetime.utcnow(),
        services=services,
        circuit_breakers=circuit_breakers,
        observability=observability,
        performance=performance
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
    request_id = set_request_id()
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        logger.log_with_context(
            logging.INFO,
            "Running agent (non-streaming)",
            query=request.query[:200],
            session_id=session_id,
            metadata={"request_id": request_id}
        )
        
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
    except CircuitBreakerOpenError as e:
        alert_manager.record_error("agent_circuit_breaker", "api", {"session_id": session_id})
        logger.log_with_context(
            logging.ERROR,
            f"Circuit breaker open: {e}",
            query=request.query[:200],
            session_id=session_id
        )
        raise create_error_response(
            error_code="CIRCUIT_BREAKER_OPEN",
            error_message="Service temporarily unavailable. Please try again later.",
            error_type="service_unavailable",
            details={"service": "agent", "session_id": session_id},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        alert_manager.record_error("agent_execution_error", "api", {"error": str(e), "session_id": session_id})
        logger.log_with_context(
            logging.ERROR,
            f"Error running agent: {e}",
            query=request.query[:200],
            session_id=session_id,
            metadata={"error": str(e)}
        )
        raise create_error_response(
            error_code="AGENT_EXECUTION_FAILED",
            error_message=f"Agent execution failed: {str(e)}",
            error_type="server_error",
            details={"session_id": session_id},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
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
    "/groq/rate-limiter-status",
    tags=["Groq Rate Limiting"],
    summary="Get Rate Limiter Status",
    description="Check current client-side rate limiter status (requests per minute)"
)
async def get_rate_limiter_status():
    """
    Get client-side rate limiter status
    
    Returns:
        Rate limiter statistics including current usage and available slots
    """
    try:
        from src.core.rate_limiter import get_groq_rate_limiter
        
        rate_limiter = get_groq_rate_limiter()
        stats = rate_limiter.get_stats()
        
        return {
            "status": "active",
            "rate_limiter": stats,
            "message": f"Client-side rate limiter: {stats['requests_in_window']}/{stats['max_requests']} requests in current window"
        }
    except Exception as e:
        logger.error(f"Error getting rate limiter status: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


@router.get(
    "/groq/token-usage",
    tags=["Groq Rate Limiting"],
    summary="Get Groq Rate Limiter Status",
    description="Check current Groq API rate limiter status (RPM limit only, no daily token limit)"
)
async def get_groq_token_usage():
    """
    Get Groq rate limiter status (RPM limit only)
    Daily token limit has been removed - only RPM limit is enforced
    """
    try:
        from src.core.rate_limiter import get_groq_rate_limiter
        from src.knowledge.entity_extractor import EntityExtractor
        
        rate_limiter = get_groq_rate_limiter()
        extractor = EntityExtractor()
        
        # Get rate limiter stats
        limiter_stats = rate_limiter.get_stats()
        
        # Get rate limit status (for RPM limits)
        rate_limit_status = cache_manager.get(extractor._get_rate_limit_key())
        
        return {
            "rate_limiter": limiter_stats,
            "rate_limit_status": rate_limit_status,
            "rpm_limit": limiter_stats.get("max_requests", 5000),
            "current_usage": limiter_stats.get("requests_in_window", 0),
            "available_slots": limiter_stats.get("available_slots", 0),
            "model": settings.groq_model,
            "note": "Daily token limit removed - only RPM limit (6000) is enforced"
        }
        
    except Exception as e:
        logger.error(f"Error getting Groq rate limiter status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get rate limiter status: {str(e)}"
        )


@router.post(
    "/groq/reset-token-usage",
    tags=["Groq Rate Limiting"],
    summary="Reset Token Usage (Deprecated)",
    description="This endpoint is deprecated. Daily token limit has been removed. Only RPM limit is enforced."
)
async def reset_token_usage():
    """
    Deprecated endpoint - daily token limit has been removed
    Only RPM limit (6000) is now enforced
    """
    return {
        "status": "deprecated",
        "message": "Daily token limit has been removed. Only RPM limit (6000) is enforced.",
        "note": "This endpoint is kept for backward compatibility but does nothing."
    }


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
                    # Check if result indicates an error
                    if result.get("status") == "error":
                        error_message = result.get("message", "Unknown error during ingestion")
                        error_details = {
                            "error": error_message,
                            "error_type": "ingestion_error",
                            "blog_name": request.blog_name,
                            "details": result
                        }
                        await progress_queue.put({"type": "error", **error_details})
                    else:
                        await progress_queue.put({"type": "done", "result": result})
                except httpx.HTTPStatusError as e:
                    error_message = f"HTTP error {e.response.status_code}: {e.response.text[:200]}"
                    if e.response.status_code == 404:
                        error_message = f"RSS feed not found. Please check the URL: {request.blog_url}"
                    elif e.response.status_code == 403:
                        error_message = f"Access forbidden. The RSS feed may require authentication or be blocked."
                    error_details = {
                        "error": error_message,
                        "error_type": "http_error",
                        "status_code": e.response.status_code,
                        "blog_name": request.blog_name,
                        "feed_url": request.blog_url
                    }
                    await progress_queue.put({"type": "error", **error_details})
                except httpx.TimeoutException as e:
                    error_details = {
                        "error": f"Request timeout. The RSS feed took too long to respond. Please check the URL: {request.blog_url}",
                        "error_type": "timeout_error",
                        "blog_name": request.blog_name,
                        "feed_url": request.blog_url
                    }
                    await progress_queue.put({"type": "error", **error_details})
                except httpx.RequestError as e:
                    error_details = {
                        "error": f"Network error: {str(e)}. Please check your internet connection and the RSS feed URL.",
                        "error_type": "network_error",
                        "blog_name": request.blog_name,
                        "feed_url": request.blog_url
                    }
                    await progress_queue.put({"type": "error", **error_details})
                except ValueError as e:
                    error_details = {
                        "error": f"Invalid RSS feed format: {str(e)}. The URL may not be a valid RSS feed.",
                        "error_type": "validation_error",
                        "blog_name": request.blog_name,
                        "feed_url": request.blog_url
                    }
                    await progress_queue.put({"type": "error", **error_details})
                except Exception as e:
                    error_details = {
                        "error": f"Unexpected error: {str(e)}",
                        "error_type": "unknown_error",
                        "blog_name": request.blog_name,
                        "feed_url": request.blog_url
                    }
                    logger.error(f"Error in blog ingestion: {e}", exc_info=True)
                    await progress_queue.put({"type": "error", **error_details})
            
            ingestion_task = asyncio.create_task(run_ingestion())
            
            while True:
                try:
                    progress_data = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    
                    if progress_data.get("type") == "done":
                        final_result = progress_data.get("result")
                        yield f"data: {json.dumps({'type': 'complete', 'result': final_result})}\n\n"
                        break
                    elif progress_data.get("type") == "error":
                        yield f"data: {json.dumps({'type': 'error', **progress_data})}\n\n"
                        break
                    elif progress_data.get("error"):
                        # Error flag in progress data (from progress callback)
                        yield f"data: {json.dumps({
                            'type': 'error',
                            'error': progress_data.get('message', 'Unknown error'),
                            'error_type': 'ingestion_error',
                            'stage': progress_data.get('stage', 'unknown'),
                            'blog_name': request.blog_name,
                            'feed_url': request.blog_url
                        })}\n\n"
                        break
                    else:
                        event = {
                            "type": "progress",
                            **progress_data
                        }
                        yield f"data: {json.dumps(event)}\n\n"
                        
                except asyncio.TimeoutError:
                    if ingestion_task.done():
                        # Check if task completed with error
                        try:
                            await ingestion_task
                        except Exception as e:
                            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'error_type': 'task_error'})}\n\n"
                        break
                    continue
            
            # Wait for task to complete
            if not ingestion_task.done():
                try:
                    await asyncio.wait_for(ingestion_task, timeout=0.5)
                except asyncio.TimeoutError:
                    pass
            
        except Exception as e:
            logger.error(f"Error in blog ingestion stream: {e}", exc_info=True)
            error_details = {
                "error": f"Stream error: {str(e)}",
                "error_type": "stream_error",
                "blog_name": request.blog_name if hasattr(request, 'blog_name') else "unknown"
            }
            yield f"data: {json.dumps({'type': 'error', **error_details})}\n\n"
    
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


@router.get(
    "/blogs/check-duplicate",
    tags=["Blog Management"],
    summary="Check if Blog Already Exists",
    description="Check if a blog has content in Pinecone. Blogs in configured sources will still be ingested."
)
async def check_blog_duplicate(
    blog_name: str = Query(..., description="Name of the blog"),
    blog_url: str = Query(..., description="RSS feed URL")
):
    """
    Check if blog already has content in Pinecone
    Only skips if content exists in Pinecone, not if it's just in configured sources
    """
    try:
        from src.knowledge.vector_store import vector_store
        
        # Normalize URLs for comparison
        normalized_url = blog_url.rstrip('/')
        
        # Check if blog exists in configured sources (informational only)
        exists_in_sources = False
        for blog_source in settings.blog_sources:
            normalized_source_url = blog_source["url"].rstrip('/')
            if (normalized_source_url == normalized_url or 
                blog_source["name"].lower() == blog_name.lower()):
                exists_in_sources = True
                break
        
        # Check if blog has content in Pinecone (this is what matters for skipping)
        stats = await vector_store.get_blog_stats(blog_name=blog_name)
        has_content = stats.get("blog_vectors", 0) > 0
        
        return {
            "exists": has_content,  # Only skip if content exists in Pinecone
            "exists_in_sources": exists_in_sources,
            "has_content_in_pinecone": has_content,
            "message": (
                "Blog content already exists in Pinecone" if has_content
                else "Blog exists in configured sources but will be ingested" if exists_in_sources
                else "Blog does not exist"
            )
        }
        
    except Exception as e:
        logger.error(f"Error checking blog duplicate: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check blog duplicate: {str(e)}"
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
