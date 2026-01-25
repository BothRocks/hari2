"""Tests for document synthesizer."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.pipeline.synthesizer import (
    SYNTHESIS_PROMPT,
    synthesize_document,
)


# Test 1: SYNTHESIS_PROMPT validation
def test_synthesis_prompt_exists():
    """Test that SYNTHESIS_PROMPT constant exists and has required fields."""
    assert SYNTHESIS_PROMPT is not None
    assert "summary" in SYNTHESIS_PROMPT.lower()
    assert "keywords" in SYNTHESIS_PROMPT.lower()


def test_synthesis_prompt_format():
    """Test that SYNTHESIS_PROMPT has required format markers."""
    assert "{text}" in SYNTHESIS_PROMPT
    assert "json" in SYNTHESIS_PROMPT.lower()
    # Check for expected fields in the JSON template
    assert "quick_summary" in SYNTHESIS_PROMPT.lower()
    assert "industries" in SYNTHESIS_PROMPT.lower()
    assert "language" in SYNTHESIS_PROMPT.lower()


# Test 2: Successful synthesis with valid LLM response
@pytest.mark.asyncio
async def test_synthesize_document_success():
    """Test successful document synthesis with valid LLM response."""
    mock_llm_response = {
        "content": json.dumps({
            "summary": "This is a comprehensive summary of the document covering main points and insights.",
            "quick_summary": "A brief executive summary.",
            "keywords": ["keyword1", "keyword2", "keyword3"],
            "industries": ["technology", "software"],
            "language": "en"
        }),
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 100,
        "output_tokens": 50,
    }

    mock_client = MagicMock()
    mock_client.complete = AsyncMock(return_value=mock_llm_response)

    result = await synthesize_document(
        text="This is a test document with some content.",
        llm_client=mock_client
    )

    # Verify the result structure
    assert "summary" in result
    assert "quick_summary" in result
    assert "keywords" in result
    assert isinstance(result["keywords"], list)
    assert "industries" in result
    assert "language" in result
    assert result["language"] == "en"

    # Verify LLM metadata is included
    assert "llm_metadata" in result
    assert result["llm_metadata"]["provider"] == "anthropic"
    assert result["llm_metadata"]["model"] == "claude-sonnet-4-20250514"
    assert result["llm_metadata"]["input_tokens"] == 100
    assert result["llm_metadata"]["output_tokens"] == 50

    # Verify LLM client was called
    mock_client.complete.assert_called_once()
    call_kwargs = mock_client.complete.call_args.kwargs
    assert "prompt" in call_kwargs
    assert "system" in call_kwargs
    assert call_kwargs["max_tokens"] == 1500
    assert call_kwargs["temperature"] == 0.3


# Test 3: JSON extraction from markdown code blocks
@pytest.mark.asyncio
async def test_synthesize_document_with_markdown_json():
    """Test JSON extraction from markdown code blocks."""
    json_content = {
        "summary": "Test summary",
        "quick_summary": "Quick test",
        "keywords": ["test"],
        "industries": ["testing"],
        "language": "en"
    }

    # Test with ```json wrapper
    mock_llm_response = {
        "content": f"```json\n{json.dumps(json_content)}\n```",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 100,
        "output_tokens": 50,
    }

    mock_client = MagicMock()
    mock_client.complete = AsyncMock(return_value=mock_llm_response)

    result = await synthesize_document(
        text="Test document",
        llm_client=mock_client
    )

    assert "summary" in result
    assert result["summary"] == "Test summary"
    assert "error" not in result


@pytest.mark.asyncio
async def test_synthesize_document_with_plain_markdown():
    """Test JSON extraction from plain markdown code blocks."""
    json_content = {
        "summary": "Test summary",
        "quick_summary": "Quick test",
        "keywords": ["test"],
        "industries": ["testing"],
        "language": "en"
    }

    # Test with ``` wrapper (no language specified)
    mock_llm_response = {
        "content": f"```\n{json.dumps(json_content)}\n```",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 100,
        "output_tokens": 50,
    }

    mock_client = MagicMock()
    mock_client.complete = AsyncMock(return_value=mock_llm_response)

    result = await synthesize_document(
        text="Test document",
        llm_client=mock_client
    )

    assert "summary" in result
    assert result["summary"] == "Test summary"
    assert "error" not in result


# Test 4: Empty/None text handling
@pytest.mark.asyncio
async def test_synthesize_document_empty_text():
    """Test handling of empty text input."""
    result = await synthesize_document(text="")

    assert "error" in result
    assert result["error"] == "No text provided"


@pytest.mark.asyncio
async def test_synthesize_document_none_text():
    """Test handling of None text input."""
    result = await synthesize_document(text=None)

    assert "error" in result
    assert result["error"] == "No text provided"


# Test 5: JSON parsing error handling
@pytest.mark.asyncio
async def test_synthesize_document_invalid_json():
    """Test handling of invalid JSON response from LLM."""
    mock_llm_response = {
        "content": "This is not valid JSON {invalid}",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 100,
        "output_tokens": 50,
    }

    mock_client = MagicMock()
    mock_client.complete = AsyncMock(return_value=mock_llm_response)

    result = await synthesize_document(
        text="Test document",
        llm_client=mock_client
    )

    assert "error" in result
    assert "Failed to parse LLM response" in result["error"]


# Test 6: General exception handling
@pytest.mark.asyncio
async def test_synthesize_document_llm_exception():
    """Test handling of LLM client exceptions."""
    mock_client = MagicMock()
    mock_client.complete = AsyncMock(side_effect=Exception("LLM API error"))

    result = await synthesize_document(
        text="Test document",
        llm_client=mock_client
    )

    assert "error" in result
    assert "LLM API error" in result["error"]


# Test 7: Text truncation validation
@pytest.mark.asyncio
async def test_synthesize_document_text_truncation():
    """Test that long text is properly truncated."""
    long_text = "A" * 20000  # Exceeds 15000 character limit

    mock_llm_response = {
        "content": json.dumps({
            "summary": "Test summary",
            "quick_summary": "Quick test",
            "keywords": ["test"],
            "industries": ["testing"],
            "language": "en"
        }),
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 100,
        "output_tokens": 50,
    }

    mock_client = MagicMock()
    mock_client.complete = AsyncMock(return_value=mock_llm_response)

    result = await synthesize_document(
        text=long_text,
        llm_client=mock_client
    )

    # Verify the prompt was truncated
    mock_client.complete.assert_called_once()
    call_kwargs = mock_client.complete.call_args.kwargs
    prompt = call_kwargs["prompt"]
    # The truncated text should be in the prompt (prompt with full text would be longer)
    full_prompt = SYNTHESIS_PROMPT.format(url="N/A", filename="N/A", text=long_text)
    assert len(prompt) < len(full_prompt)
    # Result should still be valid
    assert "error" not in result
    assert "summary" in result


# Test 8: Default LLM client creation
@pytest.mark.asyncio
async def test_synthesize_document_default_client():
    """Test that synthesize_document creates default LLM client when none provided."""
    mock_llm_response = {
        "content": json.dumps({
            "summary": "Test summary",
            "quick_summary": "Quick test",
            "keywords": ["test"],
            "industries": ["testing"],
            "language": "en"
        }),
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 100,
        "output_tokens": 50,
    }

    with patch("app.services.pipeline.synthesizer.LLMClient") as mock_llm_class:
        mock_instance = MagicMock()
        mock_instance.complete = AsyncMock(return_value=mock_llm_response)
        mock_llm_class.return_value = mock_instance

        result = await synthesize_document(text="Test document")

        # Verify LLMClient was instantiated
        mock_llm_class.assert_called_once()
        # Verify complete was called
        mock_instance.complete.assert_called_once()
        # Verify result is valid
        assert "error" not in result
        assert "summary" in result


# Test 9: Response structure validation
@pytest.mark.asyncio
async def test_synthesize_document_response_structure():
    """Test that the response has all expected fields with correct types."""
    mock_llm_response = {
        "content": json.dumps({
            "summary": "Extended summary covering main points, key insights, and conclusions.",
            "quick_summary": "Brief executive summary in 2-3 sentences.",
            "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
            "industries": ["technology", "software", "ai"],
            "language": "en"
        }),
        "provider": "openai",
        "model": "gpt-4-turbo-preview",
        "input_tokens": 200,
        "output_tokens": 100,
    }

    mock_client = MagicMock()
    mock_client.complete = AsyncMock(return_value=mock_llm_response)

    result = await synthesize_document(
        text="Detailed test document for validation.",
        llm_client=mock_client
    )

    # Verify all required fields exist
    assert "summary" in result
    assert "quick_summary" in result
    assert "keywords" in result
    assert "industries" in result
    assert "language" in result
    assert "llm_metadata" in result

    # Verify field types
    assert isinstance(result["summary"], str)
    assert isinstance(result["quick_summary"], str)
    assert isinstance(result["keywords"], list)
    assert isinstance(result["industries"], list)
    assert isinstance(result["language"], str)
    assert isinstance(result["llm_metadata"], dict)

    # Verify llm_metadata structure
    assert "provider" in result["llm_metadata"]
    assert "model" in result["llm_metadata"]
    assert "input_tokens" in result["llm_metadata"]
    assert "output_tokens" in result["llm_metadata"]
    assert result["llm_metadata"]["provider"] == "openai"
    assert result["llm_metadata"]["input_tokens"] == 200
    assert result["llm_metadata"]["output_tokens"] == 100


# Test 10: System prompt validation
@pytest.mark.asyncio
async def test_synthesize_document_system_prompt():
    """Test that the correct system prompt is used."""
    mock_llm_response = {
        "content": json.dumps({
            "summary": "Test",
            "quick_summary": "Test",
            "keywords": ["test"],
            "industries": ["test"],
            "language": "en"
        }),
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 100,
        "output_tokens": 50,
    }

    mock_client = MagicMock()
    mock_client.complete = AsyncMock(return_value=mock_llm_response)

    await synthesize_document(
        text="Test document",
        llm_client=mock_client
    )

    call_kwargs = mock_client.complete.call_args.kwargs
    assert call_kwargs["system"] == "You are a document analysis assistant. Respond only with valid JSON."
