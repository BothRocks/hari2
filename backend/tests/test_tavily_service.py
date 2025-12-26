"""Tests for Tavily web search service."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.tavily import TavilyService, TavilyResult


def test_tavily_result_schema():
    """Test TavilyResult schema."""
    result = TavilyResult(
        title="Python Official Site",
        url="https://python.org",
        content="Python is a programming language...",
        score=0.95,
    )
    assert result.title == "Python Official Site"
    assert result.score == 0.95


@pytest.mark.asyncio
async def test_tavily_service_search():
    """Test Tavily search returns formatted results."""
    mock_response = {
        "results": [
            {
                "title": "Result 1",
                "url": "https://example.com/1",
                "content": "Content 1",
                "score": 0.9,
            },
            {
                "title": "Result 2",
                "url": "https://example.com/2",
                "content": "Content 2",
                "score": 0.8,
            },
        ]
    }

    with patch("app.services.tavily.TavilyClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.search = MagicMock(return_value=mock_response)

        service = TavilyService(api_key="test-key")
        results = await service.search("test query", max_results=5)

        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[0].score == 0.9


@pytest.mark.asyncio
async def test_tavily_service_handles_no_api_key():
    """Test Tavily service raises when no API key."""
    with patch("app.services.tavily.settings") as mock_settings:
        mock_settings.tavily_api_key = None
        service = TavilyService(api_key=None)

        with pytest.raises(ValueError, match="Tavily API key not configured"):
            await service.search("test query")
