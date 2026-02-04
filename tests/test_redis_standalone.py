"""
Standalone Redis test - can run without pytest
"""
import pytest
import asyncio
import redis.asyncio as redis
from src.config import settings


@pytest.mark.asyncio
async def test_redis_operations():
    """Test Redis with various operations"""
    print("\n" + "="*60)
    print("🧪 Testing Redis Operations")
    print("="*60 + "\n")
    
    try:
        # Connect
        print(f"📡 Connecting to Redis: {settings.redis_url}")
        redis_client = await redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Test 1: Ping
        print("1️⃣ Testing PING...")
        pong = await redis_client.ping()
        assert pong is True
        print("   ✅ PING successful")
        
        # Test 2: Set/Get
        print("\n2️⃣ Testing SET/GET...")
        await redis_client.set("test:key1", "value1", ex=60)
        value = await redis_client.get("test:key1")
        assert value == "value1"
        print(f"   ✅ SET/GET successful: {value}")
        
        # Test 3: JSON storage (for cache)
        print("\n3️⃣ Testing JSON storage...")
        import json
        test_data = {"campaign_id": "123", "name": "Test Campaign", "roas": 3.5}
        await redis_client.set("test:json", json.dumps(test_data), ex=60)
        retrieved = json.loads(await redis_client.get("test:json"))
        assert retrieved["campaign_id"] == "123"
        print(f"   ✅ JSON storage successful: {retrieved}")
        
        # Test 4: Counter (for Tavily rate limiting)
        print("\n4️⃣ Testing counter operations...")
        await redis_client.set("test:counter", 0)
        await redis_client.incr("test:counter")
        await redis_client.incr("test:counter")
        count = int(await redis_client.get("test:counter"))
        assert count == 2
        print(f"   ✅ Counter operations successful: {count}")
        
        # Test 5: Pattern deletion
        print("\n5️⃣ Testing pattern deletion...")
        await redis_client.set("test:pattern:1", "val1")
        await redis_client.set("test:pattern:2", "val2")
        await redis_client.set("test:other", "val3")
        
        keys_to_delete = []
        async for key in redis_client.scan_iter(match="test:pattern:*"):
            keys_to_delete.append(key)
        
        if keys_to_delete:
            deleted = await redis_client.delete(*keys_to_delete)
            print(f"   ✅ Pattern deletion successful: {deleted} keys deleted")
        
        # Test 6: TTL check
        print("\n6️⃣ Testing TTL...")
        await redis_client.set("test:ttl", "value", ex=10)
        ttl = await redis_client.ttl("test:ttl")
        assert ttl > 0 and ttl <= 10
        print(f"   ✅ TTL check successful: {ttl} seconds remaining")
        
        # Cleanup
        print("\n🧹 Cleaning up test keys...")
        cleanup_keys = []
        async for key in redis_client.scan_iter(match="test:*"):
            cleanup_keys.append(key)
        
        if cleanup_keys:
            await redis_client.delete(*cleanup_keys)
            print(f"   ✅ Cleaned up {len(cleanup_keys)} test keys")
        
        await redis_client.close()
        
        print("\n" + "="*60)
        print("✅ All Redis tests passed!")
        print("="*60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Redis test failed: {e}")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_redis_operations())
    exit(0 if result else 1)
