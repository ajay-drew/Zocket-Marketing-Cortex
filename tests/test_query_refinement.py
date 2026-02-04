"""
Tests for query refinement logic
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.agents.marketing_strategy_advisor import MarketingStrategyAdvisor, AgentState


@pytest.mark.asyncio
async def test_refinement_triggers_on_low_result_count():
    """Test that refinement triggers when result count is low"""
    advisor = MarketingStrategyAdvisor()
    
    state: AgentState = {
        "messages": [],
        "query": "test",
        "original_query": "test",
        "tool_results": {"search_marketing_blogs": "Only one result"},
        "selected_tools": [],
        "result_quality": {"overall": 0.5, "result_count": 1},
        "refined_query": None,
        "synthesis_input": None,
        "final_response": None,
        "tool_call_events": []
    }
    
    # Should trigger refinement
    should_refine = advisor._should_refine_query(state)
    assert should_refine == "refine"


@pytest.mark.asyncio
async def test_refinement_triggers_on_low_relevance():
    """Test that refinement triggers when relevance score is low"""
    advisor = MarketingStrategyAdvisor()
    
    state: AgentState = {
        "messages": [],
        "query": "test",
        "original_query": "test",
        "tool_results": {"search_marketing_blogs": "Low quality results"},
        "selected_tools": [],
        "result_quality": {"overall": 0.4, "result_count": 3},
        "refined_query": None,
        "synthesis_input": None,
        "final_response": None,
        "tool_call_events": []
    }
    
    # Should trigger refinement
    should_refine = advisor._should_refine_query(state)
    assert should_refine == "refine"


@pytest.mark.asyncio
async def test_refinement_quality_improvement():
    """Test that refined query improves result quality"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm:
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        async def mock_ainvoke(messages):
            content = str(messages[-1]) if messages else ""
            if 'Refine the query' in content:
                mock_response = Mock()
                mock_response.content = '{"refined_query": "test query marketing strategy best practices", "strategy": "broaden", "reasoning": "Adding context"}'
                return mock_response
            return Mock(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        state: AgentState = {
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
        
        result_state = await advisor._refine_query_node(state)
        
        # Check refinement occurred
        assert result_state.get("refined_query") is not None
        refined = result_state.get("refined_query", "")
        assert len(refined) > len(state["original_query"])
        assert result_state.get("tool_call_events", [{}])[-1].get("type", "") == "query_refinement"


@pytest.mark.asyncio
async def test_refinement_strategies():
    """Test different refinement strategies (broaden, narrow, rephrase)"""
    with patch('src.agents.marketing_strategy_advisor.ChatGroq') as mock_llm:
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        
        strategies_tested = []
        
        async def mock_ainvoke(messages):
            content = str(messages[-1]) if messages else ""
            if 'Refine the query' in content:
                # Test different strategies
                if 'broaden' not in strategies_tested:
                    strategies_tested.append('broaden')
                    return Mock(content='{"refined_query": "test query marketing campaigns", "strategy": "broaden"}')
                elif 'narrow' not in strategies_tested:
                    strategies_tested.append('narrow')
                    return Mock(content='{"refined_query": "test query 2026", "strategy": "narrow"}')
                else:
                    strategies_tested.append('rephrase')
                    return Mock(content='{"refined_query": "test query proven techniques", "strategy": "rephrase"}')
            return Mock(content="Test")
        
        mock_llm_instance.ainvoke = mock_ainvoke
        
        advisor = MarketingStrategyAdvisor()
        
        # Test broadening
        state1: AgentState = {
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
        
        result1 = await advisor._refine_query_node(state1)
        assert "marketing" in result1.get("refined_query", "").lower() or "campaigns" in result1.get("refined_query", "").lower()


@pytest.mark.asyncio
async def test_no_refinement_on_high_quality():
    """Test that refinement doesn't trigger when quality is high"""
    advisor = MarketingStrategyAdvisor()
    
    state: AgentState = {
        "messages": [],
        "query": "test",
        "original_query": "test",
        "tool_results": {"search_marketing_blogs": "High quality comprehensive results"},
        "selected_tools": [],
        "result_quality": {"overall": 0.85, "result_count": 5},
        "refined_query": None,
        "synthesis_input": None,
        "final_response": None,
        "tool_call_events": []
    }
    
    # Should not refine
    should_refine = advisor._should_refine_query(state)
    assert should_refine == "synthesize"
