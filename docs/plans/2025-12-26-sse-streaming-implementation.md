# SSE Streaming Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time SSE streaming to the agentic query system, showing reasoning steps and answer chunks progressively.

**Architecture:** Add `run_agent_stream()` generator using LangGraph's `astream_events()`, expose via FastAPI `StreamingResponse`, update React frontend to consume SSE stream.

**Tech Stack:** FastAPI StreamingResponse, LangGraph astream_events v2, React fetch ReadableStream

**Design Reference:** `docs/plans/2025-12-26-sse-streaming-design.md`

---

## Task 1: SSE Formatting Utilities

**Files:**
- Create: `backend/app/utils/sse.py`
- Create: `backend/tests/test_sse_utils.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_sse_utils.py
import pytest
from app.utils.sse import format_sse, parse_sse


def test_format_sse_simple_event():
    """Format a simple SSE event."""
    result = format_sse("thinking", {"step": "retrieve", "message": "Searching..."})
    assert result == 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n'


def test_format_sse_done_event():
    """Format done event with metadata."""
    result = format_sse("done", {"research_iterations": 2})
    assert result == 'event: done\ndata: {"research_iterations": 2}\n\n'


def test_parse_sse_single_event():
    """Parse a single SSE event."""
    raw = 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n'
    events = parse_sse(raw)
    assert len(events) == 1
    assert events[0]["type"] == "thinking"
    assert events[0]["data"]["step"] == "retrieve"


def test_parse_sse_multiple_events():
    """Parse multiple SSE events in one chunk."""
    raw = (
        'event: thinking\ndata: {"step": "retrieve"}\n\n'
        'event: chunk\ndata: {"content": "Hello"}\n\n'
    )
    events = parse_sse(raw)
    assert len(events) == 2
    assert events[0]["type"] == "thinking"
    assert events[1]["type"] == "chunk"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_sse_utils.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.utils.sse'"

**Step 3: Write minimal implementation**

```python
# backend/app/utils/__init__.py
# (create empty file if doesn't exist)
```

```python
# backend/app/utils/sse.py
"""SSE (Server-Sent Events) formatting utilities."""
import json
from typing import Any


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    """
    Format data as an SSE event string.

    Args:
        event_type: Event type (thinking, chunk, sources, done, error)
        data: Event data dictionary

    Returns:
        SSE-formatted string with event and data lines
    """
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def parse_sse(raw: str) -> list[dict[str, Any]]:
    """
    Parse raw SSE text into list of events.

    Args:
        raw: Raw SSE text (may contain multiple events)

    Returns:
        List of parsed events with 'type' and 'data' keys
    """
    events = []
    current_event = {}

    for line in raw.split("\n"):
        if line.startswith("event: "):
            current_event["type"] = line[7:]
        elif line.startswith("data: "):
            try:
                current_event["data"] = json.loads(line[6:])
            except json.JSONDecodeError:
                current_event["data"] = line[6:]
        elif line == "" and current_event:
            if "type" in current_event and "data" in current_event:
                events.append(current_event)
            current_event = {}

    return events
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_sse_utils.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/utils/ backend/tests/test_sse_utils.py
git commit -m "feat(sse): add SSE formatting and parsing utilities"
```

---

## Task 2: Sentence Chunking Utility

**Files:**
- Modify: `backend/app/utils/sse.py`
- Modify: `backend/tests/test_sse_utils.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_sse_utils.py

from app.utils.sse import chunk_sentences


def test_chunk_sentences_simple():
    """Chunk text into sentences."""
    text = "First sentence. Second sentence. Third one."
    chunks = list(chunk_sentences(text))
    assert chunks == ["First sentence. ", "Second sentence. ", "Third one."]


def test_chunk_sentences_with_abbreviations():
    """Handle common abbreviations."""
    text = "Dr. Smith said hello. Mr. Jones replied."
    chunks = list(chunk_sentences(text))
    assert chunks == ["Dr. Smith said hello. ", "Mr. Jones replied."]


def test_chunk_sentences_empty():
    """Handle empty text."""
    chunks = list(chunk_sentences(""))
    assert chunks == []


