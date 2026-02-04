"""
LangSmith integration for observability and tracing
Primary observability platform for agent execution tracking
"""
import os
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
from langsmith import Client
from langchain_core.tracers import LangChainTracer
from langchain_core.callbacks import CallbackManager
from src.config import settings

logger = logging.getLogger(__name__)

# Global LangSmith client instance
_langsmith_client: Optional[Client] = None
_langsmith_tracer: Optional[LangChainTracer] = None


def get_langsmith_client() -> Optional[Client]:
    """
    Get or create LangSmith client instance
    
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
            
            # Execute function with tracing
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
        query: Query string
        result: Tool result
        duration: Execution duration in seconds
        session_id: Session ID
    """
    if not settings.enable_langsmith:
        return
    
    client = get_langsmith_client()
    if not client:
        return
    
    try:
        # Log tool call as a run
        client.create_run(
            name=f"tool_{tool_name}",
            run_type="tool",
            inputs={"query": query},
            outputs={"result": str(result)[:500]},  # Truncate long results
            extra={"duration": duration, "session_id": session_id}
        )
        logger.debug(f"[LangSmith] Logged tool call: {tool_name}")
    except Exception as e:
        logger.warning(f"[LangSmith] Failed to log tool call: {e}")


def log_llm_call(prompt: str, response: str, model: str, tokens: int, duration: float, session_id: str):
    """
    Log LLM call to LangSmith
    
    Args:
        prompt: Input prompt
        response: LLM response
        model: Model name
        tokens: Token count
        duration: Execution duration in seconds
        session_id: Session ID
    """
    if not settings.enable_langsmith:
        return
    
    client = get_langsmith_client()
    if not client:
        return
    
    try:
        client.create_run(
            name="llm_call",
            run_type="llm",
            inputs={"prompt": prompt[:1000]},  # Truncate long prompts
            outputs={"response": response[:1000]},  # Truncate long responses
            extra={
                "model": model,
                "tokens": tokens,
                "duration": duration,
                "session_id": session_id
            }
        )
        logger.debug(f"[LangSmith] Logged LLM call: {model}")
    except Exception as e:
        logger.warning(f"[LangSmith] Failed to log LLM call: {e}")
