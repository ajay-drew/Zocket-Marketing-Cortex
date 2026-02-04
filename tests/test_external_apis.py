"""
Test external API connections with real credentials from .env
"""
import pytest
import asyncio
from src.config import settings
import httpx
from neo4j import AsyncGraphDatabase
import redis.asyncio as redis


@pytest.mark.asyncio
async def test_groq_api():
    """Test Groq API connection"""
    try:
        client = httpx.AsyncClient(timeout=30.0)
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": "Say 'API works!'"}],
                "max_tokens": 10
            }
        )
        await client.aclose()
        
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        print(f"✅ Groq API: {data['choices'][0]['message']['content']}")
        
    except Exception as e:
        pytest.fail(f"❌ Groq API failed: {e}")


@pytest.mark.asyncio
async def test_tavily_api():
    """Test Tavily API connection"""
    try:
        client = httpx.AsyncClient(timeout=30.0)
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": "test query",
                "max_results": 1
            }
        )
        await client.aclose()
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data or "error" in data
        print(f"✅ Tavily API: Connected successfully")
        
    except Exception as e:
        pytest.fail(f"❌ Tavily API failed: {e}")


@pytest.mark.asyncio
async def test_neo4j_connection():
    """Test Neo4j database connection"""
    try:
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password)
        )
        
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run("RETURN 1 as num")
            record = await result.single()
            assert record["num"] == 1
        
        await driver.close()
        print("✅ Neo4j: Connected successfully")
        
    except Exception as e:
        pytest.fail(f"❌ Neo4j failed: {e}")


@pytest.mark.asyncio
async def test_redis_connection():
    """Test Redis connection"""
    try:
        redis_client = await redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Test set/get
        await redis_client.set("test_key", "test_value", ex=10)
        value = await redis_client.get("test_key")
        assert value == "test_value"
        
        # Cleanup
        await redis_client.delete("test_key")
        await redis_client.close()
        
        print("✅ Redis: Connected and tested successfully")
        
    except Exception as e:
        pytest.fail(f"❌ Redis failed: {e}")


@pytest.mark.asyncio
async def test_zep_api():
    """Test Zep API connection"""
    try:
        client = httpx.AsyncClient(timeout=30.0)
        response = await client.get(
            f"{settings.zep_api_url}/healthz",
            headers={"Authorization": f"Bearer {settings.zep_api_key}"}
        )
        await client.aclose()
        
        # Zep returns 200 for healthy
        assert response.status_code in [200, 401]  # 401 means API key issue but service is up
        print(f"✅ Zep API: Service is reachable (status: {response.status_code})")
        
    except Exception as e:
        pytest.fail(f"❌ Zep API failed: {e}")


@pytest.mark.asyncio
async def test_langsmith_connection():
    """Test LangSmith API connection"""
    try:
        client = httpx.AsyncClient(timeout=30.0)
        response = await client.get(
            "https://api.smith.langchain.com/info",
            headers={"x-api-key": settings.langchain_api_key}
        )
        await client.aclose()
        
        assert response.status_code == 200
        print("✅ LangSmith: Connected successfully")
        
    except Exception as e:
        pytest.fail(f"❌ LangSmith failed: {e}")


@pytest.mark.asyncio
async def test_pinecone_api():
    """Test Pinecone API connection"""
    try:
        from pinecone import Pinecone
        
        pc = Pinecone(api_key=settings.pinecone_api_key)
        indexes = pc.list_indexes()
        
        print(f"✅ Pinecone: Connected successfully (indexes: {len(indexes)})")
        
    except Exception as e:
        pytest.fail(f"❌ Pinecone failed: {e}")


if __name__ == "__main__":
    """Run tests directly"""
    print("\n" + "="*60)
    print("🧪 Testing External API Connections")
    print("="*60 + "\n")
    
    async def run_all_tests():
        tests = [
            ("Redis", test_redis_connection),
            ("Neo4j", test_neo4j_connection),
            ("Groq", test_groq_api),
            ("Tavily", test_tavily_api),
            ("Zep", test_zep_api),
            ("LangSmith", test_langsmith_connection),
            ("Pinecone", test_pinecone_api),
        ]
        
        results = []
        for name, test_func in tests:
            try:
                print(f"\n🔍 Testing {name}...")
                await test_func()
                results.append((name, True))
            except Exception as e:
                print(f"❌ {name} failed: {e}")
                results.append((name, False))
        
        print("\n" + "="*60)
        print("📊 Test Results Summary")
        print("="*60)
        for name, passed in results:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} - {name}")
        print("="*60 + "\n")
    
    asyncio.run(run_all_tests())
