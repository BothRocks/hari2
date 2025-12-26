# backend/tests/test_agent_retriever.py
"""Tests for retriever node."""
import pytest
from unittest.mock import AsyncMock, patch
from app.agent.state import AgentState
from app.agent.nodes.retriever import retriever_node


@pytest.mark.asyncio
async def test_retriever_node_populates_internal_results():
    """Test that retriever node calls HybridSearch and populates state."""
    mock_results = [
        {"id": "doc1", "title": "Python Guide", "quick_summary": "A guide to Python"},
        {"id": "doc2", "title": "FastAPI Docs", "quick_summary": "FastAPI documentation"},
    ]

    state = AgentState(query="How do I use FastAPI?")

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch:
        mock_instance = MockSearch.return_value
        mock_instance.search = AsyncMock(return_value=mock_results)

        result = await retriever_node(state, session=None)

        assert len(result["internal_results"]) == 2
        assert result["internal_results"][0]["title"] == "Python Guide"
        mock_instance.search.assert_called_once()


@pytest.mark.asyncio
async def test_retriever_node_handles_empty_results():
    """Test retriever handles no results gracefully."""
    state = AgentState(query="obscure query with no matches")

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch:
        mock_instance = MockSearch.return_value
        mock_instance.search = AsyncMock(return_value=[])

        result = await retriever_node(state, session=None)

        assert result["internal_results"] == []
