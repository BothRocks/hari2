"""Tests for query generator with RAG response generation."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.query.generator import generate_response, RESPONSE_PROMPT


def test_response_prompt_exists():
    """Test RESPONSE_PROMPT constant exists."""
    assert RESPONSE_PROMPT is not None
    assert isinstance(RESPONSE_PROMPT, str)
    assert len(RESPONSE_PROMPT) > 0


def test_response_prompt_contains_context():
    """Test RESPONSE_PROMPT contains 'context' placeholder."""
    assert "{context}" in RESPONSE_PROMPT
    assert "{question}" in RESPONSE_PROMPT


def test_response_prompt_structure():
    """Test RESPONSE_PROMPT has expected structure."""
    assert "HARI" in RESPONSE_PROMPT
    assert "CONTEXT:" in RESPONSE_PROMPT
    assert "USER QUESTION:" in RESPONSE_PROMPT
    assert "Instructions:" in RESPONSE_PROMPT


@pytest.mark.asyncio
async def test_generate_response_with_context_and_question():
    """Test generate_response with valid context and question."""
    # Setup mock LLM client
    mock_client = Mock()
    mock_client.complete = AsyncMock(return_value={
        "content": "This is a test answer based on the context.",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 100,
        "output_tokens": 50,
    })

    # Test data
    context = [
        {
            "id": "doc1",
            "title": "Test Document 1",
            "url": "https://example.com/doc1",
            "quick_summary": "Summary of document 1",
            "summary": "Full summary of document 1",
        },
        {
            "id": "doc2",
            "title": "Test Document 2",
            "url": "https://example.com/doc2",
            "quick_summary": "Summary of document 2",
        },
    ]

    question = "What is the main topic?"

    # Execute
    result = await generate_response(
        question=question,
        context=context,
        llm_client=mock_client,
    )

    # Verify response structure
    assert "answer" in result
    assert "sources" in result
    assert "llm_metadata" in result

    # Verify answer
    assert result["answer"] == "This is a test answer based on the context."

    # Verify sources
    assert len(result["sources"]) == 2
    assert result["sources"][0]["id"] == "doc1"
    assert result["sources"][0]["title"] == "Test Document 1"
    assert result["sources"][0]["url"] == "https://example.com/doc1"

    # Verify LLM metadata
    assert result["llm_metadata"]["provider"] == "anthropic"
    assert result["llm_metadata"]["model"] == "claude-sonnet-4-20250514"

    # Verify LLM client was called
    mock_client.complete.assert_called_once()


@pytest.mark.asyncio
async def test_generate_response_formats_context_correctly():
    """Test generate_response formats context correctly."""
    # Setup mock LLM client
    mock_client = Mock()
    mock_client.complete = AsyncMock(return_value={
        "content": "Answer",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
    })

    # Test data with quick_summary
    context = [
        {
            "id": "doc1",
            "title": "Document 1",
            "quick_summary": "Quick summary text",
            "summary": "Full summary text",
        }
    ]

    question = "Test question?"

    # Execute
    await generate_response(
        question=question,
        context=context,
        llm_client=mock_client,
    )

    # Get the call arguments
    call_args = mock_client.complete.call_args
    prompt = call_args.kwargs["prompt"]

    # Verify context formatting
    assert "[Document 1]" in prompt
    assert "Quick summary text" in prompt
    # Should use quick_summary, not full summary
    assert "Full summary text" not in prompt
    assert question in prompt


@pytest.mark.asyncio
async def test_generate_response_formats_context_with_summary_fallback():
    """Test generate_response falls back to summary when quick_summary missing."""
    # Setup mock LLM client
    mock_client = Mock()
    mock_client.complete = AsyncMock(return_value={
        "content": "Answer",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
    })

    # Test data without quick_summary
    context = [
        {
            "id": "doc1",
            "title": "Document 1",
            "summary": "Full summary text",
        }
    ]

    question = "Test question?"

    # Execute
    await generate_response(
        question=question,
        context=context,
        llm_client=mock_client,
    )

    # Get the call arguments
    call_args = mock_client.complete.call_args
    prompt = call_args.kwargs["prompt"]

    # Verify fallback to summary
    assert "Full summary text" in prompt


@pytest.mark.asyncio
async def test_generate_response_with_empty_context():
    """Test generate_response handles empty context."""
    # Setup mock LLM client
    mock_client = Mock()
    mock_client.complete = AsyncMock(return_value={
        "content": "I don't have enough context to answer that question.",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
    })

    # Empty context
    context = []
    question = "What is the answer?"

    # Execute
    result = await generate_response(
        question=question,
        context=context,
        llm_client=mock_client,
    )

    # Verify response
    assert "answer" in result
    assert result["sources"] == []

    # Verify LLM was called with "No relevant documents found."
    call_args = mock_client.complete.call_args
    prompt = call_args.kwargs["prompt"]
    assert "No relevant documents found." in prompt


@pytest.mark.asyncio
async def test_generate_response_handles_llm_errors():
    """Test generate_response handles LLM errors gracefully."""
    # Setup mock LLM client that raises error
    mock_client = Mock()
    mock_client.complete = AsyncMock(side_effect=Exception("API error"))

    context = [{"id": "doc1", "title": "Test", "quick_summary": "Summary"}]
    question = "Test question?"

    # Execute
    result = await generate_response(
        question=question,
        context=context,
        llm_client=mock_client,
    )

    # Verify error is returned
    assert "error" in result
    assert result["error"] == "API error"


@pytest.mark.asyncio
async def test_generate_response_sources_include_required_fields():
    """Test sources include id, title, url from context documents."""
    # Setup mock LLM client
    mock_client = Mock()
    mock_client.complete = AsyncMock(return_value={
        "content": "Answer",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
    })

    # Test data with all source fields
    context = [
        {
            "id": "doc1",
            "title": "Title 1",
            "url": "https://example.com/1",
            "quick_summary": "Summary 1",
        },
        {
            "id": "doc2",
            "title": "Title 2",
            "url": "https://example.com/2",
            "quick_summary": "Summary 2",
        },
    ]

    question = "Test?"

    # Execute
    result = await generate_response(
        question=question,
        context=context,
        llm_client=mock_client,
    )

    # Verify sources structure
    assert len(result["sources"]) == 2

    # Check first source
    source1 = result["sources"][0]
    assert "id" in source1
    assert "title" in source1
    assert "url" in source1
    assert source1["id"] == "doc1"
    assert source1["title"] == "Title 1"
    assert source1["url"] == "https://example.com/1"

    # Check second source
    source2 = result["sources"][1]
    assert source2["id"] == "doc2"
    assert source2["title"] == "Title 2"
    assert source2["url"] == "https://example.com/2"


@pytest.mark.asyncio
async def test_generate_response_sources_handle_missing_fields():
    """Test sources handle missing fields gracefully."""
    # Setup mock LLM client
    mock_client = Mock()
    mock_client.complete = AsyncMock(return_value={
        "content": "Answer",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
    })

    # Test data with missing fields
    context = [
        {
            "id": "doc1",
            # missing title and url
            "quick_summary": "Summary",
        }
    ]

    question = "Test?"

    # Execute
    result = await generate_response(
        question=question,
        context=context,
        llm_client=mock_client,
    )

    # Verify sources still work with None values
    assert len(result["sources"]) == 1
    assert result["sources"][0]["id"] == "doc1"
    assert result["sources"][0]["title"] is None
    assert result["sources"][0]["url"] is None


@pytest.mark.asyncio
async def test_generate_response_uses_default_llm_client():
    """Test generate_response creates default LLMClient if none provided."""
    with patch("app.services.query.generator.LLMClient") as mock_llm_class:
        # Setup mock
        mock_client = Mock()
        mock_client.complete = AsyncMock(return_value={
            "content": "Answer",
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
        })
        mock_llm_class.return_value = mock_client

        context = [{"id": "doc1", "title": "Test", "quick_summary": "Summary"}]
        question = "Test?"

        # Execute without providing llm_client
        result = await generate_response(
            question=question,
            context=context,
        )

        # Verify default client was created
        mock_llm_class.assert_called_once()
        assert "answer" in result


@pytest.mark.asyncio
async def test_generate_response_llm_call_parameters():
    """Test generate_response calls LLM with correct parameters."""
    # Setup mock LLM client
    mock_client = Mock()
    mock_client.complete = AsyncMock(return_value={
        "content": "Answer",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
    })

    context = [{"id": "doc1", "title": "Test", "quick_summary": "Summary"}]
    question = "Test?"

    # Execute
    await generate_response(
        question=question,
        context=context,
        llm_client=mock_client,
    )

    # Verify LLM client call parameters
    call_args = mock_client.complete.call_args
    assert call_args.kwargs["system"] == "You are HARI, a helpful knowledge assistant."
    assert call_args.kwargs["max_tokens"] == 1000
    assert call_args.kwargs["temperature"] == 0.7
    assert "prompt" in call_args.kwargs


@pytest.mark.asyncio
async def test_generate_response_untitled_fallback():
    """Test generate_response uses 'Untitled' when title is missing."""
    # Setup mock LLM client
    mock_client = Mock()
    mock_client.complete = AsyncMock(return_value={
        "content": "Answer",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
    })

    # Context without title
    context = [
        {
            "id": "doc1",
            "quick_summary": "Summary without title",
        }
    ]

    question = "Test?"

    # Execute
    await generate_response(
        question=question,
        context=context,
        llm_client=mock_client,
    )

    # Get the call arguments
    call_args = mock_client.complete.call_args
    prompt = call_args.kwargs["prompt"]

    # Verify 'Untitled' is used
    assert "[Untitled]" in prompt


@pytest.mark.asyncio
async def test_generate_response_multiple_documents_formatting():
    """Test generate_response formats multiple documents with proper separation."""
    # Setup mock LLM client
    mock_client = Mock()
    mock_client.complete = AsyncMock(return_value={
        "content": "Answer",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
    })

    # Multiple documents
    context = [
        {"id": "doc1", "title": "Doc 1", "quick_summary": "Summary 1"},
        {"id": "doc2", "title": "Doc 2", "quick_summary": "Summary 2"},
        {"id": "doc3", "title": "Doc 3", "quick_summary": "Summary 3"},
    ]

    question = "Test?"

    # Execute
    await generate_response(
        question=question,
        context=context,
        llm_client=mock_client,
    )

    # Get the call arguments
    call_args = mock_client.complete.call_args
    prompt = call_args.kwargs["prompt"]

    # Verify all documents are included with proper formatting
    assert "[Doc 1]" in prompt
    assert "Summary 1" in prompt
    assert "[Doc 2]" in prompt
    assert "Summary 2" in prompt
    assert "[Doc 3]" in prompt
    assert "Summary 3" in prompt

    # Verify documents are separated (double newline)
    assert "\n\n" in prompt
