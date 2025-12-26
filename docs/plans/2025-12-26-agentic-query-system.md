# Agentic Query System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a LangGraph-based agentic RAG system with cognitive loop that evaluates context sufficiency and autonomously seeks external information via Tavily.

**Architecture:** The agent uses a StateGraph with 5 nodes: Retriever (internal search), Evaluator (assess sufficiency), Router (decide next step), Researcher (Tavily web search), and Generator (final response). The graph loops through Researcher when context is insufficient, with guardrails limiting iterations.

**Tech Stack:** LangGraph, Tavily Python SDK, existing HybridSearch, existing LLMClient (Anthropic/OpenAI)

---

## Task 1: Add Dependencies

**Files:**
- Modify: `backend/pyproject.toml:6-30`

**Step 1: Add langgraph and tavily dependencies**

Add to the `dependencies` list in `pyproject.toml`:

```toml
"langgraph>=0.2.0",
"tavily-python>=0.5.0",
```

**Step 2: Install dependencies**

Run: `cd backend && uv sync`
Expected: Dependencies installed successfully

**Step 3: Verify installation**

Run: `cd backend && uv run python -c "import langgraph; import tavily; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore: add langgraph and tavily dependencies"
```

---

## Task 2: Create Agent State Schema

**Files:**
- Create: `backend/app/agent/__init__.py`
- Create: `backend/app/agent/state.py`
- Test: `backend/tests/test_agent_state.py`

**Step 1: Create agent module init**

```python
# backend/app/agent/__init__.py
"""Agentic query system using LangGraph."""
```

**Step 2: Write the failing test for state schema**

```python
# backend/tests/test_agent_state.py
"""Tests for agent state schema."""
import pytest
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
```

**Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent_state.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.agent'"

**Step 4: Write state schema implementation**

```python
# backend/app/agent/state.py
"""Agent state definitions for LangGraph."""
from typing import Any
from pydantic import BaseModel, Field


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

    class Config:
        arbitrary_types_allowed = True
```

**Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_agent_state.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/agent/ backend/tests/test_agent_state.py
git commit -m "feat(agent): add state schema for LangGraph agent"
```

---

## Task 3: Create Retriever Node

**Files:**
- Create: `backend/app/agent/nodes/__init__.py`
- Create: `backend/app/agent/nodes/retriever.py`
- Test: `backend/tests/test_agent_retriever.py`

**Step 1: Create nodes module init**

```python
# backend/app/agent/nodes/__init__.py
"""Agent nodes for the LangGraph state machine."""
from app.agent.nodes.retriever import retriever_node
from app.agent.nodes.evaluator import evaluator_node
from app.agent.nodes.router import router_node
from app.agent.nodes.researcher import researcher_node
from app.agent.nodes.generator import generator_node

__all__ = [
    "retriever_node",
    "evaluator_node",
    "router_node",
    "researcher_node",
    "generator_node",
]
```

**Step 2: Write the failing test for retriever node**

```python
# backend/tests/test_agent_retriever.py
"""Tests for retriever node."""
import pytest
from unittest.mock import AsyncMock, patch
from app.agent.state import AgentState
from app.agent.nodes.retriever import retriever_node


@pytest.mark.asyncio
async def test_retriever_node_populates_internal_results():
    """Test that retriever node calls HybridSearch and populates state."""
    mock_results = [
        {"id": "doc1", "title": "Python Guide", "quick_summary": "A guide to Python"},
        {"id": "doc2", "title": "FastAPI Docs", "quick_summary": "FastAPI documentation"},
    ]

    state = AgentState(query="How do I use FastAPI?")

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch:
        mock_instance = MockSearch.return_value
        mock_instance.search = AsyncMock(return_value=mock_results)

        result = await retriever_node(state, session=None)

        assert len(result["internal_results"]) == 2
        assert result["internal_results"][0]["title"] == "Python Guide"
        mock_instance.search.assert_called_once()


@pytest.mark.asyncio
async def test_retriever_node_handles_empty_results():
    """Test retriever handles no results gracefully."""
    state = AgentState(query="obscure query with no matches")

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch:
        mock_instance = MockSearch.return_value
        mock_instance.search = AsyncMock(return_value=[])

        result = await retriever_node(state, session=None)

        assert result["internal_results"] == []
```

**Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent_retriever.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 4: Write retriever node implementation**

```python
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
```

**Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_agent_retriever.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/agent/nodes/ backend/tests/test_agent_retriever.py
git commit -m "feat(agent): add retriever node wrapping HybridSearch"
```

