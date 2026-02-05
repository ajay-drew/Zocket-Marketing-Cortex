"""
Rate-limited wrapper for ChatGroq LLM
Ensures all Groq API calls respect the client-side rate limit (default: 5000 RPM for llama-3.1-8b-instant)
"""

from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from typing import Any, AsyncIterator, List, Optional
import logging
import asyncio

from src.core.rate_limiter import get_groq_rate_limiter, ExponentialBackoff

logger = logging.getLogger(__name__)


class RateLimitedChatGroq(ChatGroq):
    """
    Rate-limited wrapper for ChatGroq that enforces client-side rate limits
    
    Limits requests based on model rate limits (default: 5000 RPM for llama-3.1-8b-instant)
    """
    
    def __init__(self, *args, **kwargs):
        """
        Initialize rate-limited ChatGroq
        
        All arguments are passed to ChatGroq constructor
        """
        super().__init__(*args, **kwargs)
        # Use private attributes to avoid Pydantic validation issues
        self._rate_limiter = get_groq_rate_limiter()
        self._backoff = ExponentialBackoff(base_delay=1.0, max_delay=60.0)
        logger.info(f"RateLimitedChatGroq initialized with {self._rate_limiter.max_requests} RPM limit")
    
    async def ainvoke(
        self,
        input: List[BaseMessage] | str,
        config: Optional[Any] = None,
        **kwargs: Any
    ) -> Any:
        """
        Async invoke with rate limiting
        
        Args:
            input: Input messages or string
            config: Optional configuration
            **kwargs: Additional arguments
            
        Returns:
            LLM response
        """
        # Wait for rate limit before making request (RPM limit only, no daily token limit)
        await self._rate_limiter.wait_if_needed()
        
        try:
            response = await super().ainvoke(input, config, **kwargs)
            return response
        except Exception as e:
            # Check if it's a rate limit error and retry with backoff
            error_str = str(e).lower()
            is_rate_limit = (
                "rate limit" in error_str or
                "429" in error_str or
                "ratelimiterror" in error_str
            )
            
            if is_rate_limit:
                # Retry with exponential backoff
                for attempt in range(1, 4):  # Up to 3 retries
                    delay = self._backoff.get_delay(attempt)
                    logger.warning(
                        f"Groq rate limit hit (attempt {attempt}/3). "
                        f"Retrying after {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                    
                    # Wait for rate limiter again
                    await self._rate_limiter.wait_if_needed()
                    
                    try:
                        response = await super().ainvoke(input, config, **kwargs)
                        return response
                    except Exception as retry_error:
                        if attempt == 3:
                            # Last attempt failed
                            raise
                        # Check if still rate limit error
                        retry_error_str = str(retry_error).lower()
                        if not (
                            "rate limit" in retry_error_str or
                            "429" in retry_error_str or
                            "ratelimiterror" in retry_error_str
                        ):
                            # Different error, raise immediately
                            raise
            
            # Not a rate limit error or retries exhausted
            raise
    
    async def astream(
        self,
        input: List[BaseMessage] | str,
        config: Optional[Any] = None,
        **kwargs: Any
    ) -> AsyncIterator[Any]:
        """
        Async stream with rate limiting
        
        Args:
            input: Input messages or string
            config: Optional configuration
            **kwargs: Additional arguments
            
        Yields:
            LLM response chunks
        """
        # Wait for rate limit before making request (RPM limit only, no daily token limit)
        await self._rate_limiter.wait_if_needed()
        
        try:
            # Stream response chunks
            async for chunk in super().astream(input, config, **kwargs):
                yield chunk
        except Exception as e:
            # Check if it's a rate limit error and retry with backoff
            error_str = str(e).lower()
            is_rate_limit = (
                "rate limit" in error_str or
                "429" in error_str or
                "ratelimiterror" in error_str
            )
            
            if is_rate_limit:
                # Retry with exponential backoff
                for attempt in range(1, 4):  # Up to 3 retries
                    delay = self._backoff.get_delay(attempt)
                    logger.warning(
                        f"Groq rate limit hit during stream (attempt {attempt}/3). "
                        f"Retrying after {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                    
                    # Wait for rate limiter again
                    await self._rate_limiter.wait_if_needed()
                    
                    try:
                        # Stream response chunks
                        async for chunk in super().astream(input, config, **kwargs):
                            yield chunk
                        
                        return  # Success, exit retry loop
                    except Exception as retry_error:
                        if attempt == 3:
                            # Last attempt failed
                            raise
                        # Check if still rate limit error
                        retry_error_str = str(retry_error).lower()
                        if not (
                            "rate limit" in retry_error_str or
                            "429" in retry_error_str or
                            "ratelimiterror" in retry_error_str
                        ):
                            # Different error, raise immediately
                            raise
            
            # Not a rate limit error or retries exhausted
            raise
    
    async def agenerate(
        self,
        messages: List[List[BaseMessage]],
        stop: Optional[List[str]] = None,
        callbacks: Optional[Any] = None,
        **kwargs: Any
    ) -> Any:
        """
        Async generate with rate limiting
        
        Args:
            messages: List of message lists
            stop: Optional stop sequences
            callbacks: Optional callbacks (run manager)
            **kwargs: Additional arguments (may contain callbacks if passed via config)
            
        Returns:
            LLM generation result
        """
        # Wait for rate limit before making request (RPM limit only, no daily token limit)
        await self._rate_limiter.wait_if_needed()
        
        # Remove callbacks from kwargs if present to avoid duplicate argument
        # LangChain may pass callbacks both as a parameter and in kwargs
        kwargs.pop('callbacks', None)
        
        try:
            result = await super().agenerate(messages, stop=stop, callbacks=callbacks, **kwargs)
            return result
        except Exception as e:
            # Check if it's a rate limit error and retry with backoff
            error_str = str(e).lower()
            is_rate_limit = (
                "rate limit" in error_str or
                "429" in error_str or
                "ratelimiterror" in error_str
            )
            
            if is_rate_limit:
                # Retry with exponential backoff
                for attempt in range(1, 4):  # Up to 3 retries
                    delay = self._backoff.get_delay(attempt)
                    logger.warning(
                        f"Groq rate limit hit during generate (attempt {attempt}/3). "
                        f"Retrying after {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                    
                    # Wait for rate limiter again
                    await self._rate_limiter.wait_if_needed()
                    
                    # Remove callbacks from kwargs to avoid duplicate
                    retry_kwargs = kwargs.copy()
                    retry_kwargs.pop('callbacks', None)
                    
                    try:
                        result = await super().agenerate(messages, stop=stop, callbacks=callbacks, **retry_kwargs)
                        return result
                    except Exception as retry_error:
                        if attempt == 3:
                            # Last attempt failed
                            raise
                        # Check if still rate limit error
                        retry_error_str = str(retry_error).lower()
                        if not (
                            "rate limit" in retry_error_str or
                            "429" in retry_error_str or
                            "ratelimiterror" in retry_error_str
                        ):
                            # Different error, raise immediately
                            raise
            
            # Not a rate limit error or retries exhausted
            raise
