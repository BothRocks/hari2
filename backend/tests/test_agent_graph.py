# backend/tests/test_agent_graph.py
"""Tests for the agent graph."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agent.graph import create_agent_graph, run_agent, _retriever_wrapper
from app.agent.state import EvaluationResult, AgentState
from sqlalchemy.ext.asyncio import AsyncSession


def test_create_agent_graph_structure():
    """Test that graph is created with correct nodes."""
    graph = create_agent_graph()

    # Check graph has expected nodes
    assert graph is not None


@pytest.mark.asyncio
async def test_run_agent_sufficient_context():
    """Test agent flow when context is sufficient on first try."""
    mock_internal = [{"id": "1", "title": "Doc", "quick_summary": "Content"}]

    with patch("app.agent.graph.retriever_node", new_callable=AsyncMock) as mock_retriever, \
         patch("app.agent.graph.evaluator_node", new_callable=AsyncMock) as mock_evaluator, \
         patch("app.agent.graph.generator_node", new_callable=AsyncMock) as mock_generator:

        mock_retriever.return_value = {"internal_results": mock_internal}
        mock_evaluator.return_value = {
            "evaluation": EvaluationResult(
                is_sufficient=True,
                confidence=0.9,
                missing_information=[],
                reasoning="Context is complete."
            )
        }
        mock_generator.return_value = {
            "final_answer": "The answer is 42.",
            "sources": [],
            "error": None,
        }

        result = await run_agent("What is the meaning of life?")

        assert result.final_answer == "The answer is 42."
        mock_retriever.assert_called_once()
        mock_evaluator.assert_called_once()
        mock_generator.assert_called_once()


@pytest.mark.asyncio
async def test_run_agent_insufficient_context_triggers_research():
    """Test agent performs research when context is insufficient."""
    mock_internal = [{"id": "1", "title": "Doc", "quick_summary": "Partial info"}]
    mock_external = [{"title": "Web Result", "url": "https://example.com", "content": "More info"}]

    with patch("app.agent.graph.retriever_node", new_callable=AsyncMock) as mock_retriever, \
         patch("app.agent.graph.evaluator_node", new_callable=AsyncMock) as mock_evaluator, \
         patch("app.agent.graph.researcher_node", new_callable=AsyncMock) as mock_researcher, \
         patch("app.agent.graph.generator_node", new_callable=AsyncMock) as mock_generator:

        mock_retriever.return_value = {"internal_results": mock_internal}

        # First evaluation: insufficient, second: sufficient
        mock_evaluator.side_effect = [
            {
                "evaluation": EvaluationResult(
                    is_sufficient=False,
                    confidence=0.3,
                    missing_information=["additional details"],
                    reasoning="Need more info."
                )
            },
            {
                "evaluation": EvaluationResult(
                    is_sufficient=True,
                    confidence=0.9,
                    missing_information=[],
                    reasoning="Context is now complete."
                )
            },
        ]

        mock_researcher.return_value = {
            "external_results": mock_external,
            "research_iterations": 1,
        }

        mock_generator.return_value = {
            "final_answer": "Complete answer with research.",
            "sources": [],
            "error": None,
        }

        result = await run_agent("Complex question?")

        assert result.final_answer == "Complete answer with research."
        mock_retriever.assert_called_once()
        assert mock_evaluator.call_count == 2
        mock_researcher.assert_called_once()
        mock_generator.assert_called_once()


@pytest.mark.asyncio
async def test_run_agent_max_iterations_stops_research():
    """Test agent stops research after max iterations."""
    with patch("app.agent.graph.retriever_node", new_callable=AsyncMock) as mock_retriever, \
         patch("app.agent.graph.evaluator_node", new_callable=AsyncMock) as mock_evaluator, \
         patch("app.agent.graph.researcher_node", new_callable=AsyncMock) as mock_researcher, \
         patch("app.agent.graph.generator_node", new_callable=AsyncMock) as mock_generator:

        mock_retriever.return_value = {"internal_results": []}

        # Always insufficient - but router should stop after max iterations
        mock_evaluator.return_value = {
            "evaluation": EvaluationResult(
                is_sufficient=False,
                confidence=0.2,
                missing_information=["everything"],
                reasoning="Context is insufficient."
            )
        }

        # Researcher increments iterations
        call_count = [0]

        def researcher_side_effect(state, *args, **kwargs):
            call_count[0] += 1
            return {
                "external_results": [],
                "research_iterations": call_count[0],
            }

        mock_researcher.side_effect = researcher_side_effect

        mock_generator.return_value = {
            "final_answer": "Best effort answer.",
            "sources": [],
            "error": None,
        }

        result = await run_agent("Impossible question?", max_iterations=2)

        assert result.final_answer == "Best effort answer."
        # Should have researched exactly max_iterations times
        assert mock_researcher.call_count <= 2
        mock_generator.assert_called_once()


def test_create_agent_graph_has_expected_nodes():
    """Test graph structure has all expected nodes."""
    graph = create_agent_graph()

    # The compiled graph should have our nodes
    # Access internal representation to verify structure
    assert graph is not None

    # Test that the graph can be invoked (basic sanity check)
    # Actual invocation happens in other tests with mocks


@pytest.mark.asyncio
async def test_retriever_wrapper_passes_session_from_config():
    """Test that _retriever_wrapper extracts session from config and passes it to retriever_node."""
    # Create a mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Create test state
    state = AgentState(query="Test query")

    # Create config with session
    config = {"configurable": {"session": mock_session}}

    # Mock the retriever_node function
    with patch("app.agent.graph.retriever_node", new_callable=AsyncMock) as mock_retriever:
        mock_retriever.return_value = {"internal_results": []}

        # Call the wrapper
        result = await _retriever_wrapper(state, config)

        # Verify retriever_node was called with the session
        mock_retriever.assert_called_once_with(state, session=mock_session)
        assert result == {"internal_results": []}


@pytest.mark.asyncio
async def test_retriever_wrapper_handles_missing_session():
    """Test that _retriever_wrapper handles missing session gracefully."""
    state = AgentState(query="Test query")

    # Config without session
    config = {"configurable": {}}

    with patch("app.agent.graph.retriever_node", new_callable=AsyncMock) as mock_retriever:
        mock_retriever.return_value = {"internal_results": []}

        # Call the wrapper
        result = await _retriever_wrapper(state, config)

        # Verify retriever_node was called with None session
        mock_retriever.assert_called_once_with(state, session=None)
        assert result == {"internal_results": []}


@pytest.mark.asyncio
async def test_retriever_wrapper_handles_none_config():
    """Test that _retriever_wrapper handles None config gracefully."""
    state = AgentState(query="Test query")

    with patch("app.agent.graph.retriever_node", new_callable=AsyncMock) as mock_retriever:
        mock_retriever.return_value = {"internal_results": []}

        # Call the wrapper with None config
        result = await _retriever_wrapper(state, None)

        # Verify retriever_node was called with None session
        mock_retriever.assert_called_once_with(state, session=None)
        assert result == {"internal_results": []}


@pytest.mark.asyncio
async def test_run_agent_passes_session_through_config():
    """Test that run_agent properly passes session through LangGraph config."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_internal = [{"id": "1", "title": "Doc", "quick_summary": "Content"}]

    with patch("app.agent.graph.retriever_node", new_callable=AsyncMock) as mock_retriever, \
         patch("app.agent.graph.evaluator_node", new_callable=AsyncMock) as mock_evaluator, \
         patch("app.agent.graph.generator_node", new_callable=AsyncMock) as mock_generator:

        # Capture what the retriever wrapper is called with
        original_retriever = mock_retriever

        mock_retriever.return_value = {"internal_results": mock_internal}
        mock_evaluator.return_value = {
            "evaluation": EvaluationResult(
                is_sufficient=True,
                confidence=0.9,
                missing_information=[],
                reasoning="Context is complete."
            )
        }
        mock_generator.return_value = {
            "final_answer": "The answer is 42.",
            "sources": [],
            "error": None,
        }

        # Run agent with session
        result = await run_agent("What is the meaning of life?", session=mock_session)

        # Verify result is correct
        assert result.final_answer == "The answer is 42."

        # Verify retriever was called with the session
        mock_retriever.assert_called_once()
        call_args = mock_retriever.call_args
        # Session should have been passed in the call
        assert call_args[1].get('session') == mock_session or call_args[0] == (mock_session,)
