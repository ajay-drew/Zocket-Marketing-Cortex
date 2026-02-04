"""
Tests for Research Assistant agent
"""
import pytest
from src.agents.research_assistant import research_assistant
import uuid


@pytest.mark.asyncio
async def test_research_assistant_initialization():
    """Test that Research Assistant initializes correctly"""
    assert research_assistant is not None
    assert research_assistant.llm is not None
    assert len(research_assistant.tools) > 0


@pytest.mark.asyncio
async def test_get_memory_context():
    """Test retrieving memory context"""
    session_id = f"test_session_{uuid.uuid4()}"
    
    # Get memory for new session (should be empty)
    messages = await research_assistant.get_memory_context(session_id)
    
    assert isinstance(messages, list)


@pytest.mark.asyncio
async def test_stream_response():
    """Test streaming response from agent"""
    session_id = f"test_session_{uuid.uuid4()}"
    query = "What is digital marketing?"
    
    chunks = []
    async for chunk in research_assistant.stream_response(
        query=query,
        session_id=session_id
    ):
        chunks.append(chunk)
    
    # Should have received some chunks
    assert len(chunks) > 0
    # Combine chunks should form a response
    response = "".join(chunks)
    assert len(response) > 0


@pytest.mark.asyncio
async def test_get_response():
    """Test getting complete response (non-streaming)"""
    session_id = f"test_session_{uuid.uuid4()}"
    query = "Tell me about advertising"
    
    response = await research_assistant.get_response(
        query=query,
        session_id=session_id
    )
    
    assert isinstance(response, str)
    assert len(response) > 0
