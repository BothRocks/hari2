# backend/app/agent/nodes/retriever.py
"""Retriever node - searches internal knowledge base."""
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.services.search.hybrid import HybridSearch


async def retriever_node(
    state: AgentState,
    session: AsyncSession | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Search internal knowledge base using hybrid search.

    Args:
        state: Current agent state with query
        session: Database session for search
        limit: Maximum documents to retrieve

    Returns:
        State update with internal_results populated
    """
    search = HybridSearch(session)

    results = await search.search(
        query=state.query,
        limit=limit,
        session=session,
    )

    return {"internal_results": results}
