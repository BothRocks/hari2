# backend/app/agent/nodes/router.py
"""Router node - decides whether to generate or research more."""
from typing import Literal

from app.agent.state import AgentState


def router_node(state: AgentState) -> Literal["generate", "research"]:
    """
    Decide whether to generate response or continue researching.

    Args:
        state: Current agent state with evaluation

    Returns:
        "generate" - proceed to final answer generation
        "research" - perform external web search
    """
    # If a limit was exceeded, go directly to generate
    if state.exceeded_limit is not None:
        return "generate"

    # No evaluation means something went wrong, just generate
    if state.evaluation is None:
        return "generate"

    # If sufficient, generate
    if state.evaluation.is_sufficient:
        return "generate"

    # If max iterations reached, generate anyway
    if state.research_iterations >= state.max_iterations:
        return "generate"

    # Context insufficient and iterations available - research
    return "research"
