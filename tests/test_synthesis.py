"""
Tests for multi-source synthesis functionality
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.agents.marketing_strategy_advisor import MarketingStrategyAdvisor, AgentState


@pytest.mark.asyncio
async def test_multiple_source_combination():
    """Test that synthesis combines results from multiple sources"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm:
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        synthesis_called = False
        
        async def mock_ainvoke(messages):
            nonlocal synthesis_called
            content = str(messages[-1]) if messages else ""
            if 'synthesizing marketing research' in content.lower():
                synthesis_called = True
                # Verify all sources are present
                assert 'blog' in content.lower() or 'Blog' in content
                assert 'web' in content.lower() or 'Web' in content
                assert 'stored' in content.lower() or 'Stored' in content
                
                mock_response = Mock()
                mock_response.content = """Executive Summary: Combined insights from multiple sources.

Key Insights:
1. Blog insight: Content marketing best practices
2. Web insight: Current market trends
3. Stored insight: Past research findings

Recommended Strategy:
- Implement content marketing
- Monitor market trends
- Apply past learnings

Sources: https://blog.com, https://web.com"""
                return mock_response
            return Mock(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        state: AgentState = {
            "messages": [],
            "query": "test query",
            "original_query": "test query",
            "tool_results": {
                "search_marketing_blogs": "Blog result: Content marketing is key",
                "tavily_web_search": "Web result: Market trends show growth",
                "search_stored_research": "Stored result: Past research indicates success"
            },
            "selected_tools": [],
            "result_quality": {"overall": 0.8, "result_count": 3},
            "refined_query": None,
            "synthesis_input": None,
            "final_response": None,
            "tool_call_events": []
        }
        
        result_state = await advisor._synthesize_node(state)
        
        assert synthesis_called
        assert result_state.get("final_response") is not None
        assert len(result_state.get("final_response", "")) > 100


@pytest.mark.asyncio
async def test_contradiction_resolution():
    """Test that synthesis resolves contradictions between sources"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm:
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        async def mock_ainvoke(messages):
            content = str(messages[-1]) if messages else ""
            if 'synthesizing marketing research' in content.lower():
                # Should acknowledge and resolve contradictions
                mock_response = Mock()
                mock_response.content = """Executive Summary: Resolved contradictions between sources.

Key Insights:
1. Blog says: Use long-form content (HubSpot)
2. Web says: Short-form content performs better (Recent study)
3. Resolution: Use long-form for authority, short-form for engagement

Recommended Strategy:
- Combine both approaches based on audience
- Test A/B variations

Sources: https://blog.com, https://web.com"""
                return mock_response
            return Mock(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        state: AgentState = {
            "messages": [],
            "query": "content strategy",
            "original_query": "content strategy",
            "tool_results": {
                "search_marketing_blogs": "HubSpot says: Use long-form content for SEO",
                "tavily_web_search": "Recent study: Short-form content has 3x engagement"
            },
            "selected_tools": [],
            "result_quality": {"overall": 0.8, "result_count": 2},
            "refined_query": None,
            "synthesis_input": None,
            "final_response": None,
            "tool_call_events": []
        }
        
        result_state = await advisor._synthesize_node(state)
        
        response = result_state.get("final_response", "")
        # Should mention both perspectives and resolution
        assert "long-form" in response.lower() or "short-form" in response.lower()
        assert "resolution" in response.lower() or "combine" in response.lower() or "both" in response.lower()


@pytest.mark.asyncio
async def test_citation_accuracy():
    """Test that synthesis includes accurate citations"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm:
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        async def mock_ainvoke(messages):
            content = str(messages[-1]) if messages else ""
            if 'synthesizing marketing research' in content.lower():
                mock_response = Mock()
                mock_response.content = """Key Insights:
1. Insight from blogs (Source: https://blog.hubspot.com/article1)
2. Insight from web (Source: https://web.com/article2)
3. Insight from stored (Source: https://stored.com/article3)

Sources:
- https://blog.hubspot.com/article1
- https://web.com/article2
- https://stored.com/article3"""
                return mock_response
            return Mock(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        state: AgentState = {
            "messages": [],
            "query": "test",
            "original_query": "test",
            "tool_results": {
                "search_marketing_blogs": "Result with URL: https://blog.hubspot.com/article1",
                "tavily_web_search": "Result with URL: https://web.com/article2",
                "search_stored_research": "Result with URL: https://stored.com/article3"
            },
            "selected_tools": [],
            "result_quality": {"overall": 0.8, "result_count": 3},
            "refined_query": None,
            "synthesis_input": None,
            "final_response": None,
            "tool_call_events": []
        }
        
        result_state = await advisor._synthesize_node(state)
        
        response = result_state.get("final_response", "")
        # Should contain URLs
        assert "http" in response or "https" in response
        assert "source" in response.lower() or "sources" in response.lower()


@pytest.mark.asyncio
async def test_strategy_coherence():
    """Test that synthesized strategy is coherent and actionable"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm:
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        async def mock_ainvoke(messages):
            content = str(messages[-1]) if messages else ""
            if 'synthesizing marketing research' in content.lower():
                mock_response = Mock()
                mock_response.content = """Executive Summary: Coherent strategy based on multiple sources.

Key Insights:
1. Content marketing drives engagement
2. SEO optimization increases visibility
3. Social media amplifies reach

Recommended Strategy:
1. Create high-quality content (weekly)
2. Optimize for SEO keywords
3. Share on social platforms
4. Measure and iterate

This strategy combines insights from all sources into actionable steps."""
                return mock_response
            return Mock(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        state: AgentState = {
            "messages": [],
            "query": "marketing strategy",
            "original_query": "marketing strategy",
            "tool_results": {
                "search_marketing_blogs": "Content marketing insights",
                "tavily_web_search": "SEO best practices",
                "search_stored_research": "Social media strategies"
            },
            "selected_tools": [],
            "result_quality": {"overall": 0.8, "result_count": 3},
            "refined_query": None,
            "synthesis_input": None,
            "final_response": None,
            "tool_call_events": []
        }
        
        result_state = await advisor._synthesize_node(state)
        
        response = result_state.get("final_response", "")
        # Should have structure
        assert "summary" in response.lower() or "executive" in response.lower()
        assert "insight" in response.lower() or "key" in response.lower()
        assert "strategy" in response.lower() or "recommend" in response.lower()
        assert "step" in response.lower() or "action" in response.lower()
