"""Integration test for SSE streaming with real agent flow."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.utils.sse import parse_sse


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    from app.models.user import User
    return User(id="test-user-id", email="test@example.com", name="Test User", role="user")


@pytest.mark.asyncio
async def test_full_streaming_flow(mock_user):
    """Test complete SSE streaming from API to parsed events."""
    with patch("app.api.query.run_agent_stream") as mock_stream:
        async def fake_stream(*args, **kwargs):
            yield 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n'
            yield 'event: thinking\ndata: {"step": "evaluate", "message": "Evaluating..."}\n\n'
            yield 'event: chunk\ndata: {"content": "Test answer."}\n\n'
            yield 'event: sources\ndata: {"internal": [{"id": "1", "title": "Doc", "url": "https://example.com"}], "external": []}\n\n'
            yield 'event: done\ndata: {"research_iterations": 0}\n\n'

        mock_stream.return_value = fake_stream()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query/stream",
                json={"query": "test question", "max_iterations": 1},
                headers={"X-API-Key": "gorgonzola"},
            )

            assert response.status_code == 200
            events = parse_sse(response.text)

            # Verify event sequence
            event_types = [e["type"] for e in events]
            assert "thinking" in event_types
            assert "chunk" in event_types
            assert "sources" in event_types
            assert "done" in event_types

            # Verify content
            chunk_event = next(e for e in events if e["type"] == "chunk")
            assert chunk_event["data"]["content"] == "Test answer."

            # Verify sources
            sources_event = next(e for e in events if e["type"] == "sources")
            assert len(sources_event["data"]["internal"]) == 1
            assert sources_event["data"]["internal"][0]["url"] == "https://example.com"
