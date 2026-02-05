"""
Redis caching layer for performance optimization
"""
import redis
from typing import Optional, Any
import json
import logging
import asyncio
from src.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages Redis caching for frequent queries"""
    
    def __init__(self):
        """Initialize Redis client"""
        self.redis_client: Optional[redis.Redis] = None
        self.default_ttl = 3600  # 1 hour default TTL
    
    def connect(self):
        """Establish Redis connection (Upstash serverless)"""
        try:
            # Upstash Redis - synchronous client
            self.redis_client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Upstash Redis connected successfully")
        except Exception as e:
            logger.error(f"Upstash Redis connection failed: {e}")
            logger.error(f"Make sure REDIS_URL is in format: rediss://default:PASSWORD@ENDPOINT.upstash.io:6379")
            self.redis_client = None
    
    async def ping(self) -> bool:
        """
        Ping Redis to check connection (async - non-blocking)
        
        Returns:
            True if connection is healthy, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.redis_client.ping()
            )
            return True
        except Exception as e:
            logger.error(f"Redis ping error: {e}")
            return False
    
    def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Upstash Redis disconnected")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache (synchronous - for backward compatibility)
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if not self.redis_client:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value:
                logger.debug(f"Cache hit: {key}")
                return json.loads(value)
            logger.debug(f"Cache miss: {key}")
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def aget(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache (async - non-blocking)
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if not self.redis_client:
            return None
        
        try:
            loop = asyncio.get_event_loop()
            value = await loop.run_in_executor(
                None,
                lambda: self.redis_client.get(key)
            )
            if value:
                logger.debug(f"Cache hit: {key}")
                return json.loads(value)
            logger.debug(f"Cache miss: {key}")
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store value in cache (synchronous - for backward compatibility)
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 1 hour)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            serialized = json.dumps(value)
            self.redis_client.setex(
                key,
                ttl or self.default_ttl,
                serialized
            )
            logger.debug(f"Cached: {key} (TTL: {ttl or self.default_ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def aset(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store value in cache (async - non-blocking)
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 1 hour)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            serialized = json.dumps(value)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.redis_client.setex(
                    key,
                    ttl or self.default_ttl,
                    serialized
                )
            )
            logger.debug(f"Cached: {key} (TTL: {ttl or self.default_ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.delete(key)
            logger.debug(f"Deleted from cache: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching a pattern
        
        Args:
            pattern: Key pattern (e.g., "user:*")
            
        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0
        
        try:
            keys = []
            for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} keys matching pattern: {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0


# Global cache manager instance
cache_manager = CacheManager()
