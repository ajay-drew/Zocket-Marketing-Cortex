"""
Tests for blog ingestion functionality
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

# Try to import BlogIngestionClient, skip tests if dependencies not available
try:
    from src.integrations.blog_ingestion import BlogIngestionClient
    BLOG_INGESTION_AVAILABLE = True
except ImportError:
    BLOG_INGESTION_AVAILABLE = False
    BlogIngestionClient = None

from src.knowledge.vector_store import vector_store

pytestmark = pytest.mark.skipif(
    not BLOG_INGESTION_AVAILABLE,
    reason="Blog ingestion dependencies not available (feedparser, readability-lxml, etc.)"
)


@pytest.fixture
def blog_client():
    """Create a BlogIngestionClient instance for testing"""
    return BlogIngestionClient()


@pytest.fixture
def sample_rss_feed():
    """Sample RSS feed XML"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Test Blog</title>
        <link>https://example.com</link>
        <description>Test blog description</description>
        <item>
            <title>Test Post 1</title>
            <link>https://example.com/post1</link>
            <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
            <description>Test post description</description>
        </item>
        <item>
            <title>Test Post 2</title>
            <link>https://example.com/post2</link>
            <pubDate>Tue, 02 Jan 2024 00:00:00 GMT</pubDate>
            <description>Another test post</description>
        </item>
    </channel>
</rss>"""


@pytest.fixture
def sample_html():
    """Sample HTML content for article extraction"""
    return """
    <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Test Article Title</h1>
                <p>This is a test article with some content. It has multiple paragraphs.</p>
                <p>Here is another paragraph with more content to test the extraction.</p>
                <p>And one more paragraph to ensure we have enough content for chunking.</p>
            </article>
        </body>
    </html>
    """


@pytest.mark.asyncio
async def test_fetch_rss_feed(blog_client, sample_rss_feed):
    """Test RSS feed fetching and parsing"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.text = sample_rss_feed
        mock_response.raise_for_status = Mock()
        mock_response.headers = {'Content-Type': 'application/xml'}  # Proper RSS feed content type
        
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        entries = await blog_client.fetch_rss_feed("https://example.com/feed.xml")
        
        assert len(entries) == 2
        assert entries[0]["title"] == "Test Post 1"
        assert entries[0]["link"] == "https://example.com/post1"
        assert entries[1]["title"] == "Test Post 2"


