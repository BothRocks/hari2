"""Schemas for agentic query responses."""
from pydantic import BaseModel, Field


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
    max_iterations: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(
        default=120,
        ge=30,
        le=300,
        description="Max query time in seconds (30-300). Use 300 for extended retry."
    )


class AgentQueryResponse(BaseModel):
    """Response from agentic query."""
    answer: str
    sources: list[AgentSourceReference]
    research_iterations: int
    cost_usd: float | None = None
    error: str | None = None
