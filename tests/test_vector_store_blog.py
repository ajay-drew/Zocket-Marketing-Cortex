"""
Unit tests for vector store blog-specific methods
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.knowledge.vector_store import VectorStore


@pytest.fixture
def vector_store():
    """Create a VectorStore instance for testing"""
    with patch('src.knowledge.vector_store.Pinecone') as mock_pinecone, \
         patch('src.knowledge.vector_store.settings') as mock_settings:
        mock_settings.pinecone_api_key = "test-key"
        mock_settings.pinecone_index_name = "test-index"
        
        mock_pc = Mock()
        mock_index = Mock()
        mock_pc.list_indexes.return_value = []
        mock_pc.create_index.return_value = None
        mock_pc.Index.return_value = mock_index
        mock_pinecone.return_value = mock_pc
        
        store = VectorStore()
        store.index = mock_index
        return store


@pytest.mark.asyncio
async def test_check_duplicate_found(vector_store):
    """Test check_duplicate when duplicate exists"""
    url = "https://example.com/post"
    
    with patch.object(vector_store, 'search_similar', new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [
            {"url": url, "score": 0.9}
        ]
        
        result = await vector_store.check_duplicate(url)
        assert result is True


@pytest.mark.asyncio
async def test_check_duplicate_not_found(vector_store):
    """Test check_duplicate when no duplicate exists"""
    url = "https://example.com/post"
    
    with patch.object(vector_store, 'search_similar', new_callable=AsyncMock) as mock_search:
        mock_search.return_value = []
        
        result = await vector_store.check_duplicate(url)
        assert result is False


@pytest.mark.asyncio
async def test_upsert_blog_content(vector_store):
    """Test upsert_blog_content"""
    chunks = [
        {
            "text": "This is chunk 1",
            "chunk_index": 0,
            "blog_name": "Test Blog",
            "url": "https://example.com/post",
            "title": "Test Post"
        },
        {
            "text": "This is chunk 2",
            "chunk_index": 1,
            "blog_name": "Test Blog",
            "url": "https://example.com/post",
            "title": "Test Post"
        }
    ]
    
    with patch.object(vector_store, 'embed_text') as mock_embed:
        mock_embed.return_value = [0.1] * 1024  # Mock embedding
        
        result = await vector_store.upsert_blog_content(chunks)
        
        assert result == 2
        assert vector_store.index.upsert.called


@pytest.mark.asyncio
async def test_get_blog_stats(vector_store):
    """Test get_blog_stats"""
    with patch.object(vector_store, 'get_stats') as mock_stats, \
         patch.object(vector_store, 'search_similar', new_callable=AsyncMock) as mock_search:
        
        mock_stats.return_value = {"total_vectors": 100}
        mock_search.return_value = [{"url": "test"}] * 5
        
        result = await vector_store.get_blog_stats("Test Blog")
        
        assert "total_vectors" in result
        assert result["blog_name"] == "Test Blog"


@pytest.mark.asyncio
async def test_upsert_blog_content_empty_chunks(vector_store):
    """Test upsert_blog_content with empty chunks"""
    result = await vector_store.upsert_blog_content([])
    assert result == 0
