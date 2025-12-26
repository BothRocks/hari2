# backend/tests/test_agent_router.py
"""Tests for router node."""
from app.agent.state import AgentState, EvaluationResult
from app.agent.nodes.router import router_node


def test_router_returns_generate_when_sufficient():
    """Test router routes to generator when context is sufficient."""
    state = AgentState(
        query="test",
        evaluation=EvaluationResult(
            is_sufficient=True,
            confidence=0.9,
            missing_information=[],
            reasoning="All good"
        )
    )

    result = router_node(state)

    assert result == "generate"


def test_router_returns_research_when_insufficient():
    """Test router routes to researcher when context is insufficient."""
    state = AgentState(
        query="test",
        research_iterations=0,
        max_iterations=3,
        evaluation=EvaluationResult(
            is_sufficient=False,
            confidence=0.3,
            missing_information=["more data"],
            reasoning="Needs research"
        )
    )

    result = router_node(state)

    assert result == "research"


def test_router_returns_generate_when_max_iterations_reached():
    """Test router routes to generator when max iterations hit."""
    state = AgentState(
        query="test",
        research_iterations=3,
        max_iterations=3,
        evaluation=EvaluationResult(
            is_sufficient=False,
            confidence=0.3,
            missing_information=["still missing"],
            reasoning="Still insufficient"
        )
    )

    result = router_node(state)

    assert result == "generate"


def test_router_returns_generate_when_no_evaluation():
    """Test router defaults to generate when no evaluation."""
    state = AgentState(query="test", evaluation=None)

    result = router_node(state)

    assert result == "generate"