@pytest.mark.asyncio
async def test_extract_article_content(blog_client, sample_html):
    """Test article content extraction"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.text = sample_html
        mock_response.raise_for_status = Mock()
        
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        result = await blog_client.extract_article_content("https://example.com/article")
        
        assert result is not None
        assert "title" in result
        assert "content" in result
        assert len(result["content"]) > 100  # Should have extracted content


def test_chunk_content(blog_client):
    """Test content chunking"""
    content = "This is a test article. " * 100  # Create long content
    metadata = {
        "blog_name": "Test Blog",
        "url": "https://example.com/post",
        "title": "Test Post"
    }
    
    chunks = blog_client.chunk_content(content, metadata)
    
    assert len(chunks) > 0
    assert all("text" in chunk for chunk in chunks)
    assert all("blog_name" in chunk for chunk in chunks)
    assert all("url" in chunk for chunk in chunks)
    assert all("chunk_index" in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_check_duplicate(blog_client):
    """Test duplicate detection"""
    url = "https://example.com/post"
    
    # Mock vector_store.search_similar to return empty (no duplicate)
    with patch.object(vector_store, 'search_similar', new_callable=AsyncMock) as mock_search:
        mock_search.return_value = []
        result = await blog_client.check_duplicate(url)
        assert result is False
        
        # Mock with duplicate found
        mock_search.return_value = [{"url": url}]
        result = await blog_client.check_duplicate(url)
        assert result is True


@pytest.mark.asyncio
async def test_ingest_blog_success(blog_client):
    """Test successful blog ingestion"""
    # Mock all dependencies
    with patch.object(blog_client, 'fetch_rss_feed', new_callable=AsyncMock) as mock_fetch, \
         patch.object(blog_client, 'check_duplicate', new_callable=AsyncMock) as mock_duplicate, \
         patch.object(blog_client, 'extract_article_content', new_callable=AsyncMock) as mock_extract, \
         patch.object(blog_client, 'chunk_content') as mock_chunk, \
         patch.object(vector_store, 'upsert_blog_content', new_callable=AsyncMock) as mock_upsert:
        
        # Setup mocks
        mock_fetch.return_value = [
            {
                "title": "Test Post",
                "link": "https://example.com/post",
                "published": "2024-01-01",
                "summary": "Test summary",
                "author": "Test Author"
            }
        ]
        mock_duplicate.return_value = False
        mock_extract.return_value = {
            "title": "Test Post",
            "content": "This is test content. " * 50
        }
        mock_chunk.return_value = [
            {
                "text": "This is test content.",
                "chunk_index": 0,
                "total_chunks": 1
            }
        ]
        mock_upsert.return_value = 1
        
        result = await blog_client.ingest_blog(
            blog_name="Test Blog",
            feed_url="https://example.com/feed.xml",
            max_posts=1
        )
        
        assert result["status"] == "success"
        assert result["posts_ingested"] == 1
        assert result["chunks_created"] == 1
        assert result["errors"] == 0


@pytest.mark.asyncio
async def test_ingest_blog_with_duplicates(blog_client):
    """Test blog ingestion with duplicate detection"""
    with patch.object(blog_client, 'fetch_rss_feed', new_callable=AsyncMock) as mock_fetch, \
         patch.object(blog_client, 'check_duplicate', new_callable=AsyncMock) as mock_duplicate:
        
        mock_fetch.return_value = [
            {
                "title": "Test Post",
                "link": "https://example.com/post",
                "published": "2024-01-01",
                "summary": "Test",
                "author": "Author"
            }
        ]
        mock_duplicate.return_value = True  # Duplicate found
        
        result = await blog_client.ingest_blog(
            blog_name="Test Blog",
            feed_url="https://example.com/feed.xml",
            max_posts=1
        )
        
        # Should skip duplicate, so no posts ingested
        assert result["posts_ingested"] == 0


@pytest.mark.asyncio
async def test_ingest_blog_with_extraction_failure(blog_client):
    """Test blog ingestion when content extraction fails"""
    with patch.object(blog_client, 'fetch_rss_feed', new_callable=AsyncMock) as mock_fetch, \
         patch.object(blog_client, 'check_duplicate', new_callable=AsyncMock) as mock_duplicate, \
         patch.object(blog_client, 'extract_article_content', new_callable=AsyncMock) as mock_extract:
        
        mock_fetch.return_value = [
            {
                "title": "Test Post",
                "link": "https://example.com/post",
                "published": "2024-01-01",
                "summary": "Test",
                "author": "Author"
            }
        ]
        mock_duplicate.return_value = False
        mock_extract.return_value = None  # Extraction failed
        
        result = await blog_client.ingest_blog(
            blog_name="Test Blog",
            feed_url="https://example.com/feed.xml",
            max_posts=1
        )
        
        # Should have error but continue
        assert result["errors"] == 1
        assert result["posts_ingested"] == 0


def test_chunk_content_metadata_preservation(blog_client):
    """Test that chunking preserves metadata correctly"""
    content = "Short content for testing."
    metadata = {
        "blog_name": "Test Blog",
        "url": "https://example.com/post",
        "title": "Test Post",
        "custom_field": "custom_value"
    }
    
    chunks = blog_client.chunk_content(content, metadata)
    
    # All chunks should have the metadata
    for chunk in chunks:
        assert chunk["blog_name"] == "Test Blog"
        assert chunk["url"] == "https://example.com/post"
        assert chunk["title"] == "Test Post"
        assert chunk["custom_field"] == "custom_value"


@pytest.mark.asyncio
async def test_ingest_blog_empty_feed(blog_client):
    """Test ingestion with empty RSS feed"""
    with patch.object(blog_client, 'fetch_rss_feed', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = []
        
        result = await blog_client.ingest_blog(
            blog_name="Test Blog",
            feed_url="https://example.com/feed.xml",
            max_posts=10
        )
        
        assert result["status"] == "error"
        assert result["posts_ingested"] == 0
        assert "No entries" in result.get("message", "")
