"""Tests for author detection in document pipeline."""
import pytest
from unittest.mock import patch, AsyncMock

from app.services.pipeline.orchestrator import DocumentPipeline, is_generic_author


class TestIsGenericAuthor:
    """Tests for the is_generic_author helper function."""

    def test_none_is_generic(self):
        assert is_generic_author(None) is True

    def test_empty_string_is_generic(self):
        assert is_generic_author("") is True
        assert is_generic_author("   ") is True

    def test_known_generic_values(self):
        generic_values = [
            "admin", "Admin", "ADMIN",
            "unknown", "Unknown",
            "anonymous", "Anonymous",
            "user", "User",
            "editor", "Editor",
            "author", "Author",
            "n/a", "N/A", "NA", "na",
            "none", "None",
            "staff", "Staff",
            "contributor", "Contributor",
            "writer", "Writer",
            "guest", "Guest",
        ]
        for value in generic_values:
            assert is_generic_author(value) is True, f"Expected '{value}' to be generic"

    def test_real_names_not_generic(self):
        real_names = [
            "John Smith",
            "Jane Doe",
            "Dr. Maria Garcia",
            "Bob Johnson Jr.",
            "Alice",
        ]
        for name in real_names:
            assert is_generic_author(name) is False, f"Expected '{name}' to NOT be generic"


@pytest.mark.asyncio
async def test_llm_author_used_when_trafilatura_returns_none():
    """LLM-extracted author should be used when trafilatura returns None."""
    pipeline = DocumentPipeline()

    # Mock URL fetcher returning no author
    mock_url_result = {
        "text": "Article by John Smith. This is the content about technology trends.",
        "metadata": {"title": "Test Article", "author": None, "date": None},
        "url": "https://example.com/article",
    }

    # Mock synthesizer returning author from content
    mock_synthesis = {
        "title": "Test Article",
        "author": "John Smith",
        "summary": "This is a test summary about technology trends and their impact.",
        "quick_summary": "Quick summary about tech.",
        "keywords": ["technology", "trends"],
        "industries": ["tech"],
        "language": "en",
        "llm_metadata": {},
    }

    # Mock validator returning no corrections needed
    mock_validation = {
        "needs_review": False,
        "review_reasons": [],
    }

    with patch("app.services.pipeline.orchestrator.fetch_url_content", new=AsyncMock(return_value=mock_url_result)):
        with patch("app.services.pipeline.orchestrator.synthesize_document", new=AsyncMock(return_value=mock_synthesis)):
            with patch("app.services.pipeline.orchestrator.validate_and_correct", new=AsyncMock(return_value=mock_validation)):
                with patch("app.services.pipeline.orchestrator.generate_embedding", new=AsyncMock(return_value=[0.1] * 1536)):
                    result = await pipeline.process_url("https://example.com/article")

    assert result.get("author") == "John Smith"


@pytest.mark.asyncio
async def test_trafilatura_author_preferred_when_valid():
    """Trafilatura author should be preferred when it's a real name."""
    pipeline = DocumentPipeline()

    # Mock URL fetcher returning valid author
    mock_url_result = {
        "text": "Content here about important topics.",
        "metadata": {"title": "Test Article", "author": "Jane Doe", "date": None},
        "url": "https://example.com/article",
    }

    mock_synthesis = {
        "title": "Test Article",
        "author": "Unknown Author",  # LLM couldn't find it
        "summary": "This is a summary of the content about important topics.",
        "quick_summary": "Quick summary.",
        "keywords": ["test", "topics"],
        "industries": [],
        "language": "en",
        "llm_metadata": {},
    }

    mock_validation = {
        "needs_review": False,
        "review_reasons": [],
    }

    with patch("app.services.pipeline.orchestrator.fetch_url_content", new=AsyncMock(return_value=mock_url_result)):
        with patch("app.services.pipeline.orchestrator.synthesize_document", new=AsyncMock(return_value=mock_synthesis)):
            with patch("app.services.pipeline.orchestrator.validate_and_correct", new=AsyncMock(return_value=mock_validation)):
                with patch("app.services.pipeline.orchestrator.generate_embedding", new=AsyncMock(return_value=[0.1] * 1536)):
                    result = await pipeline.process_url("https://example.com/article")

    # Trafilatura author should be used since it's a real name
    assert result.get("author") == "Jane Doe"


