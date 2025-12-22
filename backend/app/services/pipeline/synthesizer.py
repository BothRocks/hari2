"""Document synthesizer using LLM for structured summary generation."""
import json
from typing import Any, Optional

from app.services.llm.client import LLMClient

SYNTHESIS_PROMPT = """Analyze the following text and provide a structured summary.

TEXT:
{text}

Respond with valid JSON only, no other text:
{{
  "summary": "Extended summary (300-500 words) covering main points, key insights, and conclusions",
  "quick_summary": "2-3 sentence executive summary",
  "keywords": ["keyword1", "keyword2", ...],  // 5-10 relevant keywords
  "industries": ["industry1", "industry2"],   // Relevant industry classifications
  "language": "en"  // Detected language code
}}
"""


async def synthesize_document(
    text: Optional[str],
    llm_client: Optional[LLMClient] = None
) -> dict[str, Any]:
    """
    Generate structured summary using LLM.

    Args:
        text: Document text to synthesize
        llm_client: Optional LLM client instance (creates default if not provided)

    Returns:
        Dictionary containing:
            - summary: Extended summary (300-500 words)
            - quick_summary: Brief 2-3 sentence summary
            - keywords: List of 5-10 relevant keywords
            - industries: List of relevant industry classifications
            - language: Detected language code
            - llm_metadata: Metadata about the LLM request (provider, model, tokens)
        Or dictionary with "error" key if processing fails
    """
    if not text:
        return {"error": "No text provided"}

    client = llm_client or LLMClient()

    # Truncate text to stay within token limits (15000 chars ≈ 3750 tokens)
    prompt = SYNTHESIS_PROMPT.format(text=text[:15000])

    try:
        response = await client.complete(
            prompt=prompt,
            system="You are a document analysis assistant. Respond only with valid JSON.",
            max_tokens=1500,
            temperature=0.3,
        )

        # Extract content from response
        content = response["content"]

        # Extract JSON if wrapped in markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        # Parse JSON response
        result = json.loads(content.strip())

        # Add LLM metadata to result
        result["llm_metadata"] = {
            "provider": response["provider"],
            "model": response["model"],
            "input_tokens": response["input_tokens"],
            "output_tokens": response["output_tokens"],
        }

        return result

    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse LLM response: {e}"}
    except Exception as e:
        return {"error": str(e)}
