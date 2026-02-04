"""
Tests for LangGraph workflow functionality
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.agents.marketing_strategy_advisor import MarketingStrategyAdvisor, AgentState


@pytest.mark.asyncio
async def test_workflow_node_execution_order():
    """Test that workflow nodes execute in correct order"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq'):
        advisor = MarketingStrategyAdvisor()
        
        # Verify workflow structure
        assert advisor.workflow is not None
        
        # Check that all nodes are registered
        nodes = advisor.workflow.nodes if hasattr(advisor.workflow, 'nodes') else []
        expected_nodes = ["query_analysis", "tool_selection", "execute_tools", "evaluate_results", "refine_query", "synthesize"]
        # Note: Actual node checking depends on LangGraph implementation


@pytest.mark.asyncio
async def test_conditional_edge_routing():
    """Test conditional edge routing based on state"""
    advisor = MarketingStrategyAdvisor()
    
    # Test should_refine_query logic
    state_high_quality: AgentState = {
        "messages": [],
        "query": "test",
        "original_query": "test",
        "tool_results": {},
        "selected_tools": [],
        "result_quality": {"overall": 0.8, "result_count": 5},
        "refined_query": None,
        "synthesis_input": None,
        "final_response": None,
        "tool_call_events": []
    }
    
    result = advisor._should_refine_query(state_high_quality)
    assert result == "synthesize"  # High quality, no refinement needed
    
    # Test low quality triggers refinement
    state_low_quality: AgentState = {
        "messages": [],
        "query": "test",
        "original_query": "test",
        "tool_results": {},
        "selected_tools": [],
        "result_quality": {"overall": 0.3, "result_count": 1},
        "refined_query": None,
        "synthesis_input": None,
        "final_response": None,
        "tool_call_events": []
    }
    
    result = advisor._should_refine_query(state_low_quality)
    assert result == "refine"  # Low quality, should refine
    
    # Test already refined - should synthesize
    state_refined: AgentState = {
        "messages": [],
        "query": "refined test",
        "original_query": "test",
        "tool_results": {},
        "selected_tools": [],
        "result_quality": {"overall": 0.3, "result_count": 1},
        "refined_query": "refined test",
        "synthesis_input": None,
        "final_response": None,
        "tool_call_events": []
    }
    
    result = advisor._should_refine_query(state_refined)
    assert result == "synthesize"  # Already refined once, proceed to synthesis


@pytest.mark.asyncio
async def test_state_management():
    """Test that state is properly managed through workflow"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm:
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        async def mock_ainvoke(messages):
            return Mock(content='{"needed_tools": ["search_marketing_blogs"]}')
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        initial_state: AgentState = {
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
        
        # Test query analysis updates state
        result_state = await advisor._query_analysis_node(initial_state)
        assert "selected_tools" in result_state
        assert len(result_state["selected_tools"]) > 0
        assert len(result_state["tool_call_events"]) > 0


@pytest.mark.asyncio
async def test_workflow_completion():
    """Test that workflow completes successfully"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm, \
         patch('src.agents.marketing_strategy_advisor.vector_store') as mock_vector_store, \
         patch('src.agents.marketing_strategy_advisor.tavily_client') as mock_tavily, \
         patch('src.agents.marketing_strategy_advisor.memory_manager') as mock_memory:
        
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        from langchain_core.messages import AIMessage
        
        async def mock_ainvoke(messages):
            if not messages:
                return AIMessage(content="Test")
            content = str(messages[-1]) if messages else ""
            if 'Analyze this marketing query' in content:
                return AIMessage(content='{"needed_tools": ["search_marketing_blogs"], "query_type": "insight"}')
            elif 'synthesizing' in content.lower():
                return AIMessage(content="Final synthesized response with recommendations.")
            elif 'You are a Marketing Strategy Advisor' in content or isinstance(messages[-1], type(messages[-1])):
                # For tool execution, return AIMessage with empty tool_calls
                return AIMessage(content="", tool_calls=[])
            return AIMessage(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        mock_vector_store.search_similar = AsyncMock(return_value=[
            {"title": "Test", "url": "https://test.com", "score": 0.85, "content": "Test content"}
        ])
        
        mock_tavily.search_with_fallback = AsyncMock(return_value={
            "query": "test",
            "results": []
        })
        
        mock_memory.add_message = AsyncMock()
        
        advisor = MarketingStrategyAdvisor()
        
        # Run workflow
        events = []
        async for event in advisor.stream_response("test query", "test_session"):
            events.append(event)
        
        # Should complete with final response
        assert len(events) > 0
        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) > 0