@pytest.mark.asyncio
async def test_llm_author_used_when_trafilatura_returns_generic():
    """LLM author should be used when trafilatura returns a generic value."""
    pipeline = DocumentPipeline()

    # Mock URL fetcher returning generic author
    mock_url_result = {
        "text": "Article written by Sarah Johnson about climate change.",
        "metadata": {"title": "Climate Report", "author": "admin", "date": None},
        "url": "https://example.com/article",
    }

    mock_synthesis = {
        "title": "Climate Report",
        "author": "Sarah Johnson",  # LLM found real author
        "summary": "A comprehensive report about climate change and its effects.",
        "quick_summary": "Climate change report.",
        "keywords": ["climate", "environment"],
        "industries": ["environment"],
        "language": "en",
        "llm_metadata": {},
    }

    mock_validation = {
        "needs_review": False,
        "review_reasons": [],
    }

    with patch("app.services.pipeline.orchestrator.fetch_url_content", new=AsyncMock(return_value=mock_url_result)):
        with patch("app.services.pipeline.orchestrator.synthesize_document", new=AsyncMock(return_value=mock_synthesis)):
            with patch("app.services.pipeline.orchestrator.validate_and_correct", new=AsyncMock(return_value=mock_validation)):
                with patch("app.services.pipeline.orchestrator.generate_embedding", new=AsyncMock(return_value=[0.1] * 1536)):
                    result = await pipeline.process_url("https://example.com/article")

    # LLM author should be used since trafilatura returned generic "admin"
    assert result.get("author") == "Sarah Johnson"


@pytest.mark.asyncio
async def test_both_generic_returns_none():
    """When both sources return generic values, author should be None."""
    pipeline = DocumentPipeline()

    mock_url_result = {
        "text": "Some article content without clear authorship.",
        "metadata": {"title": "Mystery Article", "author": "unknown", "date": None},
        "url": "https://example.com/article",
    }

    mock_synthesis = {
        "title": "Mystery Article",
        "author": "Staff",  # Also generic
        "summary": "An article with unclear authorship about various topics.",
        "quick_summary": "Unclear authorship article.",
        "keywords": ["article"],
        "industries": [],
        "language": "en",
        "llm_metadata": {},
    }

    mock_validation = {
        "needs_review": False,
        "review_reasons": [],
    }

    with patch("app.services.pipeline.orchestrator.fetch_url_content", new=AsyncMock(return_value=mock_url_result)):
        with patch("app.services.pipeline.orchestrator.synthesize_document", new=AsyncMock(return_value=mock_synthesis)):
            with patch("app.services.pipeline.orchestrator.validate_and_correct", new=AsyncMock(return_value=mock_validation)):
                with patch("app.services.pipeline.orchestrator.generate_embedding", new=AsyncMock(return_value=[0.1] * 1536)):
                    result = await pipeline.process_url("https://example.com/article")

    # Both are generic, so author should be None
    assert result.get("author") is None


@pytest.mark.asyncio
async def test_validation_corrected_author_takes_precedence():
    """Validator-corrected author should take precedence over both sources."""
    pipeline = DocumentPipeline()

    mock_url_result = {
        "text": "Article by Dr. Robert Chen about AI research.",
        "metadata": {"title": "AI Research", "author": "admin", "date": None},
        "url": "https://example.com/article",
    }

    mock_synthesis = {
        "title": "AI Research",
        "author": "Unknown",  # Generic
        "summary": "Research article about artificial intelligence advances.",
        "quick_summary": "AI research article.",
        "keywords": ["AI", "research"],
        "industries": ["tech"],
        "language": "en",
        "llm_metadata": {},
    }

    # Validator found and corrected the author
    mock_validation = {
        "needs_review": True,
        "review_reasons": ["author_auto_corrected"],
        "author": "Dr. Robert Chen",
        "original_metadata": {"author": "Unknown"},
    }

    with patch("app.services.pipeline.orchestrator.fetch_url_content", new=AsyncMock(return_value=mock_url_result)):
        with patch("app.services.pipeline.orchestrator.synthesize_document", new=AsyncMock(return_value=mock_synthesis)):
            with patch("app.services.pipeline.orchestrator.validate_and_correct", new=AsyncMock(return_value=mock_validation)):
                with patch("app.services.pipeline.orchestrator.generate_embedding", new=AsyncMock(return_value=[0.1] * 1536)):
                    result = await pipeline.process_url("https://example.com/article")

    # Validator-corrected author should be used
    assert result.get("author") == "Dr. Robert Chen"
