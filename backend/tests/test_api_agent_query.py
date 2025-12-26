"""Tests for agentic query API endpoint."""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.agent.state import AgentState, SourceReference


@pytest.fixture
def auth_headers():
    """Headers with API key auth."""
    return {"X-API-Key": "gorgonzola"}


@pytest.mark.asyncio
async def test_agentic_query_endpoint(auth_headers):
    """Test POST /api/query/agent returns agentic response."""
    mock_state = AgentState(
        query="What is Python?",
        final_answer="Python is a programming language.",
        sources=[
            SourceReference(id="1", title="Python Docs", source_type="internal")
        ],
        research_iterations=0,
    )

    with patch("app.api.query.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_state

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query/agent",
                json={"query": "What is Python?"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Python is a programming language."
        assert len(data["sources"]) == 1
        assert data["research_iterations"] == 0


@pytest.mark.asyncio
async def test_agentic_query_with_research(auth_headers):
    """Test endpoint shows when external research was performed."""
    mock_state = AgentState(
        query="Latest Python news?",
        final_answer="Python 3.13 was released.",
        sources=[
            SourceReference(title="Python.org", source_type="external", url="https://python.org")
        ],
        research_iterations=1,
    )

    with patch("app.api.query.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_state

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query/agent",
                json={"query": "Latest Python news?"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["research_iterations"] == 1
        assert data["sources"][0]["source_type"] == "external"


@pytest.mark.asyncio
async def test_agentic_query_with_error(auth_headers):
    """Test endpoint handles errors from the agent."""
    mock_state = AgentState(
        query="What is Python?",
        error="Something went wrong",
        research_iterations=0,
    )

    with patch("app.api.query.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_state

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query/agent",
                json={"query": "What is Python?"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert "Error" in data["answer"]
        assert data["error"] == "Something went wrong"


@pytest.mark.asyncio
async def test_agentic_query_custom_max_iterations(auth_headers):
    """Test endpoint respects max_iterations parameter."""
    mock_state = AgentState(
        query="Complex question",
        final_answer="Found answer after research.",
        sources=[],
        research_iterations=2,
    )

    with patch("app.api.query.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_state

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query/agent",
                json={"query": "Complex question", "max_iterations": 5},
                headers=auth_headers,
            )

        # Verify max_iterations was passed to run_agent
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["max_iterations"] == 5

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_agentic_query_requires_auth():
    """Test endpoint requires authentication."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/query/agent",
            json={"query": "What is Python?"},
        )

    assert response.status_code == 401
