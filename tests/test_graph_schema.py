"""
Tests for Neo4j graph schema operations
"""
import pytest
from src.knowledge.graph_schema import GraphSchema
from src.config import settings


@pytest.fixture
async def graph():
    """Create graph schema instance"""
    schema = GraphSchema()
    await schema.initialize_schema()
    
    # Clean up test data before tests
    async with schema.driver.session(database=settings.neo4j_database) as session:
        await session.run("MATCH (n) WHERE n.id STARTS WITH 'test_' DETACH DELETE n")
    
    yield schema
    
    # Clean up test data after tests
    async with schema.driver.session(database=settings.neo4j_database) as session:
        await session.run("MATCH (n) WHERE n.id STARTS WITH 'test_' DETACH DELETE n")
    
    await schema.close()


@pytest.mark.asyncio
async def test_create_campaign(graph):
    """Test campaign creation"""
    campaign = await graph.create_campaign(
        campaign_id="test_camp_001",
        name="Test Campaign",
        objective="CONVERSIONS",
        budget=10000.0,
        start_date="2026-01-01"
    )
    assert campaign["id"] == "test_camp_001"
    assert campaign["name"] == "Test Campaign"
    assert campaign["budget"] == 10000.0


@pytest.mark.asyncio
async def test_create_adset(graph):
    """Test adset creation"""
    # First create campaign
    await graph.create_campaign(
        campaign_id="test_camp_002",
        name="Test Campaign 2",
        objective="TRAFFIC",
        budget=5000.0,
        start_date="2026-01-01"
    )
    
    # Then create adset
    adset = await graph.create_adset(
        adset_id="test_adset_001",
        campaign_id="test_camp_002",
        name="Test AdSet",
        targeting={"age": "25-45"},
        budget=2000.0
    )
    assert adset["id"] == "test_adset_001"
    assert adset["name"] == "Test AdSet"


@pytest.mark.asyncio
async def test_campaign_hierarchy(graph):
    """Test retrieving campaign hierarchy"""
    # Create campaign
    await graph.create_campaign(
        campaign_id="test_camp_003",
        name="Test Campaign 3",
        objective="CONVERSIONS",
        budget=10000.0,
        start_date="2026-01-01"
    )
    
    # Create adset
    await graph.create_adset(
        adset_id="test_adset_002",
        campaign_id="test_camp_003",
        name="Test AdSet 2",
        targeting={"age": "18-35"},
        budget=5000.0
    )
    
    # Get hierarchy
    hierarchy = await graph.get_campaign_hierarchy("test_camp_003")
    assert hierarchy["campaign"]["id"] == "test_camp_003"
    assert len(hierarchy["adsets"]) == 1
    assert hierarchy["adsets"][0]["id"] == "test_adset_002"
