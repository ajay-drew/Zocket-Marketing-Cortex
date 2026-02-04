"""
Retry logic with exponential backoff
Handles transient failures gracefully
"""
import asyncio
import random
import logging
from typing import Callable, Type, Tuple, Any, Optional
from functools import wraps
from datetime import datetime, timedelta
from src.config import settings

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Base exception for retryable errors"""
    pass


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted"""
    pass


def is_retryable_error(error: Exception) -> bool:
    """
    Check if error is retryable
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is retryable, False otherwise
    """
    retryable_types = (
        TimeoutError,
        ConnectionError,
        ConnectionResetError,
        ConnectionRefusedError,
        OSError,
    )
    
    # Check exception type
    if isinstance(error, retryable_types):
        return True
    
    # Check exception message for rate limit
    error_str = str(error).lower()
    if "rate limit" in error_str or "429" in error_str:
        return True
    
    # Check exception message for timeout
    if "timeout" in error_str or "timed out" in error_str:
        return True
    
    return False


def calculate_backoff(attempt: int, base_delay: float, max_delay: float, jitter: bool = True) -> float:
    """
    Calculate exponential backoff delay
    
    Args:
        attempt: Current attempt number (1-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Whether to add jitter
        
    Returns:
        Delay in seconds
    """
    # Exponential backoff: base_delay * 2^(attempt-1)
    delay = base_delay * (2 ** (attempt - 1))
    
    # Cap at max delay
    delay = min(delay, max_delay)
    
    # Add jitter to prevent thundering herd
    if jitter:
        jitter_amount = delay * 0.1  # 10% jitter
        delay = delay + random.uniform(-jitter_amount, jitter_amount)
        delay = max(0, delay)  # Ensure non-negative
    
    return delay


def retry_with_backoff(
    max_attempts: int = None,
    base_delay: float = None,
    max_delay: float = 60.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = None,
    jitter: bool = True
):
    """
    Decorator to retry function with exponential backoff
    
    Usage:
        @retry_with_backoff(max_attempts=3, base_delay=1.0)
        async def search(self, query: str):
            ...
    
    Args:
        max_attempts: Maximum number of retry attempts (default: from settings)
        base_delay: Base delay in seconds (default: from settings)
        max_delay: Maximum delay in seconds
        retryable_exceptions: Tuple of exception types to retry on
        jitter: Whether to add jitter to backoff
        
    Returns:
        Decorator function
    """
    max_attempts = max_attempts or settings.retry_max_attempts
    base_delay = base_delay or settings.retry_base_delay
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    # Check if error is retryable
                    is_retryable = False
                    if retryable_exceptions:
                        is_retryable = isinstance(e, retryable_exceptions)
                    else:
                        is_retryable = is_retryable_error(e)
                    
                    if not is_retryable:
                        # Not retryable, raise immediately
                        raise
                    
                    # Check if we have more attempts
                    if attempt >= max_attempts:
                        logger.error(
                            f"[Retry] {func.__name__}: All {max_attempts} attempts exhausted. "
                            f"Last error: {e}"
                        )
                        raise RetryExhaustedError(
                            f"All {max_attempts} retry attempts exhausted"
                        ) from e
                    
                    # Calculate backoff delay
                    delay = calculate_backoff(attempt, base_delay, max_delay, jitter)
                    
                    logger.warning(
                        f"[Retry] {func.__name__}: Attempt {attempt}/{max_attempts} failed. "
                        f"Retrying in {delay:.2f}s... Error: {e}"
                    )
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
            
            # Should never reach here, but just in case
            if last_error:
                raise RetryExhaustedError(
                    f"All {max_attempts} retry attempts exhausted"
                ) from last_error
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            last_error = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    # Check if error is retryable
                    is_retryable = False
                    if retryable_exceptions:
                        is_retryable = isinstance(e, retryable_exceptions)
                    else:
                        is_retryable = is_retryable_error(e)
                    
                    if not is_retryable:
                        # Not retryable, raise immediately
                        raise
                    
                    # Check if we have more attempts
                    if attempt >= max_attempts:
                        logger.error(
                            f"[Retry] {func.__name__}: All {max_attempts} attempts exhausted. "
                            f"Last error: {e}"
                        )
                        raise RetryExhaustedError(
                            f"All {max_attempts} retry attempts exhausted"
                        ) from e
                    
                    # Calculate backoff delay
                    delay = calculate_backoff(attempt, base_delay, max_delay, jitter)
                    
                    logger.warning(
                        f"[Retry] {func.__name__}: Attempt {attempt}/{max_attempts} failed. "
                        f"Retrying in {delay:.2f}s... Error: {e}"
                    )
                    
                    # Wait before retry
                    time.sleep(delay)
            
            # Should never reach here, but just in case
            if last_error:
                raise RetryExhaustedError(
                    f"All {max_attempts} retry attempts exhausted"
                ) from last_error
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class AsyncRetry:
    """
    Async retry utility class for more control
    """
    
    def __init__(
        self,
        max_attempts: int = None,
        base_delay: float = None,
        max_delay: float = 60.0,
        retryable_exceptions: Tuple[Type[Exception], ...] = None,
        jitter: bool = True
    ):
        """
        Initialize async retry
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            retryable_exceptions: Tuple of exception types to retry on
            jitter: Whether to add jitter to backoff
        """
        self.max_attempts = max_attempts or settings.retry_max_attempts
        self.base_delay = base_delay or settings.retry_base_delay
        self.max_delay = max_delay
        self.retryable_exceptions = retryable_exceptions
        self.jitter = jitter
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with retry logic
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            RetryExhaustedError: If all attempts fail
        """
        last_error = None
        
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                # Check if error is retryable
                is_retryable = False
                if self.retryable_exceptions:
                    is_retryable = isinstance(e, self.retryable_exceptions)
                else:
                    is_retryable = is_retryable_error(e)
                
                if not is_retryable:
                    # Not retryable, raise immediately
                    raise
                
                # Check if we have more attempts
                if attempt >= self.max_attempts:
                    logger.error(
                        f"[AsyncRetry] {func.__name__}: All {self.max_attempts} attempts exhausted. "
                        f"Last error: {e}"
                    )
                    raise RetryExhaustedError(
                        f"All {self.max_attempts} retry attempts exhausted"
                    ) from e
                
                # Calculate backoff delay
                delay = calculate_backoff(attempt, self.base_delay, self.max_delay, self.jitter)
                
                logger.warning(
                    f"[AsyncRetry] {func.__name__}: Attempt {attempt}/{self.max_attempts} failed. "
                    f"Retrying in {delay:.2f}s... Error: {e}"
                )
                
                # Wait before retry
                await asyncio.sleep(delay)
        
        # Should never reach here, but just in case
        if last_error:
            raise RetryExhaustedError(
                f"All {self.max_attempts} retry attempts exhausted"
            ) from last_error