---

## Task 4: Create Tavily Service

**Files:**
- Create: `backend/app/services/tavily.py`
- Test: `backend/tests/test_tavily_service.py`

**Step 1: Write the failing test for Tavily service**

```python
# backend/tests/test_tavily_service.py
"""Tests for Tavily web search service."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.tavily import TavilyService, TavilyResult


def test_tavily_result_schema():
    """Test TavilyResult schema."""
    result = TavilyResult(
        title="Python Official Site",
        url="https://python.org",
        content="Python is a programming language...",
        score=0.95,
    )
    assert result.title == "Python Official Site"
    assert result.score == 0.95


@pytest.mark.asyncio
async def test_tavily_service_search():
    """Test Tavily search returns formatted results."""
    mock_response = {
        "results": [
            {
                "title": "Result 1",
                "url": "https://example.com/1",
                "content": "Content 1",
                "score": 0.9,
            },
            {
                "title": "Result 2",
                "url": "https://example.com/2",
                "content": "Content 2",
                "score": 0.8,
            },
        ]
    }

    with patch("app.services.tavily.TavilyClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.search = MagicMock(return_value=mock_response)

        service = TavilyService(api_key="test-key")
        results = await service.search("test query", max_results=5)

        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[0].score == 0.9


@pytest.mark.asyncio
async def test_tavily_service_handles_no_api_key():
    """Test Tavily service raises when no API key."""
    service = TavilyService(api_key=None)

    with pytest.raises(ValueError, match="Tavily API key not configured"):
        await service.search("test query")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_tavily_service.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write Tavily service implementation**

```python
# backend/app/services/tavily.py
"""Tavily web search service."""
from typing import Any
from pydantic import BaseModel
from tavily import TavilyClient

from app.core.config import settings


class TavilyResult(BaseModel):
    """A single Tavily search result."""
    title: str
    url: str
    content: str
    score: float


class TavilyService:
    """Service for web search via Tavily API."""

    def __init__(self, api_key: str | None = None):
        """
        Initialize Tavily service.

        Args:
            api_key: Tavily API key (falls back to settings)
        """
        self.api_key = api_key or settings.tavily_api_key
        self._client: TavilyClient | None = None

    @property
    def client(self) -> TavilyClient:
        """Lazy-load Tavily client."""
        if not self._client:
            if not self.api_key:
                raise ValueError("Tavily API key not configured")
            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
    ) -> list[TavilyResult]:
        """
        Search the web using Tavily.

        Args:
            query: Search query
            max_results: Maximum results to return
            search_depth: "basic" or "advanced"

        Returns:
            List of search results
        """
        if not self.api_key:
            raise ValueError("Tavily API key not configured")

        # Tavily client is sync, but we wrap for async interface
        response = self.client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
        )

        results = []
        for item in response.get("results", []):
            results.append(TavilyResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=item.get("score", 0.0),
            ))

        return results
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_tavily_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/tavily.py backend/tests/test_tavily_service.py
git commit -m "feat: add Tavily web search service"
```

---

## Task 5: Create Evaluator Node

**Files:**
- Create: `backend/app/agent/nodes/evaluator.py`
- Test: `backend/tests/test_agent_evaluator.py`

**Step 1: Write the failing test for evaluator node**

```python
# backend/tests/test_agent_evaluator.py
"""Tests for evaluator node."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.agent.state import AgentState, EvaluationResult
from app.agent.nodes.evaluator import evaluator_node, parse_evaluation_response


def test_parse_evaluation_response_valid_json():
    """Test parsing valid JSON evaluation response."""
    response = json.dumps({
        "is_sufficient": True,
        "confidence": 0.85,
        "missing_information": [],
        "reasoning": "Context fully answers the question"
    })

    result = parse_evaluation_response(response)

    assert result.is_sufficient is True
    assert result.confidence == 0.85
    assert result.missing_information == []


def test_parse_evaluation_response_with_markdown():
    """Test parsing JSON wrapped in markdown code block."""
    response = '''Here is my evaluation:
```json
{
    "is_sufficient": false,
    "confidence": 0.4,
    "missing_information": ["recent data"],
    "reasoning": "Needs current information"
}
```
'''
    result = parse_evaluation_response(response)

    assert result.is_sufficient is False
    assert result.confidence == 0.4


@pytest.mark.asyncio
async def test_evaluator_node_returns_evaluation():
    """Test evaluator node populates evaluation in state."""
    state = AgentState(
        query="What is the latest Python version?",
        internal_results=[
            {"title": "Python 3.11", "quick_summary": "Python 3.11 features..."}
        ]
    )

    mock_response = {
        "content": json.dumps({
            "is_sufficient": False,
            "confidence": 0.3,
            "missing_information": ["Python 3.12+ information"],
            "reasoning": "Results are outdated"
        })
    }

    with patch("app.agent.nodes.evaluator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(return_value=mock_response)

        result = await evaluator_node(state)

        assert result["evaluation"] is not None
        assert result["evaluation"].is_sufficient is False
        assert result["evaluation"].confidence == 0.3
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent_evaluator.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write evaluator node implementation**

```python
# backend/app/agent/nodes/evaluator.py
"""Evaluator node - assesses if retrieved context is sufficient."""
import json
import re
from typing import Any

from app.agent.state import AgentState, EvaluationResult
from app.services.llm.client import LLMClient


EVALUATION_PROMPT = """You are evaluating whether the retrieved context is sufficient to answer the user's question.

