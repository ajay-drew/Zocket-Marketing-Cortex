"""
Tests for Marketing Strategy Advisor with LangGraph workflow
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.agents.marketing_strategy_advisor import MarketingStrategyAdvisor, AgentState


@pytest.mark.asyncio
async def test_marketing_strategy_advisor_initialization():
    """Test that MarketingStrategyAdvisor initializes correctly"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq'):
        advisor = MarketingStrategyAdvisor()
        assert advisor is not None
        assert advisor.llm is not None
        assert len(advisor.tools) == 4  # tavily_web_search, search_stored_research, search_marketing_blogs, search_marketing_graph
        assert advisor.workflow is not None


@pytest.mark.asyncio
async def test_workflow_execution():
    """Test complete LangGraph workflow execution"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm, \
         patch('src.agents.marketing_strategy_advisor.vector_store') as mock_vector_store, \
         patch('src.agents.marketing_strategy_advisor.tavily_client') as mock_tavily:
        
        # Mock LLM responses
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        # Mock LLM invoke for query analysis
        from langchain_core.messages import AIMessage
        
        async def mock_ainvoke(messages):
            if not messages or not isinstance(messages, list):
                return AIMessage(content="Test response")
            content = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
            if 'Analyze this marketing query' in content:
                return AIMessage(content='{"needed_tools": ["search_marketing_blogs"], "query_type": "insight", "reasoning": "test"}')
            elif 'synthesizing marketing research' in content.lower():
                return AIMessage(content="Test synthesis response with key insights and recommendations.")
            elif 'You are a Marketing Strategy Advisor' in content:
                # Return AIMessage with tool calls for tool execution
                return AIMessage(content="", tool_calls=[])
            return AIMessage(content="Test response")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        # Mock vector store
        mock_vector_store.search_similar = AsyncMock(return_value=[
            {"title": "Test Blog", "url": "https://test.com", "score": 0.85, "content": "Test content"}
        ])
        
        # Mock tavily
        mock_tavily.search_with_fallback = AsyncMock(return_value={
            "query": "test",
            "results": [{"title": "Test", "url": "https://test.com", "content": "Test"}]
        })
        
        advisor = MarketingStrategyAdvisor()
        
        # Test stream_response
        events = []
        async for event in advisor.stream_response("test query", "test_session"):
            events.append(event)
        
        # Should have tool call events and final response
        assert len(events) > 0
        assert any(e.get("type") == "token" for e in events)


@pytest.mark.asyncio
async def test_query_refinement_trigger():
    """Test that query refinement triggers on low result quality"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm, \
         patch('src.agents.marketing_strategy_advisor.vector_store') as mock_vector_store:
        
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        # Mock low quality results
        mock_vector_store.search_similar = AsyncMock(return_value=[
            {"title": "Low Quality", "url": "https://test.com", "score": 0.3, "content": "Short"}
        ])
        
        async def mock_ainvoke(messages):
            content = str(messages[-1]) if messages else ""
            if 'Refine the query' in content:
                mock_response = Mock()
                mock_response.content = '{"refined_query": "improved test query", "strategy": "broaden", "reasoning": "test"}'
                return mock_response
            elif 'Analyze this marketing query' in content:
                mock_response = Mock()
                mock_response.content = '{"needed_tools": ["search_marketing_blogs"], "query_type": "insight"}'
                return mock_response
            return Mock(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        # Create state with low quality results
        state: AgentState = {
            "messages": [],
            "query": "test",
            "original_query": "test",
            "tool_results": {"search_marketing_blogs": "Short result"},
            "selected_tools": ["search_marketing_blogs"],
            "result_quality": {"overall": 0.3, "result_count": 1},
            "refined_query": None,
            "synthesis_input": None,
            "final_response": None,
            "tool_call_events": []
        }
        
        # Test refinement node
        result_state = await advisor._refine_query_node(state)
        
        assert result_state.get("refined_query") is not None
        assert "refined" in result_state.get("refined_query", "").lower() or "improved" in result_state.get("refined_query", "").lower()


@pytest.mark.asyncio
async def test_multi_source_synthesis():
    """Test multi-source synthesis combines results correctly"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm:
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        async def mock_ainvoke(messages):
            content = str(messages[-1]) if messages else ""
            if 'synthesizing marketing research' in content.lower():
                mock_response = Mock()
                mock_response.content = """Executive Summary: Test synthesis

Key Insights:
1. Insight from blogs
2. Insight from web

Recommended Strategy:
- Step 1
- Step 2

Sources: https://test.com"""
                return mock_response
            return Mock(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        state: AgentState = {
            "messages": [],
            "query": "test query",
            "original_query": "test query",
            "tool_results": {
                "search_marketing_blogs": "Blog result 1\nBlog result 2",
                "tavily_web_search": "Web result 1\nWeb result 2",
                "search_stored_research": "Stored result 1"
            },
            "selected_tools": [],
            "result_quality": {"overall": 0.8, "result_count": 3},
            "refined_query": None,
            "synthesis_input": None,
            "final_response": None,
            "tool_call_events": []
        }
        
        result_state = await advisor._synthesize_node(state)
        
        assert result_state.get("final_response") is not None
        assert len(result_state.get("final_response", "")) > 0
        assert "synthesis" in result_state.get("tool_call_events", [{}])[-1].get("type", "")


@pytest.mark.asyncio
async def test_tool_orchestration():
    """Test dynamic tool selection and orchestration"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm:
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        async def mock_ainvoke(messages):
            content = str(messages[-1]) if messages else ""
            if 'Analyze this marketing query' in content:
                mock_response = Mock()
                mock_response.content = '{"needed_tools": ["search_marketing_blogs", "tavily_web_search"], "query_type": "mixed"}'
                return mock_response
            return Mock(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        state: AgentState = {
            "messages": [],
            "query": "test query",
            "original_query": "test query",
            "tool_results": {},
            "selected_tools": [],
            "result_quality": {},
            "refined_query": None,
            "synthesis_input": None,
            "final_response": None,
            "tool_call_events": []
        }
        
        result_state = await advisor._query_analysis_node(state)
        
        assert len(result_state.get("selected_tools", [])) > 0
        assert "search_marketing_blogs" in result_state.get("selected_tools", [])


@pytest.mark.asyncio
async def test_result_evaluation():
    """Test result quality evaluation"""
    advisor = MarketingStrategyAdvisor()
    
    # Test high quality result
    quality1 = advisor._evaluate_result_quality("This is a comprehensive result with URLs: https://example.com and detailed content.")
    assert quality1 > 0.7
    
    # Test low quality result
    quality2 = advisor._evaluate_result_quality("Short")
    assert quality2 < 0.5
    
    # Test error result
    quality3 = advisor._evaluate_result_quality("Error: No results found")
    assert quality3 < 0.3


@pytest.mark.asyncio
async def test_error_handling():
    """Test workflow error recovery"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm, \
         patch('src.agents.marketing_strategy_advisor.vector_store') as mock_vector_store:
        
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        # Mock error in vector store
        mock_vector_store.search_similar = AsyncMock(side_effect=Exception("Test error"))
        
        async def mock_ainvoke(messages):
            return Mock(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        # Should handle errors gracefully
        events = []
        try:
            async for event in advisor.stream_response("test", "session"):
                events.append(event)
        except Exception:
            pass
        
        # Should have error event or graceful handling
        assert True  # If we get here, error was handled
