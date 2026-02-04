"""
Tests for Graph RAG integration
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.knowledge.graph_schema import graph_schema
from src.knowledge.entity_extractor import EntityExtractor


@pytest.mark.asyncio
async def test_create_marketing_entity():
    """Test creating a marketing entity in Neo4j"""
    with patch.object(graph_schema.driver, 'session') as mock_session:
        mock_session.return_value.__aenter__.return_value.run = AsyncMock()
        mock_session.return_value.__aenter__.return_value.run.return_value.single = AsyncMock(
            return_value=MagicMock()
        )
        mock_session.return_value.__aenter__.return_value.run.return_value.single.return_value = {
            "e": {
                "id": "test_entity_1",
                "name": "Meta Ads",
                "entity_type": "AdPlatform",
                "confidence": 0.95
            }
        }
        
        result = await graph_schema.create_marketing_entity(
            entity_id="test_entity_1",
            name="Meta Ads",
            entity_type="AdPlatform",
            confidence=0.95
        )
        
        assert result is not None
        assert result.get("name") == "Meta Ads"


@pytest.mark.asyncio
async def test_create_entity_relationship():
    """Test creating a relationship between entities"""
    with patch.object(graph_schema.driver, 'session') as mock_session:
        mock_session.return_value.__aenter__.return_value.run = AsyncMock()
        mock_session.return_value.__aenter__.return_value.run.return_value.single = AsyncMock(
            return_value=MagicMock()
        )
        mock_session.return_value.__aenter__.return_value.run.return_value.single.return_value = {
            "r": {"type": "OPTIMIZES_FOR"}
        }
        
        result = await graph_schema.create_entity_relationship(
            source_entity_id="entity_1",
            target_entity_id="entity_2",
            relationship_type="OPTIMIZES_FOR",
            confidence=0.90
        )
        
        assert result is True


@pytest.mark.asyncio
async def test_link_entity_to_blog():
    """Test linking an entity to a blog post"""
    with patch.object(graph_schema.driver, 'session') as mock_session:
        mock_session.return_value.__aenter__.return_value.run = AsyncMock()
        mock_session.return_value.__aenter__.return_value.run.return_value.single = AsyncMock(
            return_value=MagicMock()
        )
        mock_session.return_value.__aenter__.return_value.run.return_value.single.return_value = {
            "r": {"type": "MENTIONED_IN"}
        }
        
        result = await graph_schema.link_entity_to_blog(
            entity_id="entity_1",
            chunk_id="chunk_1",
            url="https://example.com",
            blog_name="Test Blog",
            title="Test Post"
        )
        
        assert result is True


@pytest.mark.asyncio
async def test_find_entities_by_query():
    """Test finding entities by query"""
    with patch.object(graph_schema.driver, 'session') as mock_session:
        mock_session.return_value.__aenter__.return_value.run = AsyncMock()
        mock_session.return_value.__aenter__.return_value.run.return_value.data = AsyncMock(
            return_value=[
                {
                    "e": {
                        "id": "entity_1",
                        "name": "Meta Ads",
                        "entity_type": "AdPlatform",
                        "confidence": 0.95
                    }
                }
            ]
        )
        
        results = await graph_schema.find_entities_by_query(
            query_text="Meta Ads",
            limit=10
        )
        
        assert len(results) == 1
        assert results[0]["name"] == "Meta Ads"


@pytest.mark.asyncio
async def test_get_entity_context():
    """Test getting entity context with related entities and blog posts"""
    with patch.object(graph_schema.driver, 'session') as mock_session:
        # Mock entity query
        mock_session.return_value.__aenter__.return_value.run = AsyncMock()
        mock_session.return_value.__aenter__.return_value.run.return_value.single = AsyncMock(
            return_value={
                "e": {
                    "id": "entity_1",
                    "name": "Meta Ads",
                    "entity_type": "AdPlatform"
                }
            }
        )
        mock_session.return_value.__aenter__.return_value.run.return_value.data = AsyncMock(
            return_value=[
                {
                    "related": {
                        "id": "entity_2",
                        "name": "purchase-driven",
                        "entity_type": "UserIntent"
                    },
                    "relationship_type": "OPTIMIZES_FOR",
                    "rel_confidence": 0.90
                }
            ]
        )
        
        context = await graph_schema.get_entity_context(
            entity_id="entity_1",
            include_blog_posts=True,
            max_related=5,
            max_blog_posts=10
        )
        
        assert context is not None
        assert context.get("entity") is not None
        assert len(context.get("related_entities", [])) >= 0


@pytest.mark.asyncio
async def test_graph_search_tool_integration():
    """Test graph search tool integration with agent"""
    from src.agents.marketing_strategy_advisor import marketing_strategy_advisor
    
    # Mock graph schema methods
    with patch.object(graph_schema, 'find_entities_by_query', new_callable=AsyncMock) as mock_find:
        mock_find.return_value = [
            {
                "id": "entity_1",
                "name": "Meta Ads",
                "entity_type": "AdPlatform",
                "confidence": 0.95
            }
        ]
        
        with patch.object(graph_schema, 'get_entity_context', new_callable=AsyncMock) as mock_context:
            mock_context.return_value = {
                "entity": {
                    "id": "entity_1",
                    "name": "Meta Ads",
                    "entity_type": "AdPlatform"
                },
                "related_entities": [],
                "blog_posts": []
            }
            
            with patch('src.agents.marketing_strategy_advisor.vector_store') as mock_vector:
                mock_vector.search_similar = AsyncMock(return_value=[])
                
                # Get the graph search tool
                tools = marketing_strategy_advisor._create_tools()
                graph_tool = next((t for t in tools if t.name == "search_marketing_graph"), None)
                
                assert graph_tool is not None
                
                # Test tool execution
                result = await graph_tool.coroutine("Meta Ads")
                assert "Graph-Based Search Results" in result or "No matching entities" in result