USER QUESTION:
{query}

RETRIEVED CONTEXT:
{context}

Evaluate the context and respond with a JSON object:
{{
    "is_sufficient": true/false,
    "confidence": 0.0-1.0,
    "missing_information": ["list", "of", "missing", "info"],
    "reasoning": "Brief explanation"
}}

Consider:
- Does the context directly address the question?
- Is the information current/relevant?
- Are there gaps that external search could fill?

Respond ONLY with the JSON object, no other text."""


def parse_evaluation_response(response: str) -> EvaluationResult:
    """
    Parse LLM response into EvaluationResult.

    Handles both raw JSON and markdown-wrapped JSON.
    """
    # Try to extract JSON from markdown code block
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response.strip()

    try:
        data = json.loads(json_str)
        return EvaluationResult(
            is_sufficient=data.get("is_sufficient", False),
            confidence=float(data.get("confidence", 0.5)),
            missing_information=data.get("missing_information", []),
            reasoning=data.get("reasoning", ""),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        # Default to insufficient if parsing fails
        return EvaluationResult(
            is_sufficient=False,
            confidence=0.5,
            missing_information=["Failed to parse evaluation"],
            reasoning=f"Parse error: {response[:200]}",
        )


async def evaluator_node(
    state: AgentState,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """
    Evaluate if retrieved context is sufficient to answer the query.

    Args:
        state: Current agent state with query and internal_results
        llm_client: Optional LLM client (creates new if not provided)

    Returns:
        State update with evaluation result
    """
    client = llm_client or LLMClient()

    # Format context from results
    context_parts = []
    for doc in state.internal_results:
        title = doc.get("title", "Untitled")
        summary = doc.get("quick_summary", doc.get("summary", ""))
        context_parts.append(f"[{title}]\n{summary}")

    for doc in state.external_results:
        title = doc.get("title", "Web Result")
        content = doc.get("content", doc.get("snippet", ""))
        context_parts.append(f"[{title} (external)]\n{content}")

    context_text = "\n\n".join(context_parts) if context_parts else "No context retrieved."

    prompt = EVALUATION_PROMPT.format(
        query=state.query,
        context=context_text,
    )

    try:
        response = await client.complete(
            prompt=prompt,
            system="You are a context evaluator. Respond only with JSON.",
            max_tokens=500,
            temperature=0.0,  # Deterministic for evaluation
        )

        evaluation = parse_evaluation_response(response["content"])
        return {"evaluation": evaluation}

    except Exception as e:
        # On error, default to sufficient to avoid infinite loops
        return {
            "evaluation": EvaluationResult(
                is_sufficient=True,
                confidence=0.5,
                missing_information=[],
                reasoning=f"Evaluation error: {str(e)}",
            )
        }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_agent_evaluator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/agent/nodes/evaluator.py backend/tests/test_agent_evaluator.py
git commit -m "feat(agent): add evaluator node for context sufficiency"
```

---

## Task 6: Create Router Node

**Files:**
- Create: `backend/app/agent/nodes/router.py`
- Test: `backend/tests/test_agent_router.py`

**Step 1: Write the failing test for router node**

```python
# backend/tests/test_agent_router.py
"""Tests for router node."""
import pytest
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent_router.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write router node implementation**

```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_agent_router.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/agent/nodes/router.py backend/tests/test_agent_router.py
git commit -m "feat(agent): add router node for decision logic"
```

---

## Task 7: Create Researcher Node

**Files:**
- Create: `backend/app/agent/nodes/researcher.py`
- Test: `backend/tests/test_agent_researcher.py`

**Step 1: Write the failing test for researcher node**

```python
# backend/tests/test_agent_researcher.py
"""Tests for researcher node."""
import pytest
from unittest.mock import AsyncMock, patch
from app.agent.state import AgentState, EvaluationResult
from app.agent.nodes.researcher import researcher_node
from app.services.tavily import TavilyResult


@pytest.mark.asyncio
async def test_researcher_node_calls_tavily():
    """Test researcher node searches Tavily and updates state."""
    state = AgentState(
        query="What is Python 3.12?",
        research_iterations=0,
        evaluation=EvaluationResult(
            is_sufficient=False,
            confidence=0.3,
            missing_information=["Python 3.12 features"],
            reasoning="Need current info"
        )
    )

    mock_results = [
        TavilyResult(
            title="Python 3.12 Released",
            url="https://python.org/3.12",
            content="Python 3.12 includes...",
            score=0.95
        )
    ]

    with patch("app.agent.nodes.researcher.TavilyService") as MockTavily:
        mock_instance = MockTavily.return_value
        mock_instance.search = AsyncMock(return_value=mock_results)

        result = await researcher_node(state)

        assert len(result["external_results"]) == 1
        assert result["external_results"][0]["title"] == "Python 3.12 Released"
        assert result["research_iterations"] == 1


@pytest.mark.asyncio
async def test_researcher_node_handles_tavily_error():
    """Test researcher gracefully handles Tavily errors."""
    state = AgentState(
        query="test query",
        research_iterations=0,
        evaluation=EvaluationResult(
            is_sufficient=False,
            confidence=0.3,
            missing_information=["data"],
            reasoning="Need info"
        )
    )

    with patch("app.agent.nodes.researcher.TavilyService") as MockTavily:
        mock_instance = MockTavily.return_value
        mock_instance.search = AsyncMock(side_effect=ValueError("API error"))

        result = await researcher_node(state)

        # Should still increment iteration but have empty results
        assert result["external_results"] == []
        assert result["research_iterations"] == 1


@pytest.mark.asyncio
async def test_researcher_uses_missing_info_for_query():
    """Test researcher refines query using missing information."""
    state = AgentState(
        query="Tell me about Python",
        research_iterations=0,
        evaluation=EvaluationResult(
            is_sufficient=False,
            confidence=0.3,
            missing_information=["Python 3.12 features", "release date"],
            reasoning="Too general"
        )
    )

    with patch("app.agent.nodes.researcher.TavilyService") as MockTavily:
        mock_instance = MockTavily.return_value
        mock_instance.search = AsyncMock(return_value=[])

        await researcher_node(state)

        # Check that search was called with refined query
        call_args = mock_instance.search.call_args
        search_query = call_args[0][0] if call_args[0] else call_args[1].get("query", "")
        assert "Python 3.12" in search_query or "release date" in search_query
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent_researcher.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write researcher node implementation**

```python
# backend/app/agent/nodes/researcher.py
"""Researcher node - performs external web search via Tavily."""
from typing import Any

from app.agent.state import AgentState
from app.services.tavily import TavilyService


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
    service = tavily_service or TavilyService()

    # Build refined search query
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
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_agent_researcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/agent/nodes/researcher.py backend/tests/test_agent_researcher.py
git commit -m "feat(agent): add researcher node with Tavily integration"
```

---

## Task 8: Create Generator Node

**Files:**
- Create: `backend/app/agent/nodes/generator.py`
- Test: `backend/tests/test_agent_generator.py`

**Step 1: Write the failing test for generator node**

```python
# backend/tests/test_agent_generator.py
"""Tests for generator node."""
import pytest
from unittest.mock import AsyncMock, patch
from app.agent.state import AgentState, SourceReference
from app.agent.nodes.generator import generator_node


@pytest.mark.asyncio
async def test_generator_node_produces_answer():
    """Test generator creates final answer from context."""
    state = AgentState(
        query="What is Python?",
        internal_results=[
            {"id": "1", "title": "Python Guide", "quick_summary": "Python is a programming language."}
        ],
        external_results=[],
    )

    mock_response = {"content": "Python is a high-level programming language."}

    with patch("app.agent.nodes.generator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(return_value=mock_response)

        result = await generator_node(state)

        assert result["final_answer"] == "Python is a high-level programming language."
        assert len(result["sources"]) == 1
        assert result["sources"][0].source_type == "internal"


@pytest.mark.asyncio
async def test_generator_node_combines_internal_and_external():
    """Test generator uses both internal and external sources."""
    state = AgentState(
        query="What is Python 3.12?",
        internal_results=[
            {"id": "1", "title": "Python Docs", "quick_summary": "Python overview"}
        ],
        external_results=[
            {"title": "Python 3.12 Release", "url": "https://python.org", "content": "New features..."}
        ],
    )

    mock_response = {"content": "Python 3.12 includes many new features."}

    with patch("app.agent.nodes.generator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(return_value=mock_response)

        result = await generator_node(state)

        assert len(result["sources"]) == 2
        source_types = [s.source_type for s in result["sources"]]
        assert "internal" in source_types
        assert "external" in source_types


@pytest.mark.asyncio
async def test_generator_handles_llm_error():
    """Test generator handles LLM errors gracefully."""
    state = AgentState(query="test", internal_results=[], external_results=[])

    with patch("app.agent.nodes.generator.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(side_effect=Exception("LLM error"))

        result = await generator_node(state)

        assert result["error"] is not None
        assert "LLM error" in result["error"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent_generator.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write generator node implementation**

```python
# backend/app/agent/nodes/generator.py
"""Generator node - synthesizes final response from all context."""
from typing import Any

from app.agent.state import AgentState, SourceReference
from app.services.llm.client import LLMClient


GENERATOR_PROMPT = """You are HARI, a knowledge assistant. Generate a comprehensive answer to the user's question using the provided context.

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
        State update with final_answer, sources, and potential error
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

        return {
            "final_answer": response["content"],
            "sources": internal_sources + external_sources,
            "error": None,
        }

    except Exception as e:
        return {
            "final_answer": None,
            "sources": internal_sources + external_sources,
            "error": str(e),
        }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_agent_generator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/agent/nodes/generator.py backend/tests/test_agent_generator.py
