# backend/app/agent/nodes/generator.py
"""Generator node - synthesizes final response from all context."""
from typing import Any

from app.agent.state import AgentState, SourceReference
from app.agent.pricing import calculate_cost
from app.agent.utils import get_date_context
from app.services.llm.client import LLMClient


GENERATOR_PROMPT = """You are HARI, a knowledge assistant. Generate a comprehensive answer to the user's question using the provided context.

{date_context}

USER QUESTION:
{query}

INTERNAL KNOWLEDGE BASE CONTEXT:
{internal_context}

EXTERNAL WEB SEARCH RESULTS:
{external_context}

Instructions:
- Synthesize information from both internal and external sources
- Prioritize internal sources but supplement with external when needed
- Be comprehensive but concise
- Cite sources by mentioning document titles or URLs
- If information is conflicting, note the discrepancy
- If context is insufficient, acknowledge limitations

RESPONSE:"""


LIMIT_DISCLAIMER = {
    "timeout": "\n\n*Note: This response may be incomplete due to time constraints.*",
    "cost": "\n\n*Note: This response may be incomplete due to processing limits.*",
}


async def generator_node(
    state: AgentState,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """
    Generate final answer using all retrieved context.

    Args:
        state: Agent state with query, internal_results, external_results
        llm_client: Optional LLM client

    Returns:
        State update with final_answer, sources, updated cost, and potential error
    """
    client = llm_client or LLMClient()

    # Format internal context
    internal_parts = []
    internal_sources = []
    for doc in state.internal_results:
        title = doc.get("title", "Untitled")
        summary = doc.get("quick_summary", doc.get("summary", ""))
        internal_parts.append(f"[{title}]\n{summary}")
        internal_sources.append(SourceReference(
            id=doc.get("id"),
            title=title,
            url=doc.get("url"),
            source_type="internal",
            snippet=summary[:200] if summary else None,
        ))

    internal_context = "\n\n".join(internal_parts) if internal_parts else "No internal documents found."

    # Format external context
    external_parts = []
    external_sources = []
    for doc in state.external_results:
        title = doc.get("title", "Web Result")
        content = doc.get("content", doc.get("snippet", ""))
        url = doc.get("url", "")
        external_parts.append(f"[{title}]\nURL: {url}\n{content}")
        external_sources.append(SourceReference(
            id=None,
            title=title,
            url=url,
            source_type="external",
            snippet=content[:200] if content else None,
        ))

    external_context = "\n\n".join(external_parts) if external_parts else "No external search performed."

    prompt = GENERATOR_PROMPT.format(
        date_context=get_date_context(),
        query=state.query,
        internal_context=internal_context,
        external_context=external_context,
    )

    try:
        response = await client.complete(
            prompt=prompt,
            system="You are HARI, a helpful and thorough knowledge assistant.",
            max_tokens=1500,
            temperature=0.7,
        )

        # Calculate and track cost
        cost = calculate_cost(
            provider=response.get("provider", "anthropic"),
            model=response.get("model", ""),
            input_tokens=response.get("input_tokens", 0),
            output_tokens=response.get("output_tokens", 0),
        )
        new_cost = state.cost_spent_usd + cost

        # Add disclaimer if a limit was exceeded
        answer = response["content"]
        if state.exceeded_limit:
            answer += LIMIT_DISCLAIMER.get(state.exceeded_limit, "")

        return {
            "final_answer": answer,
            "sources": internal_sources + external_sources,
            "cost_spent_usd": new_cost,
            "error": None,
        }

    except Exception as e:
        return {
            "final_answer": None,
            "sources": internal_sources + external_sources,
            "error": str(e),
        }
