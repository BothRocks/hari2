# backend/tests/test_agent_generator.py
"""Tests for generator node."""
import pytest
from unittest.mock import AsyncMock, patch
from app.agent.state import AgentState
from app.agent.nodes.generator import generator_node


@pytest.mark.asyncio
async def test_generator_node_produces_answer():
    """Test generator creates final answer from context."""
    state = AgentState(
        query="What is Python?",
        internal_results=[
            {"id": "1", "title": "Python Guide", "quick_summary": "Python is a programming language."}
        ],
        external_results=[],
    )

    mock_response = {"content": "Python is a high-level programming language."}

    with patch("app.agent.nodes.generator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(return_value=mock_response)

        result = await generator_node(state)

        assert result["final_answer"] == "Python is a high-level programming language."
        assert len(result["sources"]) == 1
        assert result["sources"][0].source_type == "internal"


@pytest.mark.asyncio
async def test_generator_node_combines_internal_and_external():
    """Test generator uses both internal and external sources."""
    state = AgentState(
        query="What is Python 3.12?",
        internal_results=[
            {"id": "1", "title": "Python Docs", "quick_summary": "Python overview"}
        ],
        external_results=[
            {"title": "Python 3.12 Release", "url": "https://python.org", "content": "New features..."}
        ],
    )

    mock_response = {"content": "Python 3.12 includes many new features."}

    with patch("app.agent.nodes.generator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(return_value=mock_response)

        result = await generator_node(state)

        assert len(result["sources"]) == 2
        source_types = [s.source_type for s in result["sources"]]
        assert "internal" in source_types
        assert "external" in source_types


@pytest.mark.asyncio
async def test_generator_handles_llm_error():
    """Test generator handles LLM errors gracefully."""
    state = AgentState(query="test", internal_results=[], external_results=[])

    with patch("app.agent.nodes.generator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(side_effect=Exception("LLM error"))

        result = await generator_node(state)

        assert result["error"] is not None
        assert "LLM error" in result["error"]