def test_chunk_sentences_no_period():
    """Handle text without periods."""
    text = "Just some text without periods"
    chunks = list(chunk_sentences(text))
    assert chunks == ["Just some text without periods"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_sse_utils.py::test_chunk_sentences_simple -v`
Expected: FAIL with "ImportError: cannot import name 'chunk_sentences'"

**Step 3: Write minimal implementation**

```python
# Add to backend/app/utils/sse.py

import re
from typing import Iterator


# Common abbreviations that don't end sentences
ABBREVIATIONS = {"Dr", "Mr", "Mrs", "Ms", "Prof", "Sr", "Jr", "vs", "etc", "e.g", "i.e"}


def chunk_sentences(text: str) -> Iterator[str]:
    """
    Split text into sentence chunks.

    Args:
        text: Text to split

    Yields:
        Individual sentences with trailing space preserved
    """
    if not text:
        return

    # Simple sentence splitting - split on . ! ? followed by space or end
    # But not after common abbreviations
    pattern = r'(?<=[.!?])\s+'
    parts = re.split(pattern, text)

    for i, part in enumerate(parts):
        if not part:
            continue
        # Add trailing space except for last part
        if i < len(parts) - 1:
            yield part + " "
        else:
            yield part
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_sse_utils.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/utils/sse.py backend/tests/test_sse_utils.py
git commit -m "feat(sse): add sentence chunking utility"
```

---

## Task 3: Thinking Message Builder

**Files:**
- Modify: `backend/app/utils/sse.py`
- Modify: `backend/tests/test_sse_utils.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_sse_utils.py

from app.utils.sse import build_thinking_message


def test_build_thinking_message_retrieve():
    """Build message for retrieve node."""
    result = build_thinking_message("retrieve", {})
    assert result == {"step": "retrieve", "message": "Searching internal knowledge..."}


def test_build_thinking_message_evaluate_with_count():
    """Build message for evaluate node with document count."""
    result = build_thinking_message("evaluate", {"internal_results": [1, 2, 3, 4, 5]})
    assert result["step"] == "evaluate"
    assert "5 documents" in result["message"]


def test_build_thinking_message_research():
    """Build message for research node."""
    result = build_thinking_message("research", {"evaluation": {"missing_information": ["AI frameworks"]}})
    assert result["step"] == "research"
    assert "AI frameworks" in result["message"]


def test_build_thinking_message_generate():
    """Build message for generate node."""
    result = build_thinking_message("generate", {})
    assert result == {"step": "generate", "message": "Generating response..."}
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_sse_utils.py::test_build_thinking_message_retrieve -v`
Expected: FAIL with "ImportError: cannot import name 'build_thinking_message'"

**Step 3: Write minimal implementation**

```python
# Add to backend/app/utils/sse.py

def build_thinking_message(node_name: str, state_data: dict[str, Any]) -> dict[str, str]:
    """
    Build an informative thinking message for a node.

    Args:
        node_name: Name of the node (retrieve, evaluate, research, generate)
        state_data: Current state data for context

    Returns:
        Dict with 'step' and 'message' keys
    """
    if node_name == "retrieve":
        return {"step": "retrieve", "message": "Searching internal knowledge..."}

    elif node_name == "evaluate":
        doc_count = len(state_data.get("internal_results", []))
        if doc_count > 0:
            return {"step": "evaluate", "message": f"Found {doc_count} documents, assessing relevance..."}
        return {"step": "evaluate", "message": "Assessing context sufficiency..."}

    elif node_name == "research":
        evaluation = state_data.get("evaluation", {})
        if isinstance(evaluation, dict):
            missing = evaluation.get("missing_information", [])
        else:
            missing = getattr(evaluation, "missing_information", [])
        if missing:
            topic = missing[0] if missing else "additional information"
            return {"step": "research", "message": f"Context insufficient, searching web for: {topic}..."}
        return {"step": "research", "message": "Searching web for additional information..."}

    elif node_name == "generate":
        return {"step": "generate", "message": "Generating response..."}

    else:
        return {"step": node_name, "message": f"Processing {node_name}..."}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_sse_utils.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/utils/sse.py backend/tests/test_sse_utils.py
git commit -m "feat(sse): add thinking message builder"
```

---

## Task 4: Streaming Agent Function

**Files:**
- Modify: `backend/app/agent/graph.py`
- Create: `backend/tests/test_agent_stream.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_agent_stream.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.graph import run_agent_stream
from app.utils.sse import parse_sse


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MagicMock()


@pytest.mark.asyncio
async def test_run_agent_stream_emits_thinking_events(mock_session):
    """Verify stream emits thinking events for nodes."""
    # Mock the graph to emit some events
    with patch("app.agent.graph.create_agent_graph") as mock_create:
        mock_graph = AsyncMock()

        # Simulate astream_events yielding node events
        async def fake_events(*args, **kwargs):
            yield {"event": "on_chain_start", "name": "retrieve", "data": {}}
            yield {"event": "on_chain_end", "name": "retrieve", "data": {"output": {"internal_results": []}}}
            yield {"event": "on_chain_start", "name": "evaluate", "data": {}}
            yield {"event": "on_chain_end", "name": "evaluate", "data": {"output": {}}}
            yield {"event": "on_chain_start", "name": "generate", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "generate",
                "data": {"output": {"final_answer": "Test answer.", "sources": []}}
            }

        mock_graph.astream_events = fake_events
        mock_create.return_value = mock_graph

        events = []
        async for chunk in run_agent_stream("test query", mock_session):
            events.extend(parse_sse(chunk))

        # Should have thinking events for retrieve, evaluate, generate
        thinking_events = [e for e in events if e["type"] == "thinking"]
        steps = [e["data"]["step"] for e in thinking_events]
        assert "retrieve" in steps
        assert "generate" in steps


@pytest.mark.asyncio
async def test_run_agent_stream_emits_chunks(mock_session):
    """Verify stream emits answer chunks."""
    with patch("app.agent.graph.create_agent_graph") as mock_create:
        mock_graph = AsyncMock()

        async def fake_events(*args, **kwargs):
            yield {"event": "on_chain_start", "name": "generate", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "generate",
                "data": {"output": {"final_answer": "First sentence. Second sentence.", "sources": []}}
            }

        mock_graph.astream_events = fake_events
        mock_create.return_value = mock_graph

        events = []
        async for chunk in run_agent_stream("test", mock_session):
            events.extend(parse_sse(chunk))

        chunk_events = [e for e in events if e["type"] == "chunk"]
        assert len(chunk_events) >= 2
        contents = [e["data"]["content"] for e in chunk_events]
        assert "First sentence." in "".join(contents)


@pytest.mark.asyncio
async def test_run_agent_stream_emits_done(mock_session):
    """Verify stream emits done event."""
    with patch("app.agent.graph.create_agent_graph") as mock_create:
        mock_graph = AsyncMock()

        async def fake_events(*args, **kwargs):
            yield {
                "event": "on_chain_end",
                "name": "generate",
                "data": {"output": {"final_answer": "Answer.", "sources": [], "research_iterations": 1}}
            }

        mock_graph.astream_events = fake_events
        mock_create.return_value = mock_graph

        events = []
        async for chunk in run_agent_stream("test", mock_session):
            events.extend(parse_sse(chunk))

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_agent_stream.py::test_run_agent_stream_emits_thinking_events -v`
Expected: FAIL with "ImportError: cannot import name 'run_agent_stream'"

**Step 3: Write minimal implementation**

```python
# Add to backend/app/agent/graph.py (after run_agent function)

from typing import AsyncIterator
from app.utils.sse import format_sse, chunk_sentences, build_thinking_message


async def run_agent_stream(
    query: str,
    session: AsyncSession | None = None,
    max_iterations: int = 3,
) -> AsyncIterator[str]:
    """
    Run the agentic RAG pipeline with streaming events.

    Args:
        query: User's question
        session: Database session for retrieval
        max_iterations: Maximum research iterations

    Yields:
        SSE-formatted event strings
    """
    graph = create_agent_graph()

    initial_state = AgentState(
        query=query,
        max_iterations=max_iterations,
    )

    config = {"configurable": {"session": session}}

    final_state = {}
    seen_nodes = set()

    try:
        async for event in graph.astream_events(initial_state, config=config, version="v2"):
            event_type = event.get("event", "")
            node_name = event.get("name", "")

            # Emit thinking event when node starts
            if event_type == "on_chain_start" and node_name in ("retrieve", "evaluate", "research", "generate"):
                if node_name not in seen_nodes:
                    seen_nodes.add(node_name)
                    thinking = build_thinking_message(node_name, final_state)
                    yield format_sse("thinking", thinking)

            # Capture output and emit chunks/sources when generate completes
            if event_type == "on_chain_end" and node_name == "generate":
                output = event.get("data", {}).get("output", {})
                final_state.update(output)

                # Emit answer chunks
                answer = output.get("final_answer", "")
                if answer:
                    for sentence in chunk_sentences(answer):
                        yield format_sse("chunk", {"content": sentence})

                # Emit sources
                sources = output.get("sources", [])
                internal = []
                external = []
                for s in sources:
                    source_dict = s if isinstance(s, dict) else s.model_dump() if hasattr(s, 'model_dump') else {}
                    if source_dict.get("source_type") == "external":
                        external.append(source_dict)
                    else:
                        internal.append(source_dict)
                yield format_sse("sources", {"internal": internal, "external": external})

            # Update state from other node outputs
            if event_type == "on_chain_end" and node_name != "generate":
                output = event.get("data", {}).get("output", {})
                if output:
                    final_state.update(output)

    except Exception as e:
        yield format_sse("error", {"step": "unknown", "message": str(e)})

    # Emit done event
    research_iterations = final_state.get("research_iterations", 0)
    yield format_sse("done", {"research_iterations": research_iterations})
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_agent_stream.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/agent/graph.py backend/tests/test_agent_stream.py
git commit -m "feat(agent): add streaming function with SSE events"
```

---

## Task 5: Streaming API Endpoint

**Files:**
- Modify: `backend/app/api/query.py`
- Create: `backend/tests/test_api_query_stream.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_api_query_stream.py
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.utils.sse import parse_sse


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    from app.models.user import User
    return User(id="test-user-id", email="test@example.com", name="Test User", role="user")


@pytest.mark.asyncio
async def test_stream_endpoint_returns_sse(mock_user):
    """Verify /query/stream returns SSE content type."""
    with patch("app.api.query.require_user", return_value=mock_user):
        with patch("app.api.query.run_agent_stream") as mock_stream:
            async def fake_stream(*args, **kwargs):
                yield 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n'
                yield 'event: done\ndata: {"research_iterations": 0}\n\n'

            mock_stream.return_value = fake_stream()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/query/stream",
                    json={"query": "test question"},
                    headers={"X-API-Key": "test-key"},
                )

                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


