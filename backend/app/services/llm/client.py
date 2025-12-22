"""LLM client with multi-provider support and automatic fallback."""
import enum
from typing import Any, Optional, cast

from anthropic import Anthropic
from anthropic.types import TextBlock
from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam

from app.core.config import settings


class LLMProvider(str, enum.Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class LLMClient:
    """
    LLM client abstraction with multi-provider support.

    Supports Anthropic (Claude) and OpenAI (GPT-4) with automatic fallback
    from Anthropic to OpenAI on failure.
    """

    def __init__(self, provider: LLMProvider = LLMProvider.ANTHROPIC):
        """
        Initialize LLM client.

        Args:
            provider: Primary LLM provider to use (defaults to Anthropic)
        """
        self.provider = provider
        self._anthropic: Optional[Anthropic] = None
        self._openai: Optional[OpenAI] = None

    @property
    def anthropic(self) -> Anthropic:
        """Lazy-load Anthropic client."""
        if not self._anthropic:
            self._anthropic = Anthropic(api_key=settings.anthropic_api_key)
        return self._anthropic

    @property
    def openai(self) -> OpenAI:
        """Lazy-load OpenAI client."""
        if not self._openai:
            self._openai = OpenAI(api_key=settings.openai_api_key)
        return self._openai

    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> dict:
        """
        Generate completion with automatic fallback.

        Args:
            prompt: User prompt/message
            system: System message/instructions
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Dictionary with completion response containing:
                - content: Generated text
                - provider: Provider used
                - model: Model name
                - input_tokens: Input token count
                - output_tokens: Output token count

        Raises:
            Exception: If OpenAI is primary and fails (no fallback from OpenAI)
        """
        try:
            if self.provider == LLMProvider.ANTHROPIC:
                return await self._complete_anthropic(
                    prompt, system, max_tokens, temperature
                )
            else:
                return await self._complete_openai(
                    prompt, system, max_tokens, temperature
                )
        except Exception as e:
            # Only fallback from Anthropic to OpenAI, not the reverse
            if self.provider == LLMProvider.ANTHROPIC:
                return await self._complete_openai(
                    prompt, system, max_tokens, temperature
                )
            raise e

    async def _complete_anthropic(
        self, prompt: str, system: str, max_tokens: int, temperature: float
    ) -> dict:
        """
        Generate completion using Anthropic Claude.

        Args:
            prompt: User prompt
            system: System message
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Returns:
            Standardized completion response
        """
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract text from first content block (type-safe)
        first_block = response.content[0]
        content_text = cast(TextBlock, first_block).text if isinstance(first_block, TextBlock) else ""

        return {
            "content": content_text,
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

    async def _complete_openai(
        self, prompt: str, system: str, max_tokens: int, temperature: float
    ) -> dict:
        """
        Generate completion using OpenAI GPT-4.

        Args:
            prompt: User prompt
            system: System message
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Returns:
            Standardized completion response
        """
        # Build properly typed messages list
        messages: list[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.openai.chat.completions.create(
            model="gpt-4-turbo-preview",
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )

        # Extract values with None handling
        content = response.choices[0].message.content or ""
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        return {
            "content": content,
            "provider": "openai",
            "model": "gpt-4-turbo-preview",
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
        }