git commit -m "feat(agent): add generator node for response synthesis"
```

---

## Task 9: Create Agent Graph

**Files:**
- Create: `backend/app/agent/graph.py`
- Test: `backend/tests/test_agent_graph.py`

**Step 1: Write the failing test for agent graph**

```python
# backend/tests/test_agent_graph.py
"""Tests for the agent graph."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agent.graph import create_agent_graph, run_agent
from app.agent.state import AgentState


def test_create_agent_graph_structure():
    """Test that graph is created with correct nodes."""
    graph = create_agent_graph()

    # Check graph has expected nodes
    assert graph is not None


@pytest.mark.asyncio
async def test_run_agent_sufficient_context():
    """Test agent flow when context is sufficient on first try."""
    mock_internal = [{"id": "1", "title": "Doc", "quick_summary": "Content"}]

    with patch("app.agent.graph.retriever_node", new_callable=AsyncMock) as mock_retriever, \
         patch("app.agent.graph.evaluator_node", new_callable=AsyncMock) as mock_evaluator, \
         patch("app.agent.graph.generator_node", new_callable=AsyncMock) as mock_generator:

        mock_retriever.return_value = {"internal_results": mock_internal}
        mock_evaluator.return_value = {
            "evaluation": MagicMock(is_sufficient=True, confidence=0.9)
        }
        mock_generator.return_value = {
            "final_answer": "The answer is 42.",
            "sources": [],
            "error": None,
        }

        result = await run_agent("What is the meaning of life?")

        assert result.final_answer == "The answer is 42."
        mock_retriever.assert_called_once()
        mock_evaluator.assert_called_once()
        mock_generator.assert_called_once()


@pytest.mark.asyncio
async def test_run_agent_with_research():
    """Test agent flow when external research is needed."""
    with patch("app.agent.graph.retriever_node", new_callable=AsyncMock) as mock_retriever, \
         patch("app.agent.graph.evaluator_node", new_callable=AsyncMock) as mock_evaluator, \
         patch("app.agent.graph.researcher_node", new_callable=AsyncMock) as mock_researcher, \
         patch("app.agent.graph.generator_node", new_callable=AsyncMock) as mock_generator:

        mock_retriever.return_value = {"internal_results": []}

        # First evaluation: insufficient
        # Second evaluation: sufficient (after research)
        mock_evaluator.side_effect = [
            {"evaluation": MagicMock(is_sufficient=False, confidence=0.2)},
            {"evaluation": MagicMock(is_sufficient=True, confidence=0.8)},
        ]

        mock_researcher.return_value = {
            "external_results": [{"title": "Web result"}],
            "research_iterations": 1,
        }

        mock_generator.return_value = {
            "final_answer": "Found via research.",
            "sources": [],
            "error": None,
        }

        result = await run_agent("Latest news?")

        assert result.final_answer == "Found via research."
        mock_researcher.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent_graph.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write agent graph implementation**

```python
# backend/app/agent/graph.py
"""LangGraph agent definition for agentic RAG."""
from typing import Literal
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.agent.nodes.retriever import retriever_node
from app.agent.nodes.evaluator import evaluator_node
from app.agent.nodes.router import router_node
from app.agent.nodes.researcher import researcher_node
from app.agent.nodes.generator import generator_node


def create_agent_graph() -> StateGraph:
    """
    Create the agentic RAG graph.

    Graph structure:
        START -> retrieve -> evaluate -> [router]
                                           |
                              sufficient ---> generate -> END
                                           |
                            insufficient ---> research -> evaluate (loop)
    """
    # Create graph with AgentState
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("retrieve", retriever_node)
    workflow.add_node("evaluate", evaluator_node)
    workflow.add_node("research", researcher_node)
    workflow.add_node("generate", generator_node)

    # Define edges
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "evaluate")

    # Conditional edge from evaluate based on router decision
    workflow.add_conditional_edges(
        "evaluate",
        router_node,
        {
            "generate": "generate",
            "research": "research",
        }
    )

    # Research loops back to evaluate
    workflow.add_edge("research", "evaluate")

    # Generate is terminal
    workflow.add_edge("generate", END)

    return workflow.compile()


async def run_agent(
    query: str,
    session: AsyncSession | None = None,
    max_iterations: int = 3,
) -> AgentState:
    """
    Run the agentic RAG pipeline.

    Args:
        query: User's question
        session: Database session for retrieval
        max_iterations: Maximum research iterations

    Returns:
        Final agent state with answer and sources
    """
    graph = create_agent_graph()

    initial_state = AgentState(
        query=query,
        max_iterations=max_iterations,
    )

    # Run graph - nodes will receive state and return updates
    # We need to handle the session passing separately
    config = {"configurable": {"session": session}}

    result = await graph.ainvoke(initial_state, config=config)

    # Result is a dict, convert back to AgentState
    if isinstance(result, dict):
        return AgentState(**result)
    return result
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_agent_graph.py -v`
Expected: PASS (may need adjustments based on LangGraph API)

**Step 5: Commit**

```bash
git add backend/app/agent/graph.py backend/tests/test_agent_graph.py
git commit -m "feat(agent): add LangGraph state machine with cognitive loop"
```

---

## Task 10: Update Nodes Init with All Exports

**Files:**
- Modify: `backend/app/agent/nodes/__init__.py`

**Step 1: Verify all nodes are importable**

Run: `cd backend && uv run python -c "from app.agent.nodes import retriever_node, evaluator_node, router_node, researcher_node, generator_node; print('OK')"`
Expected: `OK`

**Step 2: If imports fail, fix the init file**

```python
# backend/app/agent/nodes/__init__.py
"""Agent nodes for the LangGraph state machine."""
from app.agent.nodes.retriever import retriever_node
from app.agent.nodes.evaluator import evaluator_node
from app.agent.nodes.router import router_node
from app.agent.nodes.researcher import researcher_node
from app.agent.nodes.generator import generator_node

__all__ = [
    "retriever_node",
    "evaluator_node",
    "router_node",
    "researcher_node",
    "generator_node",
]
```

**Step 3: Commit if changes made**

```bash
git add backend/app/agent/nodes/__init__.py
git commit -m "fix(agent): update nodes init with all exports"
```

---

## Task 11: Create Agentic Query API Endpoint

**Files:**
- Modify: `backend/app/api/query.py`
- Create: `backend/app/schemas/agent.py`
- Test: `backend/tests/test_api_agent_query.py`

**Step 1: Write the failing test for agentic query endpoint**

```python
# backend/tests/test_api_agent_query.py
"""Tests for agentic query API endpoint."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.agent.state import AgentState, SourceReference


