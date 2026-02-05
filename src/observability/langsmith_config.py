"""
LangSmith integration for observability and tracing
Provides automatic tracing of LLM calls, tool invocations, and agent workflows
"""
import os
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
import inspect
from langsmith import Client
from langchain_core.tracers import LangChainTracer
from langchain_core.callbacks import CallbackManager
from src.config import settings

logger = logging.getLogger(__name__)

# Global LangSmith client and tracer instances
_langsmith_client: Optional[Client] = None
_langsmith_tracer: Optional[LangChainTracer] = None


def get_langsmith_client() -> Optional[Client]:
    """
    Get or create LangSmith client
    
    Returns:
        LangSmith Client instance or None if not configured
    """
    global _langsmith_client
    
    if not settings.enable_langsmith:
        return None
    
    if _langsmith_client is None:
        try:
            api_key = settings.langchain_api_key
            if not api_key or api_key == "your_langsmith_api_key_here":
                logger.warning("LangSmith API key not configured, skipping LangSmith initialization")
                return None
            
            _langsmith_client = Client(
                api_key=api_key,
                api_url=settings.langchain_endpoint
            )
            
            # Set environment variables for LangChain integration
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = api_key
            os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
            os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
            
            logger.info(f"LangSmith client initialized for project: {settings.langchain_project}")
        except Exception as e:
            logger.error(f"Failed to initialize LangSmith client: {e}", exc_info=True)
            return None
    
    return _langsmith_client


def get_langsmith_tracer() -> Optional[LangChainTracer]:
    """
    Get or create LangSmith tracer for LangChain callbacks
    
    Returns:
        LangChainTracer instance or None if not configured
    """
    global _langsmith_tracer
    
    if not settings.enable_langsmith:
        return None
    
    if _langsmith_tracer is None:
        client = get_langsmith_client()
        if client:
            _langsmith_tracer = LangChainTracer(project_name=settings.langchain_project)
            logger.info("LangSmith tracer initialized")
    
    return _langsmith_tracer


def trace_agent_execution(func: Callable) -> Callable:
    """
    Decorator to trace agent execution with LangSmith
    
    Usage:
        @trace_agent_execution
        async def stream_response(self, query: str, session_id: str):
            ...
    
    Args:
        func: Function to trace
        
    Returns:
        Wrapped function with tracing
    """
    # Check if function is an async generator
    is_async_gen = inspect.isasyncgenfunction(func)
    
    if is_async_gen:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not settings.enable_langsmith:
                async for item in func(*args, **kwargs):
                    yield item
                return
            
            tracer = get_langsmith_tracer()
            if not tracer:
                async for item in func(*args, **kwargs):
                    yield item
                return
            
            # Extract query and session_id for trace metadata
            query = kwargs.get("query", args[1] if len(args) > 1 else "unknown")
            session_id = kwargs.get("session_id", args[2] if len(args) > 2 else "unknown")
            
            try:
                # Create callback manager with LangSmith tracer
                callback_manager = CallbackManager([tracer])
                
                # Add callbacks to kwargs if function accepts it
                if "callbacks" in kwargs:
                    kwargs["callbacks"] = callback_manager
                elif hasattr(args[0], "callbacks"):
                    # For agent methods, set callbacks on the agent instance
                    pass
                
                logger.debug(f"[LangSmith] Tracing agent execution - Query: {query[:50]}..., Session: {session_id}")
                
                # For async generators, yield from the generator
                async for item in func(*args, **kwargs):
                    yield item
                
            except Exception as e:
                logger.error(f"[LangSmith] Error during agent execution trace: {e}", exc_info=True)
                # Still execute function even if tracing fails
                async for item in func(*args, **kwargs):
                    yield item
    else:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not settings.enable_langsmith:
                return await func(*args, **kwargs)
            
            tracer = get_langsmith_tracer()
            if not tracer:
                return await func(*args, **kwargs)
            
            # Extract query and session_id for trace metadata
            query = kwargs.get("query", args[1] if len(args) > 1 else "unknown")
            session_id = kwargs.get("session_id", args[2] if len(args) > 2 else "unknown")
            
            try:
                # Create callback manager with LangSmith tracer
                callback_manager = CallbackManager([tracer])
                
                # Add callbacks to kwargs if function accepts it
                if "callbacks" in kwargs:
                    kwargs["callbacks"] = callback_manager
                elif hasattr(args[0], "callbacks"):
                    # For agent methods, set callbacks on the agent instance
                    pass
                
                logger.debug(f"[LangSmith] Tracing agent execution - Query: {query[:50]}..., Session: {session_id}")
                
                # For regular async functions, await and return
                result = await func(*args, **kwargs)
                logger.debug(f"[LangSmith] Agent execution completed - Session: {session_id}")
                return result
                
            except Exception as e:
                logger.error(f"[LangSmith] Error during agent execution trace: {e}", exc_info=True)
                # Still execute function even if tracing fails
                return await func(*args, **kwargs)
    
    return wrapper


def log_tool_call(tool_name: str, query: str, result: Any, duration: float, session_id: str):
    """
    Log tool call to LangSmith
    
    Args:
        tool_name: Name of the tool
        query: Query that triggered the tool
        result: Tool result
        duration: Execution duration in seconds
        session_id: Session identifier
    """
    try:
        client = get_langsmith_client()
        if not client:
            return
        
        # Log tool call metadata
        logger.debug(
            f"[LangSmith] Tool call: {tool_name} - Duration: {duration:.2f}s - Session: {session_id}"
        )
    except Exception as e:
        logger.error(f"Error logging tool call to LangSmith: {e}")
