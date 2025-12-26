"""Agent state definitions for LangGraph."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class EvaluationResult(BaseModel):
    """Result from the evaluator node."""
    is_sufficient: bool
    confidence: float = Field(ge=0.0, le=1.0)
    missing_information: list[str] = Field(default_factory=list)
    reasoning: str


class SourceReference(BaseModel):
    """Reference to a source document."""
    id: str | None = None
    title: str | None = None
    url: str | None = None
    source_type: str = "internal"  # "internal" or "external"
    snippet: str | None = None


class AgentState(BaseModel):
    """State that flows through the agent graph."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Input
    query: str

    # Search results
    internal_results: list[dict[str, Any]] = Field(default_factory=list)
    external_results: list[dict[str, Any]] = Field(default_factory=list)

    # Evaluation
    evaluation: EvaluationResult | None = None

    # Control flow
    research_iterations: int = 0
    max_iterations: int = 3

    # Output
    final_answer: str | None = None
    sources: list[SourceReference] = Field(default_factory=list)

    # Metadata
    error: str | None = None
