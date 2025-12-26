# backend/tests/test_agent_researcher.py
"""Tests for researcher node."""
import pytest
from unittest.mock import AsyncMock, patch
from app.agent.state import AgentState, EvaluationResult
from app.agent.nodes.researcher import researcher_node
from app.services.tavily import TavilyResult


@pytest.mark.asyncio
async def test_researcher_node_calls_tavily():
    """Test researcher node searches Tavily and updates state."""
    state = AgentState(
        query="What is Python 3.12?",
        research_iterations=0,
        evaluation=EvaluationResult(
            is_sufficient=False,
            confidence=0.3,
            missing_information=["Python 3.12 features"],
            reasoning="Need current info"
        )
    )

    mock_results = [
        TavilyResult(
            title="Python 3.12 Released",
            url="https://python.org/3.12",
            content="Python 3.12 includes...",
            score=0.95
        )
    ]

    with patch("app.agent.nodes.researcher.TavilyService") as MockTavily:
        mock_instance = MockTavily.return_value
        mock_instance.search = AsyncMock(return_value=mock_results)

        result = await researcher_node(state)

        assert len(result["external_results"]) == 1
        assert result["external_results"][0]["title"] == "Python 3.12 Released"
        assert result["research_iterations"] == 1


@pytest.mark.asyncio
async def test_researcher_node_handles_tavily_error():
    """Test researcher gracefully handles Tavily errors."""
    state = AgentState(
        query="test query",
        research_iterations=0,
        evaluation=EvaluationResult(
            is_sufficient=False,
            confidence=0.3,
            missing_information=["data"],
            reasoning="Need info"
        )
    )

    with patch("app.agent.nodes.researcher.TavilyService") as MockTavily:
        mock_instance = MockTavily.return_value
        mock_instance.search = AsyncMock(side_effect=ValueError("API error"))

        result = await researcher_node(state)

        # Should still increment iteration but have empty results
        assert result["external_results"] == []
        assert result["research_iterations"] == 1


@pytest.mark.asyncio
async def test_researcher_uses_missing_info_for_query():
    """Test researcher refines query using missing information."""
    state = AgentState(
        query="Tell me about Python",
        research_iterations=0,
        evaluation=EvaluationResult(
            is_sufficient=False,
            confidence=0.3,
            missing_information=["Python 3.12 features", "release date"],
            reasoning="Too general"
        )
    )

    with patch("app.agent.nodes.researcher.TavilyService") as MockTavily:
        mock_instance = MockTavily.return_value
        mock_instance.search = AsyncMock(return_value=[])

        await researcher_node(state)

        # Check that search was called with refined query
        call_args = mock_instance.search.call_args
        search_query = call_args[0][0] if call_args[0] else call_args[1].get("query", "")
        assert "Python 3.12" in search_query or "release date" in search_query
