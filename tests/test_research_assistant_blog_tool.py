"""
Unit tests for research assistant blog search tool
"""
import pytest
from unittest.mock import patch, AsyncMock
from src.agents.research_assistant import ResearchAssistant


@pytest.fixture
def research_assistant():
    """Create a ResearchAssistant instance for testing"""
    with patch('src.agents.research_assistant.ChatGroq'), \
         patch('src.agents.research_assistant.settings') as mock_settings:
        mock_settings.groq_api_key = "test-key"
        mock_settings.groq_model = "test-model"
        
        assistant = ResearchAssistant()
        return assistant


@pytest.mark.asyncio
async def test_blog_search_async_with_results(research_assistant):
    """Test _blog_search_async with results"""
    with patch('src.agents.research_assistant.vector_store.search_similar', new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [
            {
                "title": "Test Blog Post",
                "url": "https://example.com/post",
                "score": 0.85,
                "content": "This is test content from a blog post",
                "metadata": {"blog_name": "Test Blog"}
            }
        ]
        
        result = await research_assistant._blog_search_async("test query")
        
        assert "Test Blog Post" in result
        assert "Test Blog" in result
        assert "https://example.com/post" in result
        assert "0.85" in result


@pytest.mark.asyncio
async def test_blog_search_async_no_results(research_assistant):
    """Test _blog_search_async with no results"""
    with patch('src.agents.research_assistant.vector_store.search_similar', new_callable=AsyncMock) as mock_search:
        mock_search.return_value = []
        
        result = await research_assistant._blog_search_async("test query")
        
        assert "No relevant blog posts found" in result


@pytest.mark.asyncio
async def test_blog_search_tool_in_tools_list(research_assistant):
    """Test that search_marketing_blogs tool is in tools list"""
    tool_names = [tool.name for tool in research_assistant.tools]
    assert "search_marketing_blogs" in tool_names


@pytest.mark.asyncio
async def test_blog_search_filters_by_content_type(research_assistant):
    """Test that blog search filters by content_type=blog_post"""
    with patch('src.agents.research_assistant.vector_store.search_similar', new_callable=AsyncMock) as mock_search:
        mock_search.return_value = []
        
        await research_assistant._blog_search_async("test query")
        
        # Verify search was called with correct filter
        call_args = mock_search.call_args
        assert call_args is not None
        filter_metadata = call_args[1].get("filter_metadata", {})
        assert filter_metadata.get("content_type") == "blog_post"