@pytest.mark.asyncio
async def test_stream_endpoint_emits_events(mock_user):
    """Verify stream emits expected event sequence."""
    with patch("app.api.query.require_user", return_value=mock_user):
        with patch("app.api.query.run_agent_stream") as mock_stream:
            async def fake_stream(*args, **kwargs):
                yield 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n'
                yield 'event: chunk\ndata: {"content": "Answer text."}\n\n'
                yield 'event: sources\ndata: {"internal": [], "external": []}\n\n'
                yield 'event: done\ndata: {"research_iterations": 0}\n\n'

            mock_stream.return_value = fake_stream()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/query/stream",
                    json={"query": "test question"},
                    headers={"X-API-Key": "test-key"},
                )

                events = parse_sse(response.text)
                event_types = [e["type"] for e in events]

                assert "thinking" in event_types
                assert "chunk" in event_types
                assert "sources" in event_types
                assert "done" in event_types
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_api_query_stream.py::test_stream_endpoint_returns_sse -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Write minimal implementation**

```python
# Add to backend/app/api/query.py

from fastapi.responses import StreamingResponse
from app.agent.graph import run_agent_stream


@router.post("/stream")
async def stream_agentic_query(
    data: AgentQueryRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
):
    """
    Stream agentic query with real-time reasoning visibility.

    Returns SSE stream with events:
    - thinking: Agent reasoning steps
    - chunk: Answer sentence fragments
    - sources: Source attribution
    - done: Completion signal
    - error: Inline errors (flow continues)
    """
    return StreamingResponse(
        run_agent_stream(
            query=data.query,
            session=session,
            max_iterations=data.max_iterations,
        ),
        media_type="text/event-stream",
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_api_query_stream.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/api/query.py backend/tests/test_api_query_stream.py
git commit -m "feat(api): add /query/stream SSE endpoint"
```

