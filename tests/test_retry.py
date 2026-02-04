"""
Comprehensive tests for retry logic
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
from src.observability.retry import (
    retry_with_backoff,
    AsyncRetry,
    RetryExhaustedError,
    is_retryable_error,
    calculate_backoff
)


class TestRetryableErrorDetection:
    """Test retryable error detection"""
    
    def test_timeout_error_retryable(self):
        """Test TimeoutError is retryable"""
        assert is_retryable_error(TimeoutError("Timeout")) is True
    
    def test_connection_error_retryable(self):
        """Test ConnectionError is retryable"""
        assert is_retryable_error(ConnectionError("Connection failed")) is True
    
    def test_rate_limit_error_retryable(self):
        """Test rate limit error is retryable"""
        error = Exception("Rate limit exceeded")
        assert is_retryable_error(error) is True
    
    def test_value_error_not_retryable(self):
        """Test ValueError is not retryable"""
        assert is_retryable_error(ValueError("Invalid input")) is False
    
    def test_key_error_not_retryable(self):
        """Test KeyError is not retryable"""
        assert is_retryable_error(KeyError("key")) is False


class TestBackoffCalculation:
    """Test exponential backoff calculation"""
    
    def test_backoff_exponential(self):
        """Test backoff increases exponentially"""
        delay1 = calculate_backoff(1, base_delay=1.0, max_delay=60.0)
        delay2 = calculate_backoff(2, base_delay=1.0, max_delay=60.0)
        delay3 = calculate_backoff(3, base_delay=1.0, max_delay=60.0)
        
        assert delay1 < delay2 < delay3
    
    def test_backoff_capped(self):
        """Test backoff is capped at max delay"""
        delay = calculate_backoff(10, base_delay=1.0, max_delay=5.0, jitter=False)
        assert delay <= 5.0
        
        # With jitter, may slightly exceed but should be close
        delay_with_jitter = calculate_backoff(10, base_delay=1.0, max_delay=5.0, jitter=True)
        assert delay_with_jitter <= 5.5  # Allow small jitter overflow
    
    def test_backoff_with_jitter(self):
        """Test backoff includes jitter"""
        delay1 = calculate_backoff(2, base_delay=1.0, max_delay=60.0, jitter=True)
        delay2 = calculate_backoff(2, base_delay=1.0, max_delay=60.0, jitter=True)
        
        # With jitter, delays should vary (may be same by chance, but usually different)
        # Base delay for attempt 2 is 2.0, jitter adds ±0.2
        assert 1.8 <= delay1 <= 2.2
        assert 1.8 <= delay2 <= 2.2


class TestRetryDecorator:
    """Test retry decorator"""
    
    @pytest.mark.asyncio
    async def test_retry_immediate_success(self):
        """Test function succeeds immediately"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_after_transient_failure(self):
        """Test retry succeeds after transient failure"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Temporary connection issue")
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test retry exhausted after max attempts"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=2, base_delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Persistent timeout")
        
        with pytest.raises(RetryExhaustedError) as exc_info:
            await test_func()
        
        assert call_count == 2
        assert "2" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_retry_non_retryable_error(self):
        """Test non-retryable errors are not retried"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input - not retryable")
        
        with pytest.raises(ValueError):
            await test_func()
        
        assert call_count == 1  # Should not retry
    
    @pytest.mark.asyncio
    async def test_retry_specific_exceptions(self):
        """Test retry with specific exception types"""
        call_count = 0
        
        @retry_with_backoff(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,)
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_sync_function(self):
        """Test retry on synchronous function"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def sync_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary")
            return "success"
        
        result = sync_func()
        assert result == "success"
        assert call_count == 2


class TestAsyncRetryClass:
    """Test AsyncRetry class"""
    
    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Test AsyncRetry succeeds"""
        call_count = 0
        
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        retry = AsyncRetry(max_attempts=3, base_delay=0.01)
        result = await retry.execute(test_func)
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_async_retry_with_failures(self):
        """Test AsyncRetry with failures"""
        call_count = 0
        
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("Timeout")
            return "success"
        
        retry = AsyncRetry(max_attempts=3, base_delay=0.01)
        result = await retry.execute(test_func)
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_retry_exhausted(self):
        """Test AsyncRetry exhausted"""
        call_count = 0
        
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent failure")
        
        retry = AsyncRetry(max_attempts=2, base_delay=0.01)
        
        with pytest.raises(RetryExhaustedError):
            await retry.execute(test_func)
        
        assert call_count == 2
