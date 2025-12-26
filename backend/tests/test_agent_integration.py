# backend/tests/test_agent_integration.py
"""Integration tests for the agentic query system."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agent.graph import run_agent
from app.agent.state import AgentState
from app.services.tavily import TavilyResult


@pytest.mark.asyncio
async def test_full_agent_flow_with_mocked_externals():
    """Test complete agent flow from query to answer."""
    # Mock the hybrid search
    mock_search_results = [
        {
            "id": "doc-1",
            "title": "Python Introduction",
            "quick_summary": "Python is a high-level programming language.",
            "url": "https://docs.python.org",
        }
    ]

    # Mock the LLM client
    mock_eval_response = {
        "content": '{"is_sufficient": true, "confidence": 0.85, "missing_information": [], "reasoning": "Context covers the basics"}'
    }
    mock_gen_response = {
        "content": "Python is a versatile, high-level programming language known for its readability and extensive libraries."
    }

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch, \
         patch("app.agent.nodes.evaluator.LLMClient") as MockEvalLLM, \
         patch("app.agent.nodes.generator.LLMClient") as MockGenLLM:

        # Setup mocks
        mock_search_instance = MockSearch.return_value
        mock_search_instance.search = AsyncMock(return_value=mock_search_results)

        mock_eval_instance = MockEvalLLM.return_value
        mock_eval_instance.complete = AsyncMock(return_value=mock_eval_response)

        mock_gen_instance = MockGenLLM.return_value
        mock_gen_instance.complete = AsyncMock(return_value=mock_gen_response)

        # Run agent
        result = await run_agent("What is Python?", session=None)

        # Verify results
        assert result.final_answer is not None
        assert "Python" in result.final_answer
        assert len(result.sources) == 1
        assert result.sources[0].source_type == "internal"
        assert result.research_iterations == 0  # No external research needed


@pytest.mark.asyncio
async def test_agent_flow_with_research():
    """Test agent triggers external research when needed."""
    mock_search_results = []  # No internal results

    mock_eval_insufficient = {
        "content": '{"is_sufficient": false, "confidence": 0.2, "missing_information": ["Python basics"], "reasoning": "No internal docs"}'
    }
    mock_eval_sufficient = {
        "content": '{"is_sufficient": true, "confidence": 0.9, "missing_information": [], "reasoning": "Web results helpful"}'
    }
    mock_gen_response = {
        "content": "Based on web research, Python is..."
    }

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch, \
         patch("app.agent.nodes.evaluator.LLMClient") as MockEvalLLM, \
         patch("app.agent.nodes.generator.LLMClient") as MockGenLLM, \
         patch("app.agent.nodes.researcher.TavilyService") as MockTavily:

        # Setup mocks
        mock_search_instance = MockSearch.return_value
        mock_search_instance.search = AsyncMock(return_value=mock_search_results)

        mock_eval_instance = MockEvalLLM.return_value
        mock_eval_instance.complete = AsyncMock(
            side_effect=[mock_eval_insufficient, mock_eval_sufficient]
        )

        mock_gen_instance = MockGenLLM.return_value
        mock_gen_instance.complete = AsyncMock(return_value=mock_gen_response)

        mock_tavily_instance = MockTavily.return_value
        mock_tavily_instance.search = AsyncMock(return_value=[
            TavilyResult(title="Python.org", url="https://python.org", content="Python info", score=0.9)
        ])

        # Run agent
        result = await run_agent("What is Python?", session=None)

        # Verify external research was performed
        assert result.research_iterations >= 1
        mock_tavily_instance.search.assert_called()


@pytest.mark.asyncio
async def test_agent_flow_with_max_iterations():
    """Test agent respects max_iterations limit when context is never sufficient."""
    mock_search_results = []  # No internal results

    mock_eval_insufficient = {
        "content": '{"is_sufficient": false, "confidence": 0.1, "missing_information": ["everything"], "reasoning": "No useful info found"}'
    }
    mock_gen_response = {
        "content": "I could not find enough information to fully answer your question."
    }

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch, \
         patch("app.agent.nodes.evaluator.LLMClient") as MockEvalLLM, \
         patch("app.agent.nodes.generator.LLMClient") as MockGenLLM, \
         patch("app.agent.nodes.researcher.TavilyService") as MockTavily:

        # Setup mocks
        mock_search_instance = MockSearch.return_value
        mock_search_instance.search = AsyncMock(return_value=mock_search_results)

        # Always returns insufficient
        mock_eval_instance = MockEvalLLM.return_value
        mock_eval_instance.complete = AsyncMock(return_value=mock_eval_insufficient)

        mock_gen_instance = MockGenLLM.return_value
        mock_gen_instance.complete = AsyncMock(return_value=mock_gen_response)

        mock_tavily_instance = MockTavily.return_value
        mock_tavily_instance.search = AsyncMock(return_value=[
            TavilyResult(title="Some result", url="https://example.com", content="Some content", score=0.5)
        ])

        # Run agent with max_iterations=2
        result = await run_agent("Impossible question?", session=None, max_iterations=2)

        # Verify agent stopped after max iterations
        assert result.research_iterations <= 2
        # Should still generate an answer
        assert result.final_answer is not None


@pytest.mark.asyncio
async def test_agent_handles_external_service_errors():
    """Test agent handles errors from external services gracefully."""
    mock_search_results = []  # No internal results

    mock_eval_insufficient = {
        "content": '{"is_sufficient": false, "confidence": 0.2, "missing_information": ["info"], "reasoning": "Need more"}'
    }
    mock_eval_sufficient = {
        "content": '{"is_sufficient": true, "confidence": 0.6, "missing_information": [], "reasoning": "Proceed anyway"}'
    }
    mock_gen_response = {
        "content": "I found limited information but here is what I know."
    }

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch, \
         patch("app.agent.nodes.evaluator.LLMClient") as MockEvalLLM, \
         patch("app.agent.nodes.generator.LLMClient") as MockGenLLM, \
         patch("app.agent.nodes.researcher.TavilyService") as MockTavily:

        # Setup mocks
        mock_search_instance = MockSearch.return_value
        mock_search_instance.search = AsyncMock(return_value=mock_search_results)

        # First insufficient, second sufficient (to exit after error)
        mock_eval_instance = MockEvalLLM.return_value
        mock_eval_instance.complete = AsyncMock(
            side_effect=[mock_eval_insufficient, mock_eval_sufficient]
        )

        mock_gen_instance = MockGenLLM.return_value
        mock_gen_instance.complete = AsyncMock(return_value=mock_gen_response)

        # Tavily raises an error
        mock_tavily_instance = MockTavily.return_value
        mock_tavily_instance.search = AsyncMock(side_effect=Exception("Tavily API error"))

        # Run agent
        result = await run_agent("What is Python?", session=None)

        # Agent should still produce an answer despite Tavily error
        # The researcher node catches exceptions and increments iterations
        assert result.final_answer is not None
        assert result.research_iterations >= 1


@pytest.mark.asyncio
async def test_agent_combines_internal_and_external_sources():
    """Test agent correctly combines sources from internal and external results."""
    mock_internal_results = [
        {
            "id": "doc-1",
            "title": "Internal Python Doc",
            "quick_summary": "Python is a language.",
            "url": "https://internal.docs/python",
        }
    ]

    mock_eval_insufficient = {
        "content": '{"is_sufficient": false, "confidence": 0.4, "missing_information": ["more details"], "reasoning": "Need more details"}'
    }
    mock_eval_sufficient = {
        "content": '{"is_sufficient": true, "confidence": 0.9, "missing_information": [], "reasoning": "Good coverage now"}'
    }
    mock_gen_response = {
        "content": "Python is a versatile language. Here are details from both internal docs and web research."
    }

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch, \
         patch("app.agent.nodes.evaluator.LLMClient") as MockEvalLLM, \
         patch("app.agent.nodes.generator.LLMClient") as MockGenLLM, \
         patch("app.agent.nodes.researcher.TavilyService") as MockTavily:

        # Setup mocks
        mock_search_instance = MockSearch.return_value
        mock_search_instance.search = AsyncMock(return_value=mock_internal_results)

        mock_eval_instance = MockEvalLLM.return_value
        mock_eval_instance.complete = AsyncMock(
            side_effect=[mock_eval_insufficient, mock_eval_sufficient]
        )

        mock_gen_instance = MockGenLLM.return_value
        mock_gen_instance.complete = AsyncMock(return_value=mock_gen_response)

        mock_tavily_instance = MockTavily.return_value
        mock_tavily_instance.search = AsyncMock(return_value=[
            TavilyResult(title="External Python Doc", url="https://python.org", content="External content", score=0.8)
        ])

        # Run agent
        result = await run_agent("What is Python?", session=None)

        # Verify both internal and external sources are present
        assert result.final_answer is not None
        assert len(result.sources) == 2

        internal_sources = [s for s in result.sources if s.source_type == "internal"]
        external_sources = [s for s in result.sources if s.source_type == "external"]

        assert len(internal_sources) == 1
        assert len(external_sources) == 1
        assert internal_sources[0].title == "Internal Python Doc"
        assert external_sources[0].title == "External Python Doc"


@pytest.mark.asyncio
async def test_agent_preserves_query_throughout_flow():
    """Test that the original query is preserved and used throughout the agent flow."""
    test_query = "What are the best practices for Python testing?"
    mock_internal_results = [
        {
            "id": "doc-1",
            "title": "Testing Guide",
            "quick_summary": "Guide to testing.",
            "url": "https://docs.test/guide",
        }
    ]

    mock_eval_response = {
        "content": '{"is_sufficient": true, "confidence": 0.9, "missing_information": [], "reasoning": "Good info"}'
    }
    mock_gen_response = {
        "content": "Here are the best practices for Python testing..."
    }

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch, \
         patch("app.agent.nodes.evaluator.LLMClient") as MockEvalLLM, \
         patch("app.agent.nodes.generator.LLMClient") as MockGenLLM:

        # Setup mocks
        mock_search_instance = MockSearch.return_value
        mock_search_instance.search = AsyncMock(return_value=mock_internal_results)

        mock_eval_instance = MockEvalLLM.return_value
        mock_eval_instance.complete = AsyncMock(return_value=mock_eval_response)

        mock_gen_instance = MockGenLLM.return_value
        mock_gen_instance.complete = AsyncMock(return_value=mock_gen_response)

        # Run agent
        result = await run_agent(test_query, session=None)

        # Verify query is preserved in final state
        assert result.query == test_query
        assert result.final_answer is not None

        # Verify search was called with the query
        search_call_args = mock_search_instance.search.call_args
        assert search_call_args[1]["query"] == test_query


@pytest.mark.asyncio
async def test_agent_with_empty_response_handling():
    """Test agent handles empty or malformed LLM responses gracefully."""
    mock_internal_results = [
        {
            "id": "doc-1",
            "title": "Some Doc",
            "quick_summary": "Some content.",
            "url": "https://example.com",
        }
    ]

    # Malformed JSON in evaluation response
    mock_eval_response = {
        "content": "This is not valid JSON at all"
    }
    mock_gen_response = {
        "content": "Generated answer based on available context."
    }

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch, \
         patch("app.agent.nodes.evaluator.LLMClient") as MockEvalLLM, \
         patch("app.agent.nodes.generator.LLMClient") as MockGenLLM:

        # Setup mocks
        mock_search_instance = MockSearch.return_value
        mock_search_instance.search = AsyncMock(return_value=mock_internal_results)

        mock_eval_instance = MockEvalLLM.return_value
        mock_eval_instance.complete = AsyncMock(return_value=mock_eval_response)

        mock_gen_instance = MockGenLLM.return_value
        mock_gen_instance.complete = AsyncMock(return_value=mock_gen_response)

        # Run agent - should handle malformed response gracefully
        result = await run_agent("Test query", session=None)

        # The evaluator returns is_sufficient=False on parse error,
        # but then defaults to is_sufficient=True to avoid loops
        # Either way, agent should complete without crashing
        assert result is not None


@pytest.mark.asyncio
async def test_agent_multiple_research_iterations():
    """Test agent can perform multiple research iterations before succeeding."""
    mock_internal_results = []  # No internal results

    mock_eval_insufficient_1 = {
        "content": '{"is_sufficient": false, "confidence": 0.2, "missing_information": ["topic A"], "reasoning": "Need topic A"}'
    }
    mock_eval_insufficient_2 = {
        "content": '{"is_sufficient": false, "confidence": 0.5, "missing_information": ["topic B"], "reasoning": "Need topic B too"}'
    }
    mock_eval_sufficient = {
        "content": '{"is_sufficient": true, "confidence": 0.9, "missing_information": [], "reasoning": "Now sufficient"}'
    }
    mock_gen_response = {
        "content": "Comprehensive answer after multiple research iterations."
    }

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch, \
         patch("app.agent.nodes.evaluator.LLMClient") as MockEvalLLM, \
         patch("app.agent.nodes.generator.LLMClient") as MockGenLLM, \
         patch("app.agent.nodes.researcher.TavilyService") as MockTavily:

        # Setup mocks
        mock_search_instance = MockSearch.return_value
        mock_search_instance.search = AsyncMock(return_value=mock_internal_results)

        # Need 3 evaluations: initial, after 1st research, after 2nd research
        mock_eval_instance = MockEvalLLM.return_value
        mock_eval_instance.complete = AsyncMock(
            side_effect=[mock_eval_insufficient_1, mock_eval_insufficient_2, mock_eval_sufficient]
        )

        mock_gen_instance = MockGenLLM.return_value
        mock_gen_instance.complete = AsyncMock(return_value=mock_gen_response)

        mock_tavily_instance = MockTavily.return_value
        mock_tavily_instance.search = AsyncMock(return_value=[
            TavilyResult(title="Research Result", url="https://research.com", content="Research content", score=0.7)
        ])

        # Run agent with enough iterations allowed
        result = await run_agent("Complex multi-topic question?", session=None, max_iterations=5)

        # Verify multiple research iterations occurred
        assert result.research_iterations == 2
        assert result.final_answer is not None
        # Should have called Tavily twice
        assert mock_tavily_instance.search.call_count == 2