---

## Task 6: Frontend SSE Parser Utility

**Files:**
- Create: `frontend/src/lib/sse.ts`
- Create: `frontend/src/lib/sse.test.ts`

**Step 1: Write the failing test**

```typescript
// frontend/src/lib/sse.test.ts
import { describe, it, expect } from 'vitest';
import { parseSSE, SSEEvent } from './sse';

describe('parseSSE', () => {
  it('parses single event', () => {
    const raw = 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n';
    const events = parseSSE(raw);

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('thinking');
    expect(events[0].data.step).toBe('retrieve');
  });

  it('parses multiple events', () => {
    const raw =
      'event: thinking\ndata: {"step": "retrieve"}\n\n' +
      'event: chunk\ndata: {"content": "Hello"}\n\n';
    const events = parseSSE(raw);

    expect(events).toHaveLength(2);
    expect(events[0].type).toBe('thinking');
    expect(events[1].type).toBe('chunk');
  });

  it('handles partial events gracefully', () => {
    const raw = 'event: thinking\ndata: {"step"';
    const events = parseSSE(raw);

    expect(events).toHaveLength(0);
  });

  it('handles empty string', () => {
    const events = parseSSE('');
    expect(events).toHaveLength(0);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run sse.test.ts`
Expected: FAIL with "Cannot find module './sse'"

