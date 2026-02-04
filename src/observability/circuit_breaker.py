"""
Circuit breaker pattern implementation
Prevents cascading failures by temporarily disabling failing services
"""
import time
import logging
from enum import Enum
from typing import Optional, Callable, Any
from functools import wraps
from datetime import datetime, timedelta
from src.config import settings
from src.core.cache import cache_manager

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, requests rejected
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker implementation with Redis-backed state management
    
    Prevents cascading failures by:
    1. Tracking consecutive failures
    2. Opening circuit after threshold
    3. Testing recovery in half-open state
    4. Closing circuit when healthy
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = None,
        timeout: int = None,
        redis_key_prefix: str = "circuit_breaker"
    ):
        """
        Initialize circuit breaker
        
        Args:
            name: Circuit breaker name (e.g., "tavily", "pinecone")
            failure_threshold: Number of consecutive failures before opening (default: from settings)
            timeout: Seconds to wait before testing recovery (default: from settings)
            redis_key_prefix: Redis key prefix for state storage
        """
        self.name = name
        self.failure_threshold = failure_threshold or settings.circuit_breaker_failure_threshold
        self.timeout = timeout or settings.circuit_breaker_timeout
        self.redis_key_prefix = redis_key_prefix
        
        # Redis keys
        self.state_key = f"{redis_key_prefix}:{name}:state"
        self.failure_count_key = f"{redis_key_prefix}:{name}:failure_count"
        self.last_failure_key = f"{redis_key_prefix}:{name}:last_failure"
        self.success_count_key = f"{redis_key_prefix}:{name}:success_count"
    
    def _get_state(self) -> CircuitState:
        """
        Get current circuit state from Redis
        
        Returns:
            Circuit state
        """
        state_str = cache_manager.get(self.state_key)
        if not state_str:
            return CircuitState.CLOSED
        
        try:
            return CircuitState(state_str)
        except ValueError:
            return CircuitState.CLOSED
    
    def _set_state(self, state: CircuitState):
        """
        Set circuit state in Redis
        
        Args:
            state: Circuit state
        """
        cache_manager.set(
            self.state_key,
            state.value,
            ttl=self.timeout * 2  # Keep state longer than timeout
        )
    
    def _get_failure_count(self) -> int:
        """
        Get current failure count
        
        Returns:
            Failure count
        """
        count = cache_manager.get(self.failure_count_key)
        return int(count) if count else 0
    
    def _increment_failure_count(self) -> int:
        """
        Increment failure count
        
        Returns:
            New failure count
        """
        count = self._get_failure_count() + 1
        cache_manager.set(
            self.failure_count_key,
            count,
            ttl=self.timeout * 2
        )
        cache_manager.set(
            self.last_failure_key,
            datetime.utcnow().isoformat(),
            ttl=self.timeout * 2
        )
        return count
    
    def _reset_failure_count(self):
        """Reset failure count"""
        cache_manager.delete(self.failure_count_key)
        cache_manager.delete(self.last_failure_key)
    
    def _get_success_count(self) -> int:
        """
        Get current success count (for half-open state)
        
        Returns:
            Success count
        """
        count = cache_manager.get(self.success_count_key)
        return int(count) if count else 0
    
    def _increment_success_count(self) -> int:
        """
        Increment success count
        
        Returns:
            New success count
        """
        count = self._get_success_count() + 1
        cache_manager.set(
            self.success_count_key,
            count,
            ttl=self.timeout
        )
        return count
    
    def _reset_success_count(self):
        """Reset success count"""
        cache_manager.delete(self.success_count_key)
    
    def _should_attempt_request(self) -> bool:
        """
        Check if request should be attempted
        
        Returns:
            True if request should be attempted, False otherwise
        """
        state = self._get_state()
        
        if state == CircuitState.CLOSED:
            return True
        
        if state == CircuitState.OPEN:
            # Check if timeout has passed
            last_failure_str = cache_manager.get(self.last_failure_key)
            if not last_failure_str:
                # No last failure recorded, allow attempt
                self._set_state(CircuitState.HALF_OPEN)
                return True
            
            try:
                last_failure = datetime.fromisoformat(last_failure_str)
                if datetime.utcnow() - last_failure > timedelta(seconds=self.timeout):
                    # Timeout passed, move to half-open
                    self._set_state(CircuitState.HALF_OPEN)
                    self._reset_success_count()
                    logger.info(f"[CircuitBreaker] {self.name}: Moving to HALF_OPEN state")
                    return True
            except (ValueError, TypeError):
                # Invalid timestamp, allow attempt
                self._set_state(CircuitState.HALF_OPEN)
                return True
            
            return False
        
        if state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """Record successful request"""
        state = self._get_state()
        
        if state == CircuitState.HALF_OPEN:
            # Need 2 consecutive successes to close
            success_count = self._increment_success_count()
            if success_count >= 2:
                self._set_state(CircuitState.CLOSED)
                self._reset_failure_count()
                self._reset_success_count()
                logger.info(f"[CircuitBreaker] {self.name}: Circuit CLOSED (recovered)")
        elif state == CircuitState.CLOSED:
            # Reset failure count on success
            self._reset_failure_count()
    
    def record_failure(self):
        """Record failed request"""
        state = self._get_state()
        
        failure_count = self._increment_failure_count()
        
        if state == CircuitState.HALF_OPEN:
            # Any failure in half-open moves back to open
            self._set_state(CircuitState.OPEN)
            logger.warning(f"[CircuitBreaker] {self.name}: Circuit OPEN (failed in half-open)")
        elif state == CircuitState.CLOSED:
            if failure_count >= self.failure_threshold:
                self._set_state(CircuitState.OPEN)
                logger.error(f"[CircuitBreaker] {self.name}: Circuit OPEN (threshold reached: {failure_count})")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function with circuit breaker protection
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        if not self._should_attempt_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker {self.name} is OPEN. Request rejected."
            )
        
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    async def acall(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call async function with circuit breaker protection
        
        Args:
            func: Async function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        if not self._should_attempt_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker {self.name} is OPEN. Request rejected."
            )
        
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    def get_status(self) -> dict:
        """
        Get circuit breaker status
        
        Returns:
            Status dictionary
        """
        state = self._get_state()
        failure_count = self._get_failure_count()
        last_failure = cache_manager.get(self.last_failure_key)
        
        return {
            "name": self.name,
            "state": state.value,
            "failure_count": failure_count,
            "failure_threshold": self.failure_threshold,
            "timeout": self.timeout,
            "last_failure": last_failure,
            "is_open": state == CircuitState.OPEN
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected"""
    pass


# Global circuit breakers
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """
    Get or create circuit breaker instance
    
    Args:
        name: Circuit breaker name
        **kwargs: Additional arguments for CircuitBreaker
        
    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, **kwargs)
    return _circuit_breakers[name]


def circuit_breaker(name: str, fallback: Optional[Callable] = None):
    """
    Decorator to add circuit breaker protection to a function
    
    Usage:
        @circuit_breaker("tavily", fallback=lambda: "Service unavailable")
        async def search_with_fallback(self, query: str):
            ...
    
    Args:
        name: Circuit breaker name
        fallback: Fallback function to call when circuit is open
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        cb = get_circuit_breaker(name)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await cb.acall(func, *args, **kwargs)
            except CircuitBreakerOpenError:
                if fallback:
                    if callable(fallback):
                        if hasattr(fallback, "__call__") and not hasattr(fallback, "__await__"):
                            # Sync fallback
                            return fallback(*args, **kwargs)
                        else:
                            # Async fallback
                            return await fallback(*args, **kwargs)
                    else:
                        return fallback
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return cb.call(func, *args, **kwargs)
            except CircuitBreakerOpenError:
                if fallback:
                    if callable(fallback):
                        return fallback(*args, **kwargs)
                    else:
                        return fallback
                raise
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
