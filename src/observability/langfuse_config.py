"""
Langfuse integration for backup observability
Provides redundancy when LangSmith is unavailable
"""
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
from src.config import settings

logger = logging.getLogger(__name__)

# Try to import Langfuse, but make it optional
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
    try:
        from langfuse.decorators import langfuse_context, observe
        LANGFUSE_DECORATORS_AVAILABLE = True
    except ImportError:
        LANGFUSE_DECORATORS_AVAILABLE = False
        langfuse_context = None
        observe = None
except ImportError:
    LANGFUSE_AVAILABLE = False
    LANGFUSE_DECORATORS_AVAILABLE = False
    Langfuse = None
    langfuse_context = None
    observe = None

# Global Langfuse client instance
_langfuse_client: Optional[Langfuse] = None


def get_langfuse_client() -> Optional[Any]:
    """
    Get or create Langfuse client instance
    
    Returns:
        Langfuse client instance or None if not configured
    """
    global _langfuse_client
    
    if not settings.enable_langfuse or not LANGFUSE_AVAILABLE:
        return None
    
    if _langfuse_client is None:
        try:
            public_key = settings.langfuse_public_key
            secret_key = settings.langfuse_secret_key
            
            if not public_key or not secret_key or \
               public_key == "your_langfuse_public_key_here" or \
               secret_key == "your_langfuse_secret_key_here":
                logger.warning("Langfuse API keys not configured, skipping Langfuse initialization")
                return None
            
            _langfuse_client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=settings.langfuse_host
            )
            
            logger.info("Langfuse client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse client: {e}", exc_info=True)
            return None
    
    return _langfuse_client


def trace_with_langfuse(func: Callable) -> Callable:
    """
    Decorator to trace function execution with Langfuse
    Used as backup when LangSmith is unavailable
    
    Usage:
        @trace_with_langfuse
        async def stream_response(self, query: str, session_id: str):
            ...
    
    Args:
        func: Function to trace
        
    Returns:
        Wrapped function with tracing
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not settings.enable_langfuse or not LANGFUSE_AVAILABLE:
            return await func(*args, **kwargs)
        
        client = get_langfuse_client()
        if not client:
            return await func(*args, **kwargs)
        
        # Extract query and session_id for trace metadata
        query = kwargs.get("query", args[1] if len(args) > 1 else "unknown")
        session_id = kwargs.get("session_id", args[2] if len(args) > 2 else "unknown")
        
        try:
            # Set trace metadata if decorators available
            if LANGFUSE_DECORATORS_AVAILABLE and langfuse_context:
                langfuse_context.update_current_trace(
                    name=f"{func.__name__}",
                    metadata={
                        "query": query[:200],  # Truncate long queries
                        "session_id": session_id
                    }
                )
            
            logger.debug(f"[Langfuse] Tracing function execution - {func.__name__}, Session: {session_id}")
            
            # Execute function
            result = await func(*args, **kwargs)
            
            logger.debug(f"[Langfuse] Function execution completed - {func.__name__}, Session: {session_id}")
            return result
            
        except Exception as e:
            logger.error(f"[Langfuse] Error during function execution trace: {e}", exc_info=True)
            # Still execute function even if tracing fails
            return await func(*args, **kwargs)
    
    # Apply observe decorator if available
    if LANGFUSE_DECORATORS_AVAILABLE and observe:
        wrapper = observe(name=func.__name__)(wrapper)
    
    return wrapper


def log_tool_call_langfuse(tool_name: str, query: str, result: Any, duration: float, session_id: str):
    """
    Log tool call to Langfuse
    
    Args:
        tool_name: Name of the tool
        query: Query string
        result: Tool result
        duration: Execution duration in seconds
        session_id: Session ID
    """
    if not settings.enable_langfuse:
        return
    
    client = get_langfuse_client()
    if not client:
        return
    
    try:
        client.span(
            name=f"tool_{tool_name}",
            input={"query": query},
            output={"result": str(result)[:500]},  # Truncate long results
            metadata={"duration": duration, "session_id": session_id}
        )
        logger.debug(f"[Langfuse] Logged tool call: {tool_name}")
    except Exception as e:
        logger.warning(f"[Langfuse] Failed to log tool call: {e}")


def log_llm_call_langfuse(prompt: str, response: str, model: str, tokens: int, duration: float, session_id: str):
    """
    Log LLM call to Langfuse
    
    Args:
        prompt: Input prompt
        response: LLM response
        model: Model name
        tokens: Token count
        duration: Execution duration in seconds
        session_id: Session ID
    """
    if not settings.enable_langfuse:
        return
    
    client = get_langfuse_client()
    if not client:
        return
    
    try:
        client.generation(
            name="llm_call",
            model=model,
            input=prompt[:1000],  # Truncate long prompts
            output=response[:1000],  # Truncate long responses
            metadata={
                "tokens": tokens,
                "duration": duration,
                "session_id": session_id
            }
        )
        logger.debug(f"[Langfuse] Logged LLM call: {model}")
    except Exception as e:
        logger.warning(f"[Langfuse] Failed to log LLM call: {e}")
