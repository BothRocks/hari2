# backend/tests/test_agent_stream.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.graph import run_agent_stream
from app.utils.sse import parse_sse


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.mark.asyncio
async def test_run_agent_stream_emits_thinking_events(mock_session):
    """Verify stream emits thinking events for nodes."""
    with patch("app.agent.graph.create_agent_graph") as mock_create:
        mock_graph = AsyncMock()

        # Simulate astream_events yielding node events
        async def fake_events(*args, **kwargs):
            yield {"event": "on_chain_start", "name": "retrieve", "data": {}}
            yield {"event": "on_chain_end", "name": "retrieve", "data": {"output": {"internal_results": []}}}
            yield {"event": "on_chain_start", "name": "evaluate", "data": {}}
            yield {"event": "on_chain_end", "name": "evaluate", "data": {"output": {}}}
            yield {"event": "on_chain_start", "name": "generate", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "generate",
                "data": {"output": {"final_answer": "Test answer.", "sources": []}}
            }

        mock_graph.astream_events = fake_events
        mock_create.return_value = mock_graph

        events = []
        async for chunk in run_agent_stream("test query", mock_session):
            events.extend(parse_sse(chunk))

        thinking_events = [e for e in events if e["type"] == "thinking"]
        steps = [e["data"]["step"] for e in thinking_events]
        assert "retrieve" in steps
        assert "generate" in steps


@pytest.mark.asyncio
async def test_run_agent_stream_emits_chunks(mock_session):
    """Verify stream emits answer chunks."""
    with patch("app.agent.graph.create_agent_graph") as mock_create:
        mock_graph = AsyncMock()

        async def fake_events(*args, **kwargs):
            yield {"event": "on_chain_start", "name": "generate", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "generate",
                "data": {"output": {"final_answer": "First sentence. Second sentence.", "sources": []}}
            }

        mock_graph.astream_events = fake_events
        mock_create.return_value = mock_graph

        events = []
        async for chunk in run_agent_stream("test", mock_session):
            events.extend(parse_sse(chunk))

        chunk_events = [e for e in events if e["type"] == "chunk"]
        assert len(chunk_events) >= 2
        contents = [e["data"]["content"] for e in chunk_events]
        assert "First sentence." in "".join(contents)


@pytest.mark.asyncio
async def test_run_agent_stream_emits_done(mock_session):
    """Verify stream emits done event."""
    with patch("app.agent.graph.create_agent_graph") as mock_create:
        mock_graph = AsyncMock()

        async def fake_events(*args, **kwargs):
            yield {
                "event": "on_chain_end",
                "name": "generate",
                "data": {"output": {"final_answer": "Answer.", "sources": [], "research_iterations": 1}}
            }

        mock_graph.astream_events = fake_events
        mock_create.return_value = mock_graph

        events = []
        async for chunk in run_agent_stream("test", mock_session):
            events.extend(parse_sse(chunk))

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1
