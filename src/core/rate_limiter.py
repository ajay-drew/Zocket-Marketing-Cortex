"""
Client-side rate limiter for Groq API
Limits requests based on model rate limits (default: 5000 RPM for llama-3.1-8b-instant)
"""

import asyncio
import time
from typing import Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for API requests
    
    Limits requests to max_requests per time_window seconds
    Uses sliding window algorithm for accurate rate limiting
    """
    
    def __init__(
        self,
        max_requests: int = 5000,  # Default for llama-3.1-8b-instant (6000 RPM limit)
        time_window: float = 60.0,  # 1 minute window
        initial_tokens: Optional[int] = None
    ):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed in time window (default: 5000 for llama-3.1-8b-instant)
            time_window: Time window in seconds (default: 60.0 for 1 minute)
            initial_tokens: Initial tokens available (default: max_requests)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.initial_tokens = initial_tokens or max_requests
        
        # Sliding window: track request timestamps
        self.request_times: deque = deque()
        self._lock = asyncio.Lock()
        
        logger.info(
            f"RateLimiter initialized: {max_requests} requests per {time_window}s"
        )
    
    async def acquire(self) -> float:
        """
        Acquire permission to make a request
        
        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        async with self._lock:
            now = time.time()
            
            # Remove requests outside the time window
            while self.request_times and (now - self.request_times[0]) > self.time_window:
                self.request_times.popleft()
            
            # Check if we can make a request
            if len(self.request_times) < self.max_requests:
                # Can make request immediately
                self.request_times.append(now)
                return 0.0
            
            # Need to wait until oldest request expires
            oldest_request_time = self.request_times[0]
            wait_time = self.time_window - (now - oldest_request_time)
            
            # Add small buffer to ensure we don't hit the limit
            wait_time += 0.1  # 100ms buffer
            
            # Update request times after waiting
            self.request_times.append(now + wait_time)
            
            return wait_time
    
    async def wait_if_needed(self) -> None:
        """
        Wait if necessary to respect rate limit
        
        This is a convenience method that calls acquire() and waits
        """
        wait_time = await self.acquire()
        if wait_time > 0:
            logger.debug(f"Rate limiter: waiting {wait_time:.2f}s before next request")
            await asyncio.sleep(wait_time)
    
    def get_stats(self) -> dict:
        """
        Get current rate limiter statistics
        
        Returns:
            Dictionary with current stats
        """
        now = time.time()
        
        # Remove old requests
        while self.request_times and (now - self.request_times[0]) > self.time_window:
            self.request_times.popleft()
        
        return {
            "requests_in_window": len(self.request_times),
            "max_requests": self.max_requests,
            "time_window": self.time_window,
            "available_slots": self.max_requests - len(self.request_times),
            "utilization": len(self.request_times) / self.max_requests if self.max_requests > 0 else 0.0
        }


class ExponentialBackoff:
    """
    Exponential backoff for retry logic
    """
    
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize exponential backoff
        
        Args:
            base_delay: Base delay in seconds (default: 1.0)
            max_delay: Maximum delay in seconds (default: 60.0)
            multiplier: Multiplier for each retry (default: 2.0)
            jitter: Add random jitter to prevent thundering herd (default: True)
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number
        
        Args:
            attempt: Attempt number (1-indexed)
            
        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.multiplier ** (attempt - 1))
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled (random 0-20% of delay)
        if self.jitter:
            import random
            jitter_amount = delay * 0.2 * random.random()
            delay += jitter_amount
        
        return delay


# Global rate limiter instance for Groq API
_groq_rate_limiter: Optional[RateLimiter] = None


def get_groq_rate_limiter() -> RateLimiter:
    """
    Get or create global Groq rate limiter instance
    
    Returns:
        RateLimiter instance configured for Groq (default: 5000 RPM for llama-3.1-8b-instant, configurable via settings)
    """
    global _groq_rate_limiter
    
    if _groq_rate_limiter is None:
        # Import settings here to avoid circular imports
        from src.config import settings
        
        # Use configured rate limit (default: 5000, staying under 6000 RPM for llama-3.1-8b-instant)
        # Cap at 5900 to provide safety margin
        max_requests = min(settings.groq_rate_limit, 5900)
        _groq_rate_limiter = RateLimiter(
            max_requests=max_requests,
            time_window=60.0   # 1 minute window
        )
        logger.info(
            f"Groq rate limiter created: {max_requests} requests per minute "
            f"(staying under Groq's 6000 RPM limit for llama-3.1-8b-instant)"
        )
    
    return _groq_rate_limiter


async def rate_limited_call(
    func,
    *args,
    rate_limiter: Optional[RateLimiter] = None,
    max_retries: int = 3,
    backoff: Optional[ExponentialBackoff] = None,
    **kwargs
):
    """
    Execute a function with rate limiting and exponential backoff
    
    Args:
        func: Async function to call
        *args: Function arguments
        rate_limiter: Rate limiter instance (default: uses global Groq limiter)
        max_retries: Maximum retry attempts (default: 3)
        backoff: Exponential backoff instance (default: creates new)
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
        
    Raises:
        Exception: If all retries fail
    """
    if rate_limiter is None:
        rate_limiter = get_groq_rate_limiter()
    
    if backoff is None:
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=60.0)
    
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            # Wait for rate limit before making request
            await rate_limiter.wait_if_needed()
            
            # Execute function
            return await func(*args, **kwargs)
            
        except Exception as e:
            last_error = e
            
            # Check if it's a rate limit error
            error_str = str(e).lower()
            is_rate_limit = (
                "rate limit" in error_str or
                "429" in error_str or
                "ratelimiterror" in error_str
            )
            
            if not is_rate_limit or attempt >= max_retries:
                # Not a rate limit error or out of retries
                raise
            
            # Calculate backoff delay
            delay = backoff.get_delay(attempt)
            
            logger.warning(
                f"Rate limit error (attempt {attempt}/{max_retries}). "
                f"Retrying after {delay:.2f}s..."
            )
            
            await asyncio.sleep(delay)
    
    # All retries exhausted
    raise last_error