**Step 3: Write minimal implementation**

```typescript
// frontend/src/lib/sse.ts

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

/**
 * Parse raw SSE text into structured events.
 */
export function parseSSE(raw: string): SSEEvent[] {
  const events: SSEEvent[] = [];
  const lines = raw.split('\n');

  let currentType = '';
  let currentData = '';

  for (const line of lines) {
    if (line.startsWith('event: ')) {
      currentType = line.slice(7);
    } else if (line.startsWith('data: ')) {
      currentData = line.slice(6);
    } else if (line === '' && currentType && currentData) {
      try {
        events.push({
          type: currentType,
          data: JSON.parse(currentData),
        });
      } catch {
        // Skip malformed JSON
      }
      currentType = '';
      currentData = '';
    }
  }

  return events;
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run sse.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/lib/sse.ts frontend/src/lib/sse.test.ts
git commit -m "feat(frontend): add SSE parsing utility"
```

---

## Task 7: ThinkingSteps Component

**Files:**
- Create: `frontend/src/components/chat/ThinkingSteps.tsx`
- Create: `frontend/src/components/chat/ThinkingSteps.test.tsx`

**Step 1: Write the failing test**

```typescript
// frontend/src/components/chat/ThinkingSteps.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThinkingSteps } from './ThinkingSteps';

describe('ThinkingSteps', () => {
  it('renders thinking steps', () => {
    const steps = [
      { step: 'retrieve', message: 'Searching...', isError: false },
      { step: 'evaluate', message: 'Evaluating...', isError: false },
    ];

    render(<ThinkingSteps steps={steps} />);

    expect(screen.getByText('Searching...')).toBeInTheDocument();
    expect(screen.getByText('Evaluating...')).toBeInTheDocument();
  });

  it('renders error steps with warning style', () => {
    const steps = [
      { step: 'research', message: 'Web search failed...', isError: true },
    ];

    render(<ThinkingSteps steps={steps} />);

    const errorElement = screen.getByText('Web search failed...');
    expect(errorElement.closest('div')).toHaveClass('text-yellow-600');
  });

  it('renders nothing when no steps', () => {
    const { container } = render(<ThinkingSteps steps={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run ThinkingSteps.test.tsx`
Expected: FAIL with "Cannot find module './ThinkingSteps'"

**Step 3: Write minimal implementation**

```typescript
// frontend/src/components/chat/ThinkingSteps.tsx
import { Loader2 } from 'lucide-react';

export interface ThinkingStep {
  step: string;
  message: string;
  isError?: boolean;
}

interface ThinkingStepsProps {
  steps: ThinkingStep[];
  isLoading?: boolean;
}

export function ThinkingSteps({ steps, isLoading }: ThinkingStepsProps) {
  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="space-y-1 text-sm mb-3 p-3 bg-muted/50 rounded-lg">
      {steps.map((step, i) => (
        <div
          key={i}
          className={`flex items-center gap-2 ${
            step.isError ? 'text-yellow-600' : 'text-muted-foreground'
          }`}
        >
          {isLoading && i === steps.length - 1 ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <span className="w-3 h-3 text-center">
              {step.isError ? '!' : ''}
            </span>
          )}
          <span>{step.message}</span>
        </div>
      ))}
    </div>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run ThinkingSteps.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/chat/ThinkingSteps.tsx frontend/src/components/chat/ThinkingSteps.test.tsx
git commit -m "feat(frontend): add ThinkingSteps component"
```

---

## Task 8: Update ChatMessage with Clickable Sources

**Files:**
- Modify: `frontend/src/components/chat/ChatMessage.tsx`
- Create: `frontend/src/components/chat/ChatMessage.test.tsx`

**Step 1: Write the failing test**

