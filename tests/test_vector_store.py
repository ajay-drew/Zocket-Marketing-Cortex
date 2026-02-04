"""
Tests for Pinecone vector store
"""
import pytest
from src.knowledge.vector_store import vector_store


@pytest.mark.asyncio
async def test_embed_text():
    """Test text embedding generation"""
    text = "Test query for embedding"
    embedding = vector_store.embed_text(text)
    
    assert embedding is not None
    assert len(embedding) == 1024  # Dimension for multilingual-e5-large
    assert all(isinstance(x, float) for x in embedding)


@pytest.mark.asyncio
async def test_upsert_research():
    """Test storing research results"""
    query = "test research query"
    research_results = [
        {
            "title": "Test Article 1",
            "url": "https://example.com/article1",
            "content": "This is test content for article 1",
            "score": 0.95
        },
        {
            "title": "Test Article 2",
            "url": "https://example.com/article2",
            "content": "This is test content for article 2",
            "score": 0.90
        }
    ]
    
    count = await vector_store.upsert_research(
        query=query,
        research_results=research_results,
        metadata={"test": True}
    )
    
    assert count == 2


@pytest.mark.asyncio
async def test_search_similar():
    """Test semantic search"""
    # First, upsert some research
    query = "marketing trends 2024"
    research_results = [
        {
            "title": "Marketing Trends 2024",
            "url": "https://example.com/trends",
            "content": "Digital marketing trends for 2024 include AI, personalization, and video content",
            "score": 0.95
        }
    ]
    
    await vector_store.upsert_research(query, research_results)
    
    # Search for similar content
    results = await vector_store.search_similar(
        query="What are the latest marketing trends?",
        top_k=5
    )
    
    assert isinstance(results, list)
    # Results may be empty if index is new, which is fine


@pytest.mark.asyncio
async def test_get_stats():
    """Test getting index statistics"""
    stats = vector_store.get_stats()
    
    assert isinstance(stats, dict)
    assert "total_vectors" in stats or "dimension" in stats
