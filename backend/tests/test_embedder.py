# backend/tests/test_embedder.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.pipeline.embedder import (
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    generate_embedding,
    generate_embeddings_batch,
)


def test_embedding_constants():
    """Test that embedding constants are correctly defined."""
    assert EMBEDDING_MODEL == "text-embedding-3-small"
    assert EMBEDDING_DIMENSIONS == 1536


@pytest.mark.asyncio
async def test_generate_embedding_success():
    """Test successful embedding generation."""
    test_text = "This is a test document for embedding generation."
    mock_embedding = [0.1] * EMBEDDING_DIMENSIONS

    # Create mock response
    mock_response = Mock()
    mock_response.data = [Mock(embedding=mock_embedding)]

    # Mock OpenAI client
    with patch("app.services.pipeline.embedder.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = await generate_embedding(test_text)

        assert result is not None
        assert len(result) == EMBEDDING_DIMENSIONS
        assert result == mock_embedding
        mock_client.embeddings.create.assert_called_once_with(
            model=EMBEDDING_MODEL,
            input=test_text,
        )


@pytest.mark.asyncio
async def test_generate_embedding_empty_text():
    """Test that empty text returns None."""
    result = await generate_embedding("")
    assert result is None


@pytest.mark.asyncio
async def test_generate_embedding_none_text():
    """Test that None text returns None."""
    result = await generate_embedding(None)
    assert result is None


@pytest.mark.asyncio
async def test_generate_embedding_text_truncation():
    """Test that long text is truncated before sending to API."""
    long_text = "x" * 50000  # Text longer than 30000 char limit
    mock_embedding = [0.2] * EMBEDDING_DIMENSIONS

    mock_response = Mock()
    mock_response.data = [Mock(embedding=mock_embedding)]

    with patch("app.services.pipeline.embedder.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = await generate_embedding(long_text)

        # Verify the call was made with truncated text
        call_args = mock_client.embeddings.create.call_args
        assert len(call_args.kwargs["input"]) == 30000
        assert result == mock_embedding


@pytest.mark.asyncio
async def test_generate_embedding_api_error():
    """Test error handling when OpenAI API fails."""
    test_text = "Test text"

    with patch("app.services.pipeline.embedder.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client

        result = await generate_embedding(test_text)

        assert result is None


@pytest.mark.asyncio
async def test_generate_embedding_return_type():
    """Test that the return type is a list of floats."""
    test_text = "Test document"
    mock_embedding = [0.5] * EMBEDDING_DIMENSIONS

    mock_response = Mock()
    mock_response.data = [Mock(embedding=mock_embedding)]

    with patch("app.services.pipeline.embedder.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = await generate_embedding(test_text)

        assert isinstance(result, list)
        assert all(isinstance(x, (int, float)) for x in result)
        assert len(result) == EMBEDDING_DIMENSIONS


@pytest.mark.asyncio
async def test_generate_embeddings_batch_success():
    """Test batch embedding generation."""
    texts = ["Text 1", "Text 2", "Text 3"]
    mock_embedding_1 = [0.1] * EMBEDDING_DIMENSIONS
    mock_embedding_2 = [0.2] * EMBEDDING_DIMENSIONS
    mock_embedding_3 = [0.3] * EMBEDDING_DIMENSIONS

    mock_response = Mock()
    mock_response.data = [Mock(embedding=mock_embedding_1)]

    with patch("app.services.pipeline.embedder.OpenAI") as mock_openai:
        mock_client = MagicMock()
        # Set different return values for each call
        mock_client.embeddings.create.side_effect = [
            Mock(data=[Mock(embedding=mock_embedding_1)]),
            Mock(data=[Mock(embedding=mock_embedding_2)]),
            Mock(data=[Mock(embedding=mock_embedding_3)]),
        ]
        mock_openai.return_value = mock_client

        results = await generate_embeddings_batch(texts)

        assert len(results) == 3
        assert results[0] == mock_embedding_1
        assert results[1] == mock_embedding_2
        assert results[2] == mock_embedding_3
        assert mock_client.embeddings.create.call_count == 3


@pytest.mark.asyncio
async def test_generate_embeddings_batch_with_empty_text():
    """Test batch embedding generation with empty text."""
    texts = ["Text 1", "", "Text 3"]
    mock_embedding_1 = [0.1] * EMBEDDING_DIMENSIONS
    mock_embedding_3 = [0.3] * EMBEDDING_DIMENSIONS

    with patch("app.services.pipeline.embedder.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = [
            Mock(data=[Mock(embedding=mock_embedding_1)]),
            Mock(data=[Mock(embedding=mock_embedding_3)]),
        ]
        mock_openai.return_value = mock_client

        results = await generate_embeddings_batch(texts)

        assert len(results) == 3
        assert results[0] == mock_embedding_1
        assert results[1] is None  # Empty text should return None
        assert results[2] == mock_embedding_3
        # Should only be called twice (not for empty text)
        assert mock_client.embeddings.create.call_count == 2


@pytest.mark.asyncio
async def test_generate_embeddings_batch_with_errors():
    """Test batch embedding generation with some failures."""
    texts = ["Text 1", "Text 2"]
    mock_embedding_1 = [0.1] * EMBEDDING_DIMENSIONS

    with patch("app.services.pipeline.embedder.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = [
            Mock(data=[Mock(embedding=mock_embedding_1)]),
            Exception("API Error"),
        ]
        mock_openai.return_value = mock_client

        results = await generate_embeddings_batch(texts)

        assert len(results) == 2
        assert results[0] == mock_embedding_1
        assert results[1] is None  # Failed embedding should return None


@pytest.mark.asyncio
async def test_generate_embeddings_batch_empty_list():
    """Test batch embedding generation with empty list."""
    results = await generate_embeddings_batch([])
    assert results == []


@pytest.mark.asyncio
async def test_generate_embedding_uses_correct_api_key():
    """Test that the function uses the API key from settings."""
    test_text = "Test text"
    mock_embedding = [0.1] * EMBEDDING_DIMENSIONS

    mock_response = Mock()
    mock_response.data = [Mock(embedding=mock_embedding)]

    with patch("app.services.pipeline.embedder.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        with patch("app.services.pipeline.embedder.settings") as mock_settings:
            mock_settings.openai_api_key = "test-api-key-123"

            await generate_embedding(test_text)

            # Verify OpenAI was initialized with the correct API key
            mock_openai.assert_called_once_with(api_key="test-api-key-123")
