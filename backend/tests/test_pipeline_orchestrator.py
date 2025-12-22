"""Tests for DocumentPipeline orchestrator."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.pipeline.orchestrator import DocumentPipeline


# Test 1: Pipeline initialization
def test_pipeline_initialization():
    """Test that DocumentPipeline can be instantiated."""
    pipeline = DocumentPipeline()
    assert pipeline is not None
    assert hasattr(pipeline, "process_url")
    assert hasattr(pipeline, "process_pdf")
    assert hasattr(pipeline, "_process_text")


# Test 2: Successful URL processing (short text path)
@pytest.mark.asyncio
async def test_process_url_success_short_text():
    """Test successful URL processing with short text (no extractive summary)."""
    pipeline = DocumentPipeline()

    # Mock fetch_url_content
    mock_fetch_result = {
        "text": "This is a short article about technology.",
        "metadata": {"title": "Tech Article", "author": "John Doe"},
        "url": "https://example.com/article",
    }

    # Mock synthesis response
    mock_synthesis = {
        "summary": "A comprehensive summary about technology and its impact on society.",
        "quick_summary": "Technology article summary.",
        "keywords": ["technology", "innovation", "digital"],
        "industries": ["technology", "software"],
        "language": "en",
        "llm_metadata": {
            "provider": "anthropic",
            "model": "claude-sonnet-4",
            "input_tokens": 100,
            "output_tokens": 50,
        },
    }

    # Mock embedding
    mock_embedding = [0.1] * 1536

    with patch(
        "app.services.pipeline.orchestrator.fetch_url_content",
        AsyncMock(return_value=mock_fetch_result),
    ), patch(
        "app.services.pipeline.orchestrator.synthesize_document",
        AsyncMock(return_value=mock_synthesis),
    ), patch(
        "app.services.pipeline.orchestrator.generate_embedding",
        AsyncMock(return_value=mock_embedding),
    ):
        result = await pipeline.process_url("https://example.com/article")

    assert result["status"] == "completed"
    assert result["content"] == "This is a short article about technology."
    assert "content_hash" in result
    assert len(result["content_hash"]) == 64  # SHA256 hex
    assert result["title"] == "Tech Article"
    assert result["summary"] == mock_synthesis["summary"]
    assert result["quick_summary"] == mock_synthesis["quick_summary"]
    assert result["keywords"] == mock_synthesis["keywords"]
    assert result["industries"] == mock_synthesis["industries"]
    assert result["language"] == "en"
    assert result["embedding"] == mock_embedding
    assert result["quality_score"] > 0
    assert result["token_count"] > 0
    assert result["llm_metadata"] == mock_synthesis["llm_metadata"]


# Test 3: Successful URL processing (long text path with extractive summary)
@pytest.mark.asyncio
async def test_process_url_success_long_text():
    """Test URL processing with long text that triggers extractive summarization."""
    pipeline = DocumentPipeline()

    # Create long text (>2000 tokens)
    long_text = "Long article content. " * 2000  # ~4000 tokens

    mock_fetch_result = {
        "text": long_text,
        "metadata": {"title": "Long Article"},
        "url": "https://example.com/long",
    }

    mock_synthesis = {
        "summary": "A summary of the long article.",
        "quick_summary": "Brief summary.",
        "keywords": ["long", "article"],
        "industries": ["publishing"],
        "language": "en",
        "llm_metadata": {"provider": "anthropic", "model": "claude", "input_tokens": 100, "output_tokens": 50},
    }

    mock_embedding = [0.2] * 1536

    # Track if extractive_summarize was called
    extractive_called = False

    def mock_extractive(text, sentence_count=10, language="english"):
        nonlocal extractive_called
        extractive_called = True
        return text[:1000]  # Return truncated

    with patch(
        "app.services.pipeline.orchestrator.fetch_url_content",
        AsyncMock(return_value=mock_fetch_result),
    ), patch(
        "app.services.pipeline.orchestrator.extractive_summarize",
        side_effect=mock_extractive,
    ), patch(
        "app.services.pipeline.orchestrator.synthesize_document",
        AsyncMock(return_value=mock_synthesis),
    ), patch(
        "app.services.pipeline.orchestrator.generate_embedding",
        AsyncMock(return_value=mock_embedding),
    ):
        result = await pipeline.process_url("https://example.com/long")

    assert result["status"] == "completed"
    assert extractive_called  # Verify extractive summary was used
    assert result["token_count"] > 2000


# Test 4: Successful PDF processing
@pytest.mark.asyncio
async def test_process_pdf_success():
    """Test successful PDF processing."""
    pipeline = DocumentPipeline()

    mock_pdf_content = b"%PDF-1.4 fake pdf content"

    mock_extract_result = {
        "text": "PDF text content about business.",
        "page_count": 5,
        "metadata": {"title": "Business Report", "author": "Jane Smith"},
    }

    mock_synthesis = {
        "summary": "A business report summary.",
        "quick_summary": "Brief business summary.",
        "keywords": ["business", "report"],
        "industries": ["finance"],
        "language": "en",
        "llm_metadata": {"provider": "anthropic", "model": "claude", "input_tokens": 100, "output_tokens": 50},
    }

    mock_embedding = [0.3] * 1536

    with patch(
        "app.services.pipeline.orchestrator.extract_text_from_pdf",
        AsyncMock(return_value=mock_extract_result),
    ), patch(
        "app.services.pipeline.orchestrator.synthesize_document",
        AsyncMock(return_value=mock_synthesis),
    ), patch(
        "app.services.pipeline.orchestrator.generate_embedding",
        AsyncMock(return_value=mock_embedding),
    ):
        result = await pipeline.process_pdf(mock_pdf_content, filename="report.pdf")

    assert result["status"] == "completed"
    assert result["content"] == "PDF text content about business."
    assert result["title"] == "Business Report"
    assert result["summary"] == mock_synthesis["summary"]
    assert result["embedding"] == mock_embedding


# Test 5: Error handling - fetch fails
@pytest.mark.asyncio
async def test_process_url_fetch_error():
    """Test error handling when URL fetch fails."""
    pipeline = DocumentPipeline()

    mock_fetch_result = {
        "text": "",
        "error": "HTTP error: 404",
    }

    with patch(
        "app.services.pipeline.orchestrator.fetch_url_content",
        AsyncMock(return_value=mock_fetch_result),
    ):
        result = await pipeline.process_url("https://example.com/notfound")

    assert result["status"] == "failed"
    assert "error" in result
    assert "404" in result["error"]


# Test 6: Error handling - PDF extraction fails
@pytest.mark.asyncio
async def test_process_pdf_extract_error():
    """Test error handling when PDF extraction fails."""
    pipeline = DocumentPipeline()

    mock_extract_result = {
        "text": "",
        "error": "Invalid PDF format",
    }

    with patch(
        "app.services.pipeline.orchestrator.extract_text_from_pdf",
        AsyncMock(return_value=mock_extract_result),
    ):
        result = await pipeline.process_pdf(b"bad pdf", filename="bad.pdf")

    assert result["status"] == "failed"
    assert "error" in result
    assert "Invalid PDF format" in result["error"]


# Test 7: Error handling - no content extracted (empty text after cleaning)
@pytest.mark.asyncio
async def test_process_url_no_content():
    """Test error handling when no content remains after cleaning."""
    pipeline = DocumentPipeline()

    mock_fetch_result = {
        "text": "   \n\n  \t  ",  # Only whitespace
        "metadata": {},
        "url": "https://example.com/empty",
    }

    with patch(
        "app.services.pipeline.orchestrator.fetch_url_content",
        AsyncMock(return_value=mock_fetch_result),
    ):
        result = await pipeline.process_url("https://example.com/empty")

    assert result["status"] == "failed"
    assert "error" in result
    assert "No content extracted" in result["error"]


# Test 8: Error handling - LLM synthesis fails
@pytest.mark.asyncio
async def test_process_url_synthesis_error():
    """Test error handling when LLM synthesis fails."""
    pipeline = DocumentPipeline()

    mock_fetch_result = {
        "text": "Some article content.",
        "metadata": {"title": "Article"},
        "url": "https://example.com/article",
    }

    mock_synthesis = {
        "error": "LLM API error: Rate limit exceeded",
    }

    with patch(
        "app.services.pipeline.orchestrator.fetch_url_content",
        AsyncMock(return_value=mock_fetch_result),
    ), patch(
        "app.services.pipeline.orchestrator.synthesize_document",
        AsyncMock(return_value=mock_synthesis),
    ):
        result = await pipeline.process_url("https://example.com/article")

    assert result["status"] == "failed"
    assert "error" in result
    assert "Rate limit exceeded" in result["error"]


# Test 9: Content hash generation
@pytest.mark.asyncio
async def test_content_hash_generation():
    """Test that content hash is correctly generated."""
    pipeline = DocumentPipeline()

    mock_fetch_result = {
        "text": "Unique content for hashing.",
        "metadata": {},
        "url": "https://example.com/test",
    }

    mock_synthesis = {
        "summary": "Summary",
        "quick_summary": "Quick",
        "keywords": ["test"],
        "industries": ["tech"],
        "language": "en",
        "llm_metadata": {"provider": "anthropic", "model": "claude", "input_tokens": 10, "output_tokens": 5},
    }

    with patch(
        "app.services.pipeline.orchestrator.fetch_url_content",
        AsyncMock(return_value=mock_fetch_result),
    ), patch(
        "app.services.pipeline.orchestrator.synthesize_document",
        AsyncMock(return_value=mock_synthesis),
    ), patch(
        "app.services.pipeline.orchestrator.generate_embedding",
        AsyncMock(return_value=None),
    ):
        result1 = await pipeline.process_url("https://example.com/test")
        result2 = await pipeline.process_url("https://example.com/test")

    # Same content should produce same hash
    assert result1["content_hash"] == result2["content_hash"]
    assert len(result1["content_hash"]) == 64  # SHA256 produces 64 hex chars


# Test 10: Title fallback from synthesis when metadata title is missing
@pytest.mark.asyncio
async def test_title_fallback_to_synthesis():
    """Test that title falls back to synthesis when metadata title is missing."""
    pipeline = DocumentPipeline()

    mock_fetch_result = {
        "text": "Article without metadata title.",
        "metadata": {},  # No title in metadata
        "url": "https://example.com/notitle",
    }

    mock_synthesis = {
        "title": "Generated Title from LLM",
        "summary": "Summary",
        "quick_summary": "Quick",
        "keywords": ["test"],
        "industries": ["tech"],
        "language": "en",
        "llm_metadata": {"provider": "anthropic", "model": "claude", "input_tokens": 10, "output_tokens": 5},
    }

    with patch(
        "app.services.pipeline.orchestrator.fetch_url_content",
        AsyncMock(return_value=mock_fetch_result),
    ), patch(
        "app.services.pipeline.orchestrator.synthesize_document",
        AsyncMock(return_value=mock_synthesis),
    ), patch(
        "app.services.pipeline.orchestrator.generate_embedding",
        AsyncMock(return_value=None),
    ):
        result = await pipeline.process_url("https://example.com/notitle")

    assert result["title"] == "Generated Title from LLM"


# Test 11: Embedding failure doesn't break pipeline
@pytest.mark.asyncio
async def test_embedding_failure_handled():
    """Test that embedding failure is handled gracefully."""
    pipeline = DocumentPipeline()

    mock_fetch_result = {
        "text": "Article content.",
        "metadata": {"title": "Test"},
        "url": "https://example.com/test",
    }

    mock_synthesis = {
        "summary": "Summary",
        "quick_summary": "Quick",
        "keywords": ["test"],
        "industries": ["tech"],
        "language": "en",
        "llm_metadata": {"provider": "anthropic", "model": "claude", "input_tokens": 10, "output_tokens": 5},
    }

    with patch(
        "app.services.pipeline.orchestrator.fetch_url_content",
        AsyncMock(return_value=mock_fetch_result),
    ), patch(
        "app.services.pipeline.orchestrator.synthesize_document",
        AsyncMock(return_value=mock_synthesis),
    ), patch(
        "app.services.pipeline.orchestrator.generate_embedding",
        AsyncMock(return_value=None),  # Embedding fails
    ):
        result = await pipeline.process_url("https://example.com/test")

    assert result["status"] == "completed"
    assert result["embedding"] is None
    # Quality score should still be calculated (just lower without embedding)
    assert result["quality_score"] >= 0
