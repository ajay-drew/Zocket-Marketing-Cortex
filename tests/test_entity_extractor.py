"""
Tests for entity extraction module
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.knowledge.entity_extractor import EntityExtractor, Entity, Relationship, ExtractionResult
from langchain_core.messages import AIMessage


@pytest.mark.asyncio
async def test_entity_extractor_initialization():
    """Test EntityExtractor initialization"""
    extractor = EntityExtractor()
    assert extractor is not None
    assert extractor.llm is not None


@pytest.mark.asyncio
async def test_extract_entities_success():
    """Test successful entity extraction"""
    # Mock LLM response - valid JSON without trailing commas
    mock_response = AIMessage(content='''{
        "entities": [
            {
                "name": "Meta Ads",
                "type": "AdPlatform",
                "confidence": 0.95
            },
            {
                "name": "purchase-driven",
                "type": "UserIntent",
                "confidence": 0.90
            }
        ],
        "relationships": [
            {
                "source": "Meta Ads",
                "target": "purchase-driven",
                "type": "OPTIMIZES_FOR",
                "confidence": 0.85
            }
        ]
    }''')
    
    with patch('src.knowledge.entity_extractor.ChatGroq') as mock_chat_groq:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_groq.return_value = mock_llm
        
        extractor = EntityExtractor()
        
        result = await extractor.extract_entities(
            content="Meta Ads is optimized for purchase-driven intent",
            chunk_id="test_chunk_1",
            url="https://example.com"
        )
        
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 2
        assert result.entities[0].name == "Meta Ads"
        assert result.entities[0].type == "AdPlatform"
        assert len(result.relationships) == 1
        assert result.relationships[0].source == "Meta Ads"
        assert result.relationships[0].target == "purchase-driven"


@pytest.mark.asyncio
async def test_extract_entities_low_confidence_filter():
    """Test that entities with low confidence are filtered out"""
    # Mock LLM response with low confidence entities
    mock_response = AIMessage(content='''{
        "entities": [
            {
                "name": "Meta Ads",
                "type": "AdPlatform",
                "confidence": 0.95
            },
            {
                "name": "Low Confidence Entity",
                "type": "MarketingConcept",
                "confidence": 0.50
            }
        ],
        "relationships": []
    }''')
    
    with patch('src.knowledge.entity_extractor.ChatGroq') as mock_chat_groq:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_groq.return_value = mock_llm
        
        extractor = EntityExtractor()
        
        result = await extractor.extract_entities(
            content="Test content",
            chunk_id="test_chunk_1"
        )
        
        # Only high confidence entity should be included
        assert len(result.entities) == 1
        assert result.entities[0].name == "Meta Ads"


@pytest.mark.asyncio
async def test_extract_entities_invalid_json():
    """Test handling of invalid JSON response"""
    # Mock LLM response with invalid JSON
    mock_response = AIMessage(content="This is not JSON")
    
    with patch('src.knowledge.entity_extractor.ChatGroq') as mock_chat_groq:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_groq.return_value = mock_llm
        
        extractor = EntityExtractor()
        
        result = await extractor.extract_entities(
            content="Test content",
            chunk_id="test_chunk_1"
        )
        
        # Should return empty result
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0
        assert len(result.relationships) == 0


@pytest.mark.asyncio
async def test_extract_entities_error_handling():
    """Test error handling during extraction"""
    with patch('src.knowledge.entity_extractor.ChatGroq') as mock_chat_groq:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM error"))
        mock_chat_groq.return_value = mock_llm
        
        extractor = EntityExtractor()
        result = await extractor.extract_entities(
            content="Test content",
            chunk_id="test_chunk_1"
        )
        
        # Should return empty result on error
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0


def test_generate_entity_id():
    """Test entity ID generation"""
    entity_id = EntityExtractor._generate_entity_id("Meta Ads", "AdPlatform")
    
    assert entity_id.startswith("AdPlatform_")
    assert "meta_ads" in entity_id.lower()
    assert len(entity_id) > 10  # Should include hash


def test_normalize_entity_name():
    """Test entity name normalization"""
    extractor = EntityExtractor()
    
    normalized = extractor.normalize_entity_name("  Meta Ads  ")
    assert normalized == "meta ads"
    
    normalized = extractor.normalize_entity_name("The Google Ads")
    assert normalized == "google ads"