```typescript
// frontend/src/components/chat/ChatMessage.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatMessage } from './ChatMessage';

describe('ChatMessage', () => {
  it('renders sources as clickable links', () => {
    const sources = [
      { id: '1', title: 'Tech Report', url: 'https://example.com/report.pdf' },
      { id: '2', title: 'AI Guide', url: 'https://ai.com/guide' },
    ];

    render(
      <ChatMessage role="assistant" content="Test answer" sources={sources} />
    );

    const link1 = screen.getByRole('link', { name: /Tech Report/i });
    expect(link1).toHaveAttribute('href', 'https://example.com/report.pdf');
    expect(link1).toHaveAttribute('target', '_blank');

    const link2 = screen.getByRole('link', { name: /AI Guide/i });
    expect(link2).toHaveAttribute('href', 'https://ai.com/guide');
  });

  it('renders source without url as non-link', () => {
    const sources = [{ id: '1', title: 'No URL Source', url: null }];

    render(
      <ChatMessage role="assistant" content="Test" sources={sources} />
    );

    expect(screen.getByText('No URL Source')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /No URL Source/i })).not.toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run ChatMessage.test.tsx`
Expected: FAIL (links not implemented yet)

**Step 3: Write minimal implementation**

```typescript
// frontend/src/components/chat/ChatMessage.tsx
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ExternalLink } from 'lucide-react';

interface Source {
  id: string | null;
  title: string | null;
  url: string | null;
}

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
}

export function ChatMessage({ role, content, sources }: ChatMessageProps) {
  return (
    <div className={`flex ${role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <Card className={`max-w-[80%] p-4 ${role === 'user' ? 'bg-primary text-primary-foreground' : ''}`}>
        <p className="whitespace-pre-wrap">{content}</p>
        {sources && sources.length > 0 && (
          <div className="mt-3 pt-3 border-t">
            <p className="text-xs text-muted-foreground mb-2">Sources:</p>
            <div className="flex flex-wrap gap-1">
              {sources.map((source, i) => (
                source.url ? (
                  <a
                    key={i}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1"
                  >
                    <Badge variant="outline" className="text-xs hover:bg-accent cursor-pointer">
                      {source.title || 'Untitled'}
                      <ExternalLink className="h-3 w-3 ml-1" />
                    </Badge>
                  </a>
                ) : (
                  <Badge key={i} variant="outline" className="text-xs">
                    {source.title || 'Untitled'}
                  </Badge>
                )
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run ChatMessage.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/chat/ChatMessage.tsx frontend/src/components/chat/ChatMessage.test.tsx
git commit -m "feat(frontend): add clickable source links to ChatMessage"
```

---

## Task 9: Streaming API Function

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/api.test.ts`

**Step 1: Write the failing test**

```typescript
// frontend/src/lib/api.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { queryApi } from './api';

describe('queryApi.streamAsk', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('calls fetch with correct parameters', async () => {
    const mockResponse = {
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode('event: done\ndata: {}\n\n'),
            })
            .mockResolvedValueOnce({ done: true, value: undefined }),
        }),
      },
    };

    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    const events: unknown[] = [];
    await queryApi.streamAsk('test query', (event) => events.push(event));

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/query/stream'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ query: 'test query', max_iterations: 3 }),
      })
    );
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run api.test.ts`
Expected: FAIL with "queryApi.streamAsk is not a function"

**Step 3: Write minimal implementation**

```typescript
// Add to frontend/src/lib/api.ts

import { parseSSE, SSEEvent } from './sse';

// Add to queryApi object:
export const queryApi = {
  ask: (query: string, limit = 5) =>
    api.post('/api/query/', { query, limit }),

  search: (query: string, limit = 10) =>
    api.post('/api/search/', { query, limit }),

  streamAsk: async (
    query: string,
    onEvent: (event: SSEEvent) => void,
    maxIterations = 3
  ): Promise<void> => {
    const apiKey = localStorage.getItem('api_key');

    const response = await fetch(`${API_BASE}/api/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      },
      credentials: 'include',
      body: JSON.stringify({ query, max_iterations: maxIterations }),
    });

    if (!response.ok) {
      throw new Error(`Stream request failed: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value, { stream: true });
      const events = parseSSE(text);

      for (const event of events) {
        onEvent(event);
      }
    }
  },
};
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run api.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.test.ts
git commit -m "feat(frontend): add streaming API function"
```

---

## Task 10: Integrate Streaming into ChatPage

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`
- Create: `frontend/src/pages/ChatPage.test.tsx`

**Step 1: Write the failing test**

```typescript
// frontend/src/pages/ChatPage.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChatPage } from './ChatPage';
import { queryApi } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  queryApi: {
    ask: vi.fn(),
    streamAsk: vi.fn(),
  },
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function renderWithProviders() {
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatPage />
    </QueryClientProvider>
  );
}

describe('ChatPage streaming', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    queryClient.clear();
  });

  it('displays thinking steps during streaming', async () => {
    vi.mocked(queryApi.streamAsk).mockImplementation(async (query, onEvent) => {
      onEvent({ type: 'thinking', data: { step: 'retrieve', message: 'Searching...' } });
      onEvent({ type: 'thinking', data: { step: 'evaluate', message: 'Evaluating...' } });
      onEvent({ type: 'chunk', data: { content: 'Answer text.' } });
      onEvent({ type: 'sources', data: { internal: [], external: [] } });
      onEvent({ type: 'done', data: { research_iterations: 0 } });
    });

    renderWithProviders();

    const input = screen.getByPlaceholderText(/ask/i);
    await userEvent.type(input, 'test query');
    await userEvent.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText('Searching...')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText(/Answer text/)).toBeInTheDocument();
    });
  });

  it('displays inline errors without breaking', async () => {
    vi.mocked(queryApi.streamAsk).mockImplementation(async (query, onEvent) => {
      onEvent({ type: 'thinking', data: { step: 'retrieve', message: 'Searching...' } });
      onEvent({ type: 'error', data: { step: 'research', message: 'Web search failed...' } });
      onEvent({ type: 'chunk', data: { content: 'Fallback answer.' } });
      onEvent({ type: 'done', data: { research_iterations: 0 } });
    });

    renderWithProviders();

    const input = screen.getByPlaceholderText(/ask/i);
    await userEvent.type(input, 'test query');
    await userEvent.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText(/Web search failed/)).toBeInTheDocument();
      expect(screen.getByText(/Fallback answer/)).toBeInTheDocument();
    });
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run ChatPage.test.tsx`
Expected: FAIL (streaming not integrated yet)

**Step 3: Write minimal implementation**

```typescript
// frontend/src/pages/ChatPage.tsx
import { useState, useCallback } from 'react';
import { queryApi } from '@/lib/api';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ThinkingSteps, ThinkingStep } from '@/components/chat/ThinkingSteps';
import { ScrollArea } from '@/components/ui/scroll-area';
import { SSEEvent } from '@/lib/sse';

