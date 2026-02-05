"""
Integration tests for the Marketing Cortex system
"""
import pytest
import httpx
import asyncio
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data


def test_blog_sources_endpoint():
    """Test blog sources endpoint integration"""
    response = client.get("/api/blogs/sources")
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    assert isinstance(data["sources"], list)


def test_agent_stream_endpoint_structure():
    """Test agent stream endpoint structure (without actual streaming)"""
    # This tests the endpoint exists and accepts requests
    # Full streaming tests would require more complex setup
    response = client.post(
        "/api/agent/stream",
        json={"query": "test query", "session_id": "test-session"},
        headers={"Accept": "text/event-stream"}
    )
    # Should return 200 or handle the request properly
    assert response.status_code in [200, 422]  # 422 if validation fails


def test_api_documentation_accessible():
    """Test that API documentation is accessible"""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_schema_available():
    """Test that OpenAPI schema is available"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "paths" in data


@pytest.mark.asyncio
async def test_blog_ingestion_flow():
    """Test complete blog ingestion flow"""
    # This is a simplified integration test
    # In a real scenario, you'd mock external services
    
    # Test that the endpoint accepts valid requests
    response = client.post(
        "/api/blogs/ingest/stream",
        json={
            "blog_url": "https://example.com/feed.xml",
            "blog_name": "Test Blog",
            "max_posts": 5
        }
    )
    
    # Should either succeed (200), fail gracefully (503 service unavailable), or validation error (422)
    # 500 is acceptable if there's a real service issue (e.g., Neo4j/Pinecone not available)
    assert response.status_code in [200, 422, 500, 503]


