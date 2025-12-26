"""Schemas for agentic query responses."""
from pydantic import BaseModel


class AgentSourceReference(BaseModel):
    """Source reference with internal/external distinction."""
    id: str | None = None
    title: str | None = None
    url: str | None = None
    source_type: str = "internal"  # "internal" or "external"
    snippet: str | None = None


class AgentQueryRequest(BaseModel):
    """Request for agentic query."""
    query: str
    max_iterations: int = 3


class AgentQueryResponse(BaseModel):
    """Response from agentic query."""
    answer: str
    sources: list[AgentSourceReference]
    research_iterations: int
    error: str | None = None
