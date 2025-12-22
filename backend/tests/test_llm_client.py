"""Tests for LLM client abstraction with mocked API calls."""
import pytest
from unittest.mock import Mock, patch
from app.services.llm.client import LLMClient, LLMProvider
from anthropic.types import TextBlock


def test_llm_provider_enum():
    """Test LLM provider enum values."""
    assert LLMProvider.ANTHROPIC.value == "anthropic"
    assert LLMProvider.OPENAI.value == "openai"


def test_llm_client_initialization():
    """Test LLM client initialization with default provider."""
    client = LLMClient()
    assert client is not None
    assert client.provider == LLMProvider.ANTHROPIC


def test_llm_client_initialization_with_openai():
    """Test LLM client initialization with OpenAI provider."""
    client = LLMClient(provider=LLMProvider.OPENAI)
    assert client.provider == LLMProvider.OPENAI


def test_anthropic_property_lazy_loading():
    """Test Anthropic client is lazily loaded."""
    with patch("app.services.llm.client.Anthropic") as mock_anthropic:
        client = LLMClient()
        assert client._anthropic is None

        # Access property
        anthropic_client = client.anthropic

        # Should be created
        mock_anthropic.assert_called_once()
        assert client._anthropic is not None

        # Second access should reuse same instance
        anthropic_client2 = client.anthropic
        assert anthropic_client is anthropic_client2
        mock_anthropic.assert_called_once()  # Still only called once


def test_openai_property_lazy_loading():
    """Test OpenAI client is lazily loaded."""
    with patch("app.services.llm.client.OpenAI") as mock_openai:
        client = LLMClient()
        assert client._openai is None

        # Access property
        openai_client = client.openai

        # Should be created
        mock_openai.assert_called_once()
        assert client._openai is not None

        # Second access should reuse same instance
        openai_client2 = client.openai
        assert openai_client is openai_client2
        mock_openai.assert_called_once()  # Still only called once


@pytest.mark.asyncio
async def test_complete_with_anthropic():
    """Test complete method with Anthropic provider."""
    with patch("app.services.llm.client.Anthropic") as mock_anthropic_class:
        # Setup mock response with proper TextBlock mock
        mock_text_block = Mock(spec=TextBlock)
        mock_text_block.text = "Test response"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.usage = Mock(
            input_tokens=10,
            output_tokens=20
        )

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        # Test
        client = LLMClient(provider=LLMProvider.ANTHROPIC)
        result = await client.complete(
            prompt="Test prompt",
            system="Test system",
            max_tokens=1000,
            temperature=0.5
        )

        # Verify
        assert result["content"] == "Test response"
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["input_tokens"] == 10
        assert result["output_tokens"] == 20

        # Verify API was called correctly
        mock_client.messages.create.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            temperature=0.5,
            system="Test system",
            messages=[{"role": "user", "content": "Test prompt"}]
        )


@pytest.mark.asyncio
async def test_complete_with_openai():
    """Test complete method with OpenAI provider."""
    with patch("app.services.llm.client.OpenAI") as mock_openai_class:
        # Setup mock response
        mock_choice = Mock()
        mock_choice.message.content = "OpenAI response"

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(
            prompt_tokens=15,
            completion_tokens=25
        )

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Test
        client = LLMClient(provider=LLMProvider.OPENAI)
        result = await client.complete(
            prompt="Test prompt",
            system="Test system",
            max_tokens=1000,
            temperature=0.5
        )

        # Verify
        assert result["content"] == "OpenAI response"
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4-turbo-preview"
        assert result["input_tokens"] == 15
        assert result["output_tokens"] == 25

        # Verify API was called correctly
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4-turbo-preview",
            max_tokens=1000,
            temperature=0.5,
            messages=[
                {"role": "system", "content": "Test system"},
                {"role": "user", "content": "Test prompt"}
            ]
        )


@pytest.mark.asyncio
async def test_complete_with_openai_no_system():
    """Test complete method with OpenAI without system message."""
    with patch("app.services.llm.client.OpenAI") as mock_openai_class:
        # Setup mock response
        mock_choice = Mock()
        mock_choice.message.content = "OpenAI response"

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20)

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Test
        client = LLMClient(provider=LLMProvider.OPENAI)
        await client.complete(prompt="Test prompt")

        # Verify no system message in call
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Test prompt"}


@pytest.mark.asyncio
async def test_fallback_anthropic_to_openai():
    """Test automatic fallback from Anthropic to OpenAI on failure."""
    with patch("app.services.llm.client.Anthropic") as mock_anthropic_class, \
         patch("app.services.llm.client.OpenAI") as mock_openai_class:

        # Anthropic fails
        mock_anthropic_client = Mock()
        mock_anthropic_client.messages.create.side_effect = Exception("Anthropic API error")
        mock_anthropic_class.return_value = mock_anthropic_client

        # OpenAI succeeds
        mock_choice = Mock()
        mock_choice.message.content = "Fallback response"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20)

        mock_openai_client = Mock()
        mock_openai_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_openai_client

        # Test
        client = LLMClient(provider=LLMProvider.ANTHROPIC)
        result = await client.complete(prompt="Test prompt")

        # Verify fallback to OpenAI
        assert result["content"] == "Fallback response"
        assert result["provider"] == "openai"

        # Both providers should have been tried
        mock_anthropic_client.messages.create.assert_called_once()
        mock_openai_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_fallback_fails_on_openai_primary():
    """Test that OpenAI primary failure raises exception (no fallback to Anthropic)."""
    with patch("app.services.llm.client.OpenAI") as mock_openai_class:
        # OpenAI fails
        mock_openai_client = Mock()
        mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI API error")
        mock_openai_class.return_value = mock_openai_client

        # Test
        client = LLMClient(provider=LLMProvider.OPENAI)

        with pytest.raises(Exception, match="OpenAI API error"):
            await client.complete(prompt="Test prompt")


@pytest.mark.asyncio
async def test_complete_default_parameters():
    """Test complete method uses default parameters correctly."""
    with patch("app.services.llm.client.Anthropic") as mock_anthropic_class:
        # Setup mock response
        mock_text_block = Mock(spec=TextBlock)
        mock_text_block.text = "Response"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.usage = Mock(input_tokens=5, output_tokens=10)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        # Test with defaults
        client = LLMClient()
        await client.complete(prompt="Test")

        # Verify defaults were used
        call_args = mock_client.messages.create.call_args
        assert call_args[1]["max_tokens"] == 2000  # default
        assert call_args[1]["temperature"] == 0.7  # default
        assert call_args[1]["system"] == ""  # default


@pytest.mark.asyncio
async def test_complete_response_structure():
    """Test that response structure is consistent across providers."""
    with patch("app.services.llm.client.Anthropic") as mock_anthropic_class:
        # Setup mock
        mock_text_block = Mock(spec=TextBlock)
        mock_text_block.text = "Test"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.usage = Mock(input_tokens=1, output_tokens=2)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        client = LLMClient()
        result = await client.complete(prompt="Test")

        # Verify response has all required fields
        assert "content" in result
        assert "provider" in result
        assert "model" in result
        assert "input_tokens" in result
        assert "output_tokens" in result

        # Verify types
        assert isinstance(result["content"], str)
        assert isinstance(result["provider"], str)
        assert isinstance(result["model"], str)
        assert isinstance(result["input_tokens"], int)
        assert isinstance(result["output_tokens"], int)