@pytest.fixture
def auth_headers():
    """Headers with API key auth."""
    return {"X-API-Key": "gorgonzola"}


@pytest.mark.asyncio
async def test_agentic_query_endpoint():
    """Test POST /api/query/agent returns agentic response."""
    mock_state = AgentState(
        query="What is Python?",
        final_answer="Python is a programming language.",
        sources=[
            SourceReference(id="1", title="Python Docs", source_type="internal")
        ],
        research_iterations=0,
    )

    with patch("app.api.query.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_state

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query/agent",
                json={"query": "What is Python?"},
                headers={"X-API-Key": "gorgonzola"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Python is a programming language."
        assert len(data["sources"]) == 1
        assert data["research_iterations"] == 0


@pytest.mark.asyncio
async def test_agentic_query_with_research():
    """Test endpoint shows when external research was performed."""
    mock_state = AgentState(
        query="Latest Python news?",
        final_answer="Python 3.13 was released.",
        sources=[
            SourceReference(title="Python.org", source_type="external", url="https://python.org")
        ],
        research_iterations=1,
    )

    with patch("app.api.query.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_state

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query/agent",
                json={"query": "Latest Python news?"},
                headers={"X-API-Key": "gorgonzola"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["research_iterations"] == 1
        assert data["sources"][0]["source_type"] == "external"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_api_agent_query.py -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Create agent response schema**

```python
# backend/app/schemas/agent.py
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
```

**Step 4: Add agentic endpoint to query router**

Add to `backend/app/api/query.py`:

```python
# Add imports at top
from app.agent.graph import run_agent
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse, AgentSourceReference


# Add new endpoint
@router.post("/agent", response_model=AgentQueryResponse)
async def agentic_query(
    data: AgentQueryRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
):
    """
    Query with agentic RAG - evaluates context sufficiency and
    automatically searches the web if internal knowledge is insufficient.
    """
    result = await run_agent(
        query=data.query,
        session=session,
        max_iterations=data.max_iterations,
    )

    if result.error:
        return AgentQueryResponse(
            answer=f"Error: {result.error}",
            sources=[],
            research_iterations=result.research_iterations,
            error=result.error,
        )

    return AgentQueryResponse(
        answer=result.final_answer or "Unable to generate response.",
        sources=[
            AgentSourceReference(
                id=s.id,
                title=s.title,
                url=s.url,
                source_type=s.source_type,
                snippet=s.snippet,
            )
            for s in result.sources
        ],
        research_iterations=result.research_iterations,
    )
```

**Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_api_agent_query.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/api/query.py backend/app/schemas/agent.py backend/tests/test_api_agent_query.py
git commit -m "feat(api): add /api/query/agent endpoint for agentic RAG"
```

---

## Task 12: Fix Session Passing in Retriever Node

**Files:**
- Modify: `backend/app/agent/nodes/retriever.py`
- Modify: `backend/app/agent/graph.py`

**Step 1: Update retriever to get session from config**

The LangGraph nodes receive config, so we need to extract session from there:

```python
# backend/app/agent/nodes/retriever.py
"""Retriever node - searches internal knowledge base."""
from typing import Any
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.services.search.hybrid import HybridSearch


async def retriever_node(
    state: AgentState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """
    Search internal knowledge base using hybrid search.

    Args:
        state: Current agent state with query
        config: LangGraph config with session in configurable

    Returns:
        State update with internal_results populated
    """
    # Extract session from config
    session = None
    if config and "configurable" in config:
        session = config["configurable"].get("session")

    search = HybridSearch(session)

    results = await search.search(
        query=state.query,
        limit=10,
        session=session,
    )

    return {"internal_results": results}
```

**Step 2: Run all agent tests**

Run: `cd backend && uv run pytest tests/test_agent_*.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add backend/app/agent/nodes/retriever.py
git commit -m "fix(agent): pass database session through LangGraph config"
```

---

## Task 13: Add Environment Variable Documentation

**Files:**
- Modify: `CLAUDE.md` (add Tavily API key instruction)

**Step 1: Update CLAUDE.md environment section**

Add to the environment variables section:

```markdown
# Tavily API (for agentic web search)
TAVILY_API_KEY=tvly-...
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Tavily API key to environment setup"
```

---

## Task 14: Integration Test

**Files:**
- Create: `backend/tests/test_agent_integration.py`

**Step 1: Write integration test**

```python
# backend/tests/test_agent_integration.py
"""Integration tests for the agentic query system."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agent.graph import run_agent
from app.agent.state import AgentState


@pytest.mark.asyncio
async def test_full_agent_flow_with_mocked_externals():
    """Test complete agent flow from query to answer."""
    # Mock the hybrid search
    mock_search_results = [
        {
            "id": "doc-1",
            "title": "Python Introduction",
            "quick_summary": "Python is a high-level programming language.",
            "url": "https://docs.python.org",
        }
    ]

    # Mock the LLM client
    mock_eval_response = {
        "content": '{"is_sufficient": true, "confidence": 0.85, "missing_information": [], "reasoning": "Context covers the basics"}'
    }
    mock_gen_response = {
        "content": "Python is a versatile, high-level programming language known for its readability and extensive libraries."
    }

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch, \
         patch("app.agent.nodes.evaluator.LLMClient") as MockEvalLLM, \
         patch("app.agent.nodes.generator.LLMClient") as MockGenLLM:

        # Setup mocks
        mock_search_instance = MockSearch.return_value
        mock_search_instance.search = AsyncMock(return_value=mock_search_results)

        mock_eval_instance = MockEvalLLM.return_value
        mock_eval_instance.complete = AsyncMock(return_value=mock_eval_response)

        mock_gen_instance = MockGenLLM.return_value
        mock_gen_instance.complete = AsyncMock(return_value=mock_gen_response)

        # Run agent
        result = await run_agent("What is Python?", session=None)

        # Verify results
        assert result.final_answer is not None
        assert "Python" in result.final_answer
        assert len(result.sources) == 1
        assert result.sources[0].source_type == "internal"
        assert result.research_iterations == 0  # No external research needed


@pytest.mark.asyncio
async def test_agent_flow_with_research():
    """Test agent triggers external research when needed."""
    mock_search_results = []  # No internal results

    mock_eval_insufficient = {
        "content": '{"is_sufficient": false, "confidence": 0.2, "missing_information": ["Python basics"], "reasoning": "No internal docs"}'
    }
    mock_eval_sufficient = {
        "content": '{"is_sufficient": true, "confidence": 0.9, "missing_information": [], "reasoning": "Web results helpful"}'
    }
    mock_gen_response = {
        "content": "Based on web research, Python is..."
    }

    with patch("app.agent.nodes.retriever.HybridSearch") as MockSearch, \
         patch("app.agent.nodes.evaluator.LLMClient") as MockEvalLLM, \
         patch("app.agent.nodes.generator.LLMClient") as MockGenLLM, \
         patch("app.agent.nodes.researcher.TavilyService") as MockTavily:

        # Setup mocks
        mock_search_instance = MockSearch.return_value
        mock_search_instance.search = AsyncMock(return_value=mock_search_results)

        mock_eval_instance = MockEvalLLM.return_value
        mock_eval_instance.complete = AsyncMock(
            side_effect=[mock_eval_insufficient, mock_eval_sufficient]
        )

        mock_gen_instance = MockGenLLM.return_value
        mock_gen_instance.complete = AsyncMock(return_value=mock_gen_response)

        mock_tavily_instance = MockTavily.return_value
        mock_tavily_instance.search = AsyncMock(return_value=[
            MagicMock(title="Python.org", url="https://python.org", content="Python info", score=0.9)
        ])

        # Run agent
        result = await run_agent("What is Python?", session=None)

        # Verify external research was performed
        assert result.research_iterations >= 1
        mock_tavily_instance.search.assert_called()
```

**Step 2: Run integration test**

Run: `cd backend && uv run pytest tests/test_agent_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_agent_integration.py
git commit -m "test(agent): add integration tests for agentic flow"
```

---

## Task 15: Run Full Test Suite

**Step 1: Run all tests**

Run: `cd backend && uv run pytest -v`
Expected: All tests PASS

**Step 2: Run linting**

Run: `cd backend && uv run ruff check app tests`
Expected: No errors (or fix any that appear)

**Step 3: Final commit if any fixes**

```bash
git add -A
git commit -m "fix: address linting issues in agent module"
```

---

## Summary

This plan implements the core agentic query system:

1. **Tasks 1-2**: Setup dependencies and state schema
2. **Tasks 3-8**: Implement all 5 agent nodes (retriever, evaluator, router, researcher, generator)
3. **Task 9**: Wire up LangGraph state machine
4. **Tasks 10-11**: Create API endpoint
5. **Tasks 12-15**: Fix integration issues, add docs, run tests

**Not included in this plan** (future phases):
- SSE streaming endpoint (Phase 2)
- Telegram/Slack integrations (Phase 3.2-3.3)
- Quality validation (Phase 4)
- Observability (Phase 6)

These can be planned separately after the core agent is working.