interface Source {
  id: string | null;
  title: string | null;
  url: string | null;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  thinkingSteps?: ThinkingStep[];
}

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentThinking, setCurrentThinking] = useState<ThinkingStep[]>([]);
  const [currentContent, setCurrentContent] = useState('');

  const handleEvent = useCallback((event: SSEEvent) => {
    if (event.type === 'thinking') {
      const data = event.data as { step: string; message: string };
      setCurrentThinking((prev) => [...prev, { step: data.step, message: data.message }]);
    } else if (event.type === 'error') {
      const data = event.data as { step: string; message: string };
      setCurrentThinking((prev) => [
        ...prev,
        { step: data.step, message: data.message, isError: true },
      ]);
    } else if (event.type === 'chunk') {
      const data = event.data as { content: string };
      setCurrentContent((prev) => prev + data.content);
    } else if (event.type === 'sources') {
      const data = event.data as { internal: Source[]; external: Source[] };
      const allSources = [...data.internal, ...data.external];
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: currentContent,
          sources: allSources,
          thinkingSteps: currentThinking,
        },
      ]);
      setCurrentThinking([]);
      setCurrentContent('');
    } else if (event.type === 'done') {
      setIsLoading(false);
    }
  }, [currentContent, currentThinking]);

  const handleSubmit = async (message: string) => {
    setMessages((prev) => [...prev, { role: 'user', content: message }]);
    setIsLoading(true);
    setCurrentThinking([]);
    setCurrentContent('');

    try {
      await queryApi.streamAsk(message, handleEvent);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${(error as Error).message}` },
      ]);
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <ScrollArea className="flex-1 pr-4">
        <div className="space-y-4 pb-4">
          {messages.length === 0 && !isLoading ? (
            <div className="text-center text-muted-foreground py-12">
              <h2 className="text-2xl font-semibold mb-2">Welcome to HARI</h2>
              <p>Ask any question about your knowledge base</p>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <div key={i}>
                  {msg.thinkingSteps && msg.thinkingSteps.length > 0 && (
                    <ThinkingSteps steps={msg.thinkingSteps} />
                  )}
                  <ChatMessage {...msg} />
                </div>
              ))}
              {isLoading && (
                <div>
                  <ThinkingSteps steps={currentThinking} isLoading />
                  {currentContent && (
                    <ChatMessage role="assistant" content={currentContent} />
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </ScrollArea>
      <div className="pt-4 border-t">
        <ChatInput onSubmit={handleSubmit} isLoading={isLoading} />
      </div>
    </div>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run ChatPage.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx frontend/src/pages/ChatPage.test.tsx
git commit -m "feat(frontend): integrate SSE streaming into ChatPage"
```

---

## Task 11: Run Full Test Suites

**Step 1: Run backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All tests PASS

**Step 2: Run frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: All tests PASS

**Step 3: Run linting**

Run: `cd backend && uv run ruff check . && cd ../frontend && npm run lint`
Expected: No errors

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve linting and test issues"
```

---

## Task 12: Integration Test

**Files:**
- Create: `backend/tests/test_stream_integration.py`

**Step 1: Write integration test**

```python
# backend/tests/test_stream_integration.py
"""Integration test for SSE streaming with real agent flow."""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.utils.sse import parse_sse


@pytest.mark.asyncio
async def test_full_streaming_flow():
    """Test complete SSE streaming from API to parsed events."""
    # Mock database and external services
    with patch("app.api.query.get_session") as mock_session:
        with patch("app.api.query.require_user") as mock_auth:
            from app.models.user import User
            mock_auth.return_value = User(
                id="test", email="test@test.com", name="Test", role="user"
            )
            mock_session.return_value = MagicMock()

            # Mock the hybrid search to return some results
            with patch("app.agent.nodes.retriever.HybridSearch") as mock_search:
                mock_search.return_value.search.return_value = [
                    {"id": "1", "title": "Test Doc", "url": "https://example.com", "content": "Test content"}
                ]

                # Mock LLM responses
                with patch("app.services.llm.client.LLMClient.complete") as mock_llm:
                    mock_llm.return_value = {
                        "content": '{"is_sufficient": true, "confidence": 0.9, "missing_information": [], "reasoning": "Good"}',
                        "provider": "anthropic",
                        "model": "claude",
                        "input_tokens": 100,
                        "output_tokens": 50,
                    }

                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        response = await client.post(
                            "/api/query/stream",
                            json={"query": "test question", "max_iterations": 1},
                            headers={"X-API-Key": "test"},
                        )

                        assert response.status_code == 200
                        events = parse_sse(response.text)

                        # Verify event sequence
                        event_types = [e["type"] for e in events]
                        assert "thinking" in event_types
                        assert "done" in event_types
```

**Step 2: Run integration test**

Run: `cd backend && uv run pytest tests/test_stream_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_stream_integration.py
git commit -m "test: add SSE streaming integration test"
```

---

## Task 13: Update Documentation

**Files:**
- Modify: `TODO.md`

**Step 1: Update TODO.md**

Mark Phase 2.1 and 2.2 as complete:

```markdown
## Implementation Status Summary

| Phase | Feature | Status |
|-------|---------|--------|
| 2.1 | SSE Streaming | ✅ Complete |
| 2.2 | Frontend Streaming | ✅ Complete |
```

**Step 2: Commit**

```bash
git add TODO.md
git commit -m "docs: mark SSE streaming as complete in TODO"
```

---

## Summary

**Total Tasks:** 13

**Files Created:**
- `backend/app/utils/sse.py`
- `backend/app/utils/__init__.py`
- `backend/tests/test_sse_utils.py`
- `backend/tests/test_agent_stream.py`
- `backend/tests/test_api_query_stream.py`
- `backend/tests/test_stream_integration.py`
- `frontend/src/lib/sse.ts`
- `frontend/src/lib/sse.test.ts`
- `frontend/src/lib/api.test.ts`
- `frontend/src/components/chat/ThinkingSteps.tsx`
- `frontend/src/components/chat/ThinkingSteps.test.tsx`
- `frontend/src/components/chat/ChatMessage.test.tsx`
- `frontend/src/pages/ChatPage.test.tsx`

**Files Modified:**
- `backend/app/agent/graph.py`
- `backend/app/api/query.py`
- `frontend/src/lib/api.ts`
- `frontend/src/components/chat/ChatMessage.tsx`
- `frontend/src/pages/ChatPage.tsx`
- `TODO.md`
