"""Tests for streaming query API endpoint."""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.utils.sse import parse_sse


@pytest.fixture
def auth_headers():
    """Headers with API key auth."""
    return {"X-API-Key": "gorgonzola"}


@pytest.mark.asyncio
async def test_stream_endpoint_returns_sse(auth_headers):
    """Verify /query/stream returns SSE content type."""
    with patch("app.api.query.run_agent_stream") as mock_stream:
        async def fake_stream(*args, **kwargs):
            yield 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n'
            yield 'event: done\ndata: {"research_iterations": 0}\n\n'

        mock_stream.return_value = fake_stream()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query/stream",
                json={"query": "test question"},
                headers=auth_headers,
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


@pytest.mark.asyncio
async def test_stream_endpoint_emits_events(auth_headers):
    """Verify stream emits expected event sequence."""
    with patch("app.api.query.run_agent_stream") as mock_stream:
        async def fake_stream(*args, **kwargs):
            yield 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n'
            yield 'event: chunk\ndata: {"content": "Answer text."}\n\n'
            yield 'event: sources\ndata: {"internal": [], "external": []}\n\n'
            yield 'event: done\ndata: {"research_iterations": 0}\n\n'

        mock_stream.return_value = fake_stream()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query/stream",
                json={"query": "test question"},
                headers=auth_headers,
            )

            events = parse_sse(response.text)
            event_types = [e["type"] for e in events]

            assert "thinking" in event_types
            assert "chunk" in event_types
            assert "sources" in event_types
            assert "done" in event_types


@pytest.mark.asyncio
async def test_stream_endpoint_requires_auth():
    """Test endpoint requires authentication."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/query/stream",
            json={"query": "test question"},
        )

    assert response.status_code == 401
