"""Tests for client-side rate limiter"""

import pytest
import asyncio
import time
from src.core.rate_limiter import RateLimiter, ExponentialBackoff, get_groq_rate_limiter


class TestRateLimiter:
    """Test rate limiter functionality"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self):
        """Test rate limiter initializes correctly"""
        limiter = RateLimiter(max_requests=5, time_window=60.0)
        stats = limiter.get_stats()
        
        assert stats["max_requests"] == 5
        assert stats["time_window"] == 60.0
        assert stats["requests_in_window"] == 0
        assert stats["available_slots"] == 5
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self):
        """Test rate limiter allows requests within limit"""
        limiter = RateLimiter(max_requests=3, time_window=60.0)
        
        # First 3 requests should be allowed immediately
        for i in range(3):
            wait_time = await limiter.acquire()
            assert wait_time == 0.0
        
        stats = limiter.get_stats()
        assert stats["requests_in_window"] == 3
        assert stats["available_slots"] == 0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess_requests(self):
        """Test rate limiter blocks requests exceeding limit"""
        limiter = RateLimiter(max_requests=2, time_window=1.0)  # 1 second window for faster test
        
        # First 2 requests should be allowed
        await limiter.acquire()
        await limiter.acquire()
        
        # Third request should require wait
        wait_time = await limiter.acquire()
        assert wait_time > 0.0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_sliding_window(self):
        """Test rate limiter sliding window behavior"""
        limiter = RateLimiter(max_requests=2, time_window=1.0)  # 1 second window
        
        # Make 2 requests
        await limiter.acquire()
        await limiter.acquire()
        
        # Wait for window to expire
        await asyncio.sleep(1.1)
        
        # Next request should be allowed immediately
        wait_time = await limiter.acquire()
        assert wait_time == 0.0
    
    @pytest.mark.asyncio
    async def test_groq_rate_limiter_default(self):
        """Test Groq rate limiter uses correct default (5000 RPM for llama-3.1-8b-instant)"""
        limiter = get_groq_rate_limiter()
        stats = limiter.get_stats()
        
        assert stats["max_requests"] <= 5900  # Must be <= 5900 to stay under Groq's 6000 RPM
        assert stats["max_requests"] >= 1000  # Should be at least 1000 for the new model
        assert stats["time_window"] == 60.0


class TestExponentialBackoff:
    """Test exponential backoff functionality"""
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff calculates delays correctly"""
        backoff = ExponentialBackoff(base_delay=1.0, multiplier=2.0, jitter=False)
        
        assert backoff.get_delay(1) == 1.0  # 1 * 2^0
        assert backoff.get_delay(2) == 2.0  # 1 * 2^1
        assert backoff.get_delay(3) == 4.0  # 1 * 2^2
        assert backoff.get_delay(4) == 8.0  # 1 * 2^3
    
    def test_exponential_backoff_max_delay(self):
        """Test exponential backoff respects max delay"""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=5.0, jitter=False)
        
        # Delay should be capped at max_delay
        delay = backoff.get_delay(10)  # Would be 512 without cap
        assert delay <= 5.0
    
    def test_exponential_backoff_jitter(self):
        """Test exponential backoff adds jitter when enabled"""
        backoff = ExponentialBackoff(base_delay=1.0, jitter=True)
        
        # With jitter, delay should vary slightly
        delays = [backoff.get_delay(2) for _ in range(10)]
        # All should be close to 2.0 but not exactly the same
        assert all(1.6 <= d <= 2.4 for d in delays)  # 2.0 ± 20% jitter
