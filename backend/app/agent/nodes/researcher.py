# backend/app/agent/nodes/researcher.py
"""Researcher node - performs external web search via Tavily."""
import time
from typing import Any

from app.agent.state import AgentState
from app.agent.utils import get_date_context
from app.services.tavily import TavilyService


def check_limits(state: AgentState) -> dict[str, Any] | None:
    """
    Check if any guardrail limits have been exceeded.

    Returns:
        State update dict with exceeded_limit set, or None if within limits
    """
    # Check timeout
    if state.start_time > 0:
        elapsed = time.time() - state.start_time
        if elapsed > state.timeout_seconds:
            return {"exceeded_limit": "timeout"}

    # Check cost
    if state.cost_spent_usd >= state.cost_ceiling_usd:
        return {"exceeded_limit": "cost"}

    return None


def build_research_query(state: AgentState) -> str:
    """
    Build an optimized search query using original query and missing info.

    Args:
        state: Agent state with query and evaluation

    Returns:
        Refined search query
    """
    base_query = state.query

    # Incorporate missing information if available
    if state.evaluation and state.evaluation.missing_information:
        missing = state.evaluation.missing_information[:2]  # Limit to top 2
        missing_str = " ".join(missing)
        return f"{base_query} {missing_str}"

    return base_query


async def researcher_node(
    state: AgentState,
    tavily_service: TavilyService | None = None,
) -> dict[str, Any]:
    """
    Search external sources via Tavily to fill knowledge gaps.

    Args:
        state: Current agent state
        tavily_service: Optional Tavily service instance

    Returns:
        State update with external_results and incremented iteration
    """
    # Check limits before processing
    limit_exceeded = check_limits(state)
    if limit_exceeded:
        return {
            **limit_exceeded,
            "research_iterations": state.research_iterations + 1,
        }

    service = tavily_service or TavilyService()

    # Build refined search query with date context for recency
    date_context = get_date_context()
    search_query = build_research_query(state)

    try:
        results = await service.search(
            query=search_query,
            max_results=5,
            search_depth="basic",
        )

        # Convert to dict format matching internal results
        external_results = [
            {
                "title": r.title,
                "url": r.url,
                "content": r.content,
                "snippet": r.content[:500] if r.content else "",
                "score": r.score,
                "source_type": "external",
            }
            for r in results
        ]

        return {
            "external_results": state.external_results + external_results,
            "research_iterations": state.research_iterations + 1,
        }

    except Exception:
        # On error, increment iteration but don't add results
        return {
            "external_results": state.external_results,
            "research_iterations": state.research_iterations + 1,
        }
