"""Tests for agent state schema."""
from app.agent.state import AgentState, EvaluationResult


def test_agent_state_initial():
    """Test AgentState can be created with minimal fields."""
    state = AgentState(query="What is Python?")
    assert state.query == "What is Python?"
    assert state.internal_results == []
    assert state.external_results == []
    assert state.evaluation is None
    assert state.research_iterations == 0
    assert state.final_answer is None


def test_evaluation_result_schema():
    """Test EvaluationResult schema."""
    result = EvaluationResult(
        is_sufficient=False,
        confidence=0.3,
        missing_information=["recent updates", "external sources"],
        reasoning="Context lacks current information"
    )
    assert result.is_sufficient is False
    assert result.confidence == 0.3
    assert len(result.missing_information) == 2
