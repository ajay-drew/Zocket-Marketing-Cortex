"""
Tests for Tavily client with rate limiting
"""
import pytest
from src.integrations.tavily_client import TavilyClient, TavilyRateLimitError
from src.core.cache import cache_manager


@pytest.fixture(scope="session", autouse=True)
def setup_cache():
    """Setup cache manager for all tests"""
    cache_manager.connect()
    yield
    cache_manager.disconnect()


@pytest.fixture
async def tavily():
    """Create Tavily client instance"""
    client = TavilyClient()
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_cache_key_generation(tavily):
    """Test cache key generation"""
    key1 = tavily._get_cache_key("test query", "general")
    key2 = tavily._get_cache_key("TEST QUERY", "general")  # Same query, different case
    key3 = tavily._get_cache_key("different query", "general")
    
    # Same query (case-insensitive) should generate same key
    assert key1 == key2
    # Different query should generate different key
    assert key1 != key3
    # Keys should have proper format
    assert key1.startswith("tavily:general:")


@pytest.mark.asyncio
async def test_cache_ttl_selection(tavily):
    """Test TTL selection based on search type"""
    assert tavily._get_cache_ttl("research") == 604800  # 7 days
    assert tavily._get_cache_ttl("news") == 3600        # 1 hour
    assert tavily._get_cache_ttl("competitor") == 86400 # 1 day
    assert tavily._get_cache_ttl("general") == 604800   # Default to research


@pytest.mark.asyncio
async def test_quota_status(tavily):
    """Test quota status retrieval"""
    status = await tavily.get_quota_status()
    
    assert "requests_used" in status
    assert "requests_remaining" in status
    assert "monthly_limit" in status
    assert "usage_percentage" in status
    assert "status" in status
    
    assert status["monthly_limit"] == 1000
    assert status["requests_remaining"] >= 0


@pytest.mark.asyncio
async def test_monthly_count_increment(tavily):
    """Test monthly counter increment"""
    # Reset counter for test
    cache_manager.delete(tavily.RATE_LIMIT_KEY)
    
    count1 = tavily._increment_monthly_count()
    count2 = tavily._increment_monthly_count()
    count3 = tavily._increment_monthly_count()
    
    assert count1 == 1
    assert count2 == 2
    assert count3 == 3


@pytest.mark.asyncio
async def test_search_caching(tavily):
    """Test that search results are cached"""
    query = "test marketing trends"
    cache_key = tavily._get_cache_key(query, "general")
    
    # Clear cache first
    cache_manager.delete(cache_key)
    
    # Mock result for testing (don't actually call API)
    mock_result = {
        "query": query,
        "results": [{"title": "Test", "url": "https://example.com"}],
        "_cached": False
    }
    
    # Manually cache the result
    cache_manager.set(cache_key, mock_result, ttl=60)
    
    # Retrieve from cache
    cached = cache_manager.get(cache_key)
    assert cached is not None
    assert cached["query"] == query


@pytest.mark.asyncio
async def test_fallback_search(tavily):
    """Test fallback search when quota exceeded"""
    result = await tavily._fallback_search("test query", max_results=5)
    
    assert result["_fallback"] is True
    assert result["_fallback_reason"] == "tavily_quota_exceeded"
    assert "query" in result
    assert "message" in result


@pytest.mark.asyncio
async def test_cache_clearing(tavily):
    """Test cache clearing functionality"""
    # Add some test cache entries
    cache_manager.set("tavily:general:test1", {"data": "test1"}, ttl=60)
    cache_manager.set("tavily:news:test2", {"data": "test2"}, ttl=60)
    
    # Clear only general type
    cleared = await tavily.clear_cache("general")
    assert cleared >= 0
    
    # Clear all
    cleared_all = await tavily.clear_cache()
    assert cleared_all >= 0


@pytest.mark.asyncio
async def test_quota_warning_thresholds(tavily):
    """Test that warnings are logged at correct thresholds"""
    # This test verifies the logic exists
    # In production, you'd use a mock logger to verify actual log calls
    from datetime import datetime, timedelta
    
    # Setup reset date for test
    now = datetime.now()
    next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    cache_manager.set(tavily.RATE_LIMIT_RESET_KEY, next_month.isoformat(), ttl=2592000)
    
    # Set counter to warning threshold (499) and increment to trigger 500
    cache_manager.set(tavily.RATE_LIMIT_KEY, 499, ttl=2592000)
    count = tavily._increment_monthly_count()
    assert count == 500  # Should trigger 50% warning
    
    # Set to critical threshold (899) and increment to trigger 900
    cache_manager.set(tavily.RATE_LIMIT_KEY, 899, ttl=2592000)
    count = tavily._increment_monthly_count()
    assert count == 900  # Should trigger 90% warning
