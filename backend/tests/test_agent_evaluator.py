# backend/tests/test_agent_evaluator.py
"""Tests for evaluator node."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.agent.state import AgentState
from app.agent.nodes.evaluator import evaluator_node, parse_evaluation_response


def test_parse_evaluation_response_valid_json():
    """Test parsing valid JSON evaluation response."""
    response = json.dumps({
        "is_sufficient": True,
        "confidence": 0.85,
        "missing_information": [],
        "reasoning": "Context fully answers the question"
    })

    result = parse_evaluation_response(response)

    assert result.is_sufficient is True
    assert result.confidence == 0.85
    assert result.missing_information == []


def test_parse_evaluation_response_with_markdown():
    """Test parsing JSON wrapped in markdown code block."""
    response = '''Here is my evaluation:
```json
{
    "is_sufficient": false,
    "confidence": 0.4,
    "missing_information": ["recent data"],
    "reasoning": "Needs current information"
}
```
'''
    result = parse_evaluation_response(response)

    assert result.is_sufficient is False
    assert result.confidence == 0.4


def test_parse_evaluation_response_invalid_json():
    """Test parsing invalid JSON returns safe default."""
    response = "This is not valid JSON at all"

    result = parse_evaluation_response(response)

    # Should default to insufficient
    assert result.is_sufficient is False
    assert result.confidence == 0.5
    assert "Failed to parse evaluation" in result.missing_information


def test_parse_evaluation_response_missing_fields():
    """Test parsing JSON with missing fields uses defaults."""
    response = json.dumps({
        "is_sufficient": True,
        "confidence": 0.9
        # missing_information and reasoning are missing
    })

    result = parse_evaluation_response(response)

    assert result.is_sufficient is True
    assert result.confidence == 0.9
    assert result.missing_information == []
    assert result.reasoning == ""


@pytest.mark.asyncio
async def test_evaluator_node_returns_evaluation():
    """Test evaluator node populates evaluation in state."""
    state = AgentState(
        query="What is the latest Python version?",
        internal_results=[
            {"title": "Python 3.11", "quick_summary": "Python 3.11 features..."}
        ]
    )

    mock_response = {
        "content": json.dumps({
            "is_sufficient": False,
            "confidence": 0.3,
            "missing_information": ["Python 3.12+ information"],
            "reasoning": "Results are outdated"
        })
    }

    with patch("app.agent.nodes.evaluator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(return_value=mock_response)

        result = await evaluator_node(state)

        assert result["evaluation"] is not None
        assert result["evaluation"].is_sufficient is False
        assert result["evaluation"].confidence == 0.3


@pytest.mark.asyncio
async def test_evaluator_node_includes_external_results():
    """Test evaluator node considers external results in context."""
    state = AgentState(
        query="What is FastAPI?",
        internal_results=[
            {"title": "FastAPI Intro", "quick_summary": "FastAPI basics..."}
        ],
        external_results=[
            {"title": "FastAPI Official Docs", "content": "FastAPI is a modern..."}
        ]
    )

    mock_response = {
        "content": json.dumps({
            "is_sufficient": True,
            "confidence": 0.95,
            "missing_information": [],
            "reasoning": "Both internal and external context are comprehensive"
        })
    }

    with patch("app.agent.nodes.evaluator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(return_value=mock_response)

        result = await evaluator_node(state)

        assert result["evaluation"].is_sufficient is True
        assert result["evaluation"].confidence == 0.95


@pytest.mark.asyncio
async def test_evaluator_node_handles_empty_results():
    """Test evaluator handles no results gracefully."""
    state = AgentState(
        query="obscure query with no matches",
        internal_results=[],
        external_results=[]
    )

    mock_response = {
        "content": json.dumps({
            "is_sufficient": False,
            "confidence": 0.1,
            "missing_information": ["Any relevant information"],
            "reasoning": "No context retrieved"
        })
    }

    with patch("app.agent.nodes.evaluator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(return_value=mock_response)

        result = await evaluator_node(state)

        assert result["evaluation"].is_sufficient is False


@pytest.mark.asyncio
async def test_evaluator_node_handles_llm_error():
    """Test evaluator defaults to sufficient on LLM error to avoid infinite loops."""
    state = AgentState(
        query="What is Python?",
        internal_results=[{"title": "Python", "quick_summary": "A language"}]
    )

    with patch("app.agent.nodes.evaluator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(side_effect=Exception("API error"))

        result = await evaluator_node(state)

        # Should default to sufficient to avoid infinite loops
        assert result["evaluation"].is_sufficient is True
        assert "error" in result["evaluation"].reasoning.lower()


@pytest.mark.asyncio
async def test_evaluator_node_uses_correct_temperature():
    """Test evaluator uses temperature=0.0 for deterministic evaluation."""
    state = AgentState(
        query="Test query",
        internal_results=[{"title": "Doc", "quick_summary": "Content"}]
    )

    mock_response = {
        "content": json.dumps({
            "is_sufficient": True,
            "confidence": 0.8,
            "missing_information": [],
            "reasoning": "Sufficient"
        })
    }

    with patch("app.agent.nodes.evaluator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(return_value=mock_response)

        await evaluator_node(state)

        # Verify temperature=0.0 was used
        call_kwargs = mock_instance.complete.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.0
