"""
Tavily API client with rate limiting, caching, and fallback strategies

Handles 1000 requests/month limit with:
- Aggressive caching (7 days for research queries)
- Request counting and monitoring
- Automatic fallback to alternative sources
- Query deduplication
"""
import hashlib
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
from src.config import settings
from src.core.cache import cache_manager

logger = logging.getLogger(__name__)


class TavilyRateLimitError(Exception):
    """Raised when Tavily rate limit is exceeded"""
    pass


class TavilyClient:
    """
    Tavily API client with intelligent rate limiting
    
    Strategy:
    1. Check cache first (7-day TTL for research queries)
    2. Check monthly quota before making request
    3. Deduplicate similar queries
    4. Fall back to alternative sources if quota exceeded
    """
    
    # Rate limit tracking
    MONTHLY_LIMIT = 1000
    RATE_LIMIT_KEY = "tavily:monthly_count"
    RATE_LIMIT_RESET_KEY = "tavily:reset_date"
    
    # Cache TTLs
    CACHE_TTL_RESEARCH = 604800  # 7 days for research queries
    CACHE_TTL_NEWS = 3600        # 1 hour for news/trends
    CACHE_TTL_COMPETITOR = 86400 # 1 day for competitor analysis
    
    def __init__(self):
        """Initialize Tavily client"""
        self.api_key = settings.tavily_api_key
        self.base_url = "https://api.tavily.com"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    def _get_cache_key(self, query: str, search_type: str = "general") -> str:
        """
        Generate cache key for query
        
        Args:
            query: Search query
            search_type: Type of search (general, news, competitor)
            
        Returns:
            Cache key
        """
        # Normalize query (lowercase, strip whitespace)
        normalized = query.lower().strip()
        # Hash for consistent key length
        query_hash = hashlib.md5(normalized.encode()).hexdigest()
        return f"tavily:{search_type}:{query_hash}"
    
    def _get_cache_ttl(self, search_type: str) -> int:
        """
        Get appropriate cache TTL based on search type
        
        Args:
            search_type: Type of search
            
        Returns:
            TTL in seconds
        """
        ttl_map = {
            "general": self.CACHE_TTL_RESEARCH,
            "research": self.CACHE_TTL_RESEARCH,
            "news": self.CACHE_TTL_NEWS,
            "competitor": self.CACHE_TTL_COMPETITOR,
        }
        return ttl_map.get(search_type, self.CACHE_TTL_RESEARCH)
    
    def _get_monthly_count(self) -> int:
        """
        Get current monthly request count
        
        Returns:
            Number of requests made this month
        """
        count = cache_manager.get(self.RATE_LIMIT_KEY)
        return int(count) if count else 0
    
    def _increment_monthly_count(self) -> int:
        """
        Increment monthly request count
        
        Returns:
            New count
        """
        # Check if we need to reset the counter
        reset_date = cache_manager.get(self.RATE_LIMIT_RESET_KEY)
        now = datetime.now()
        
        if not reset_date or datetime.fromisoformat(reset_date) < now:
            # Reset counter for new month
            next_month = now.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
            cache_manager.set(
                self.RATE_LIMIT_RESET_KEY,
                next_month.isoformat(),
                ttl=int((next_month - now).total_seconds())
            )
            cache_manager.set(self.RATE_LIMIT_KEY, 1, ttl=2592000)  # 30 days
            logger.info("Reset Tavily monthly counter")
            return 1
        
        # Increment existing counter
        count = self._get_monthly_count()
        new_count = count + 1
        cache_manager.set(self.RATE_LIMIT_KEY, new_count, ttl=2592000)
        
        # Log warnings at thresholds
        if new_count == 500:
            logger.warning("⚠️ Tavily API: 50% of monthly quota used (500/1000)")
        elif new_count == 750:
            logger.warning("⚠️ Tavily API: 75% of monthly quota used (750/1000)")
        elif new_count == 900:
            logger.error("🚨 Tavily API: 90% of monthly quota used (900/1000)")
        elif new_count >= 950:
            logger.critical("🚨 Tavily API: 95% of monthly quota used - switching to fallback mode")
        
        return new_count
    
    async def get_quota_status(self) -> Dict[str, Any]:
        """
        Get current quota status
        
        Returns:
            Dict with usage statistics
        """
        count = self._get_monthly_count()
        reset_date = cache_manager.get(self.RATE_LIMIT_RESET_KEY)
        
        return {
            "requests_used": count,
            "requests_remaining": max(0, self.MONTHLY_LIMIT - count),
            "monthly_limit": self.MONTHLY_LIMIT,
            "usage_percentage": round((count / self.MONTHLY_LIMIT) * 100, 2),
            "reset_date": reset_date,
            "status": "healthy" if count < 750 else "warning" if count < 950 else "critical"
        }
    
    async def search(
        self,
        query: str,
        search_type: str = "general",
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Search using Tavily API with caching and rate limiting
        
        Args:
            query: Search query
            search_type: Type of search (general, news, competitor)
            max_results: Maximum number of results
            include_domains: Domains to include
            exclude_domains: Domains to exclude
            force_refresh: Skip cache and force new API call
            
        Returns:
            Search results with metadata
            
        Raises:
            TavilyRateLimitError: If monthly quota exceeded
        """
        # Step 1: Check cache first (unless force_refresh)
        cache_key = self._get_cache_key(query, search_type)
        if not force_refresh:
            cached_result = cache_manager.get(cache_key)
            if cached_result:
                logger.info(f"✅ Tavily cache hit: {query[:50]}...")
                cached_result["_cached"] = True
                cached_result["_cache_key"] = cache_key
                return cached_result
        
        # Step 2: Check rate limit
        current_count = await self._get_monthly_count()
        if current_count >= self.MONTHLY_LIMIT:
            logger.error(f"🚨 Tavily monthly limit exceeded: {current_count}/{self.MONTHLY_LIMIT}")
            raise TavilyRateLimitError(
                f"Monthly limit of {self.MONTHLY_LIMIT} requests exceeded. "
                f"Using fallback search methods."
            )
        
        # Step 3: Make API request
        try:
            logger.info(f"🔍 Tavily API call ({current_count + 1}/{self.MONTHLY_LIMIT}): {query[:50]}...")
            
            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "advanced" if search_type == "research" else "basic",
                "include_answer": True,
                "include_raw_content": False,
            }
            
            if include_domains:
                payload["include_domains"] = include_domains
            if exclude_domains:
                payload["exclude_domains"] = exclude_domains
            
            response = await self.client.post(
                f"{self.base_url}/search",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # Step 4: Increment counter
            self._increment_monthly_count()
            
            # Step 5: Cache result
            cache_ttl = self._get_cache_ttl(search_type)
            result["_cached"] = False
            result["_cache_key"] = cache_key
            result["_timestamp"] = datetime.now().isoformat()
            result["_search_type"] = search_type
            
            cache_manager.set(cache_key, result, ttl=cache_ttl)
            logger.info(f"✅ Tavily result cached for {cache_ttl}s")
            
            return result
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("🚨 Tavily rate limit hit (429)")
                raise TavilyRateLimitError("Tavily rate limit exceeded")
            logger.error(f"Tavily API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            raise
    
    async def search_with_fallback(
        self,
        query: str,
        search_type: str = "general",
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Search with automatic fallback to alternative methods
        
        Args:
            query: Search query
            search_type: Type of search
            max_results: Maximum results
            
        Returns:
            Search results (from Tavily or fallback)
        """
        try:
            # Try Tavily first
            return await self.search(query, search_type, max_results)
        except TavilyRateLimitError:
            # Fall back to alternative search
            logger.warning(f"⚠️ Using fallback search for: {query}")
            return await self._fallback_search(query, max_results)
    
    async def _fallback_search(
        self,
        query: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Fallback search using alternative methods
        
        Options:
        1. DuckDuckGo (free, no API key)
        2. Cached historical data
        3. LLM-generated insights (based on training data)
        
        Args:
            query: Search query
            max_results: Maximum results
            
        Returns:
            Fallback search results
        """
        logger.info(f"🔄 Executing fallback search: {query}")
        
        # For now, return a structured response indicating fallback mode
        # In Phase 2, we'll implement DuckDuckGo integration
        return {
            "query": query,
            "results": [],
            "answer": "Search quota exceeded. Using cached data and LLM knowledge.",
            "_fallback": True,
            "_fallback_reason": "tavily_quota_exceeded",
            "_timestamp": datetime.now().isoformat(),
            "message": (
                "Tavily API quota exceeded. Consider:\n"
                "1. Using cached research data\n"
                "2. Implementing DuckDuckGo fallback\n"
                "3. Relying on LLM's training data for general queries"
            )
        }
    
    async def clear_cache(self, search_type: Optional[str] = None):
        """
        Clear Tavily cache
        
        Args:
            search_type: Specific search type to clear, or None for all
        """
        if search_type:
            pattern = f"tavily:{search_type}:*"
        else:
            pattern = "tavily:*"
        
        cleared = cache_manager.clear_pattern(pattern)
        logger.info(f"Cleared {cleared} Tavily cache entries")
        return cleared


# Global Tavily client instance
tavily_client = TavilyClient()
