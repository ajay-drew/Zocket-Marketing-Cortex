"""
Tests for API endpoints
"""
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Marketing Cortex"
        assert data["status"] == "running"
        assert "version" in data


@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "services" in data
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_run_agent_endpoint():
    """Test run-agent endpoint"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "query": "What are my top performing campaigns?",
            "session_id": "test_session_001"
        }
        response = await client.post("/api/run-agent", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "agent_used" in data
        assert "session_id" in data
        assert data["session_id"] == "test_session_001"
