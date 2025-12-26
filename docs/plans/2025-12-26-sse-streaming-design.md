# SSE Streaming Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time streaming to the agentic query system, showing reasoning steps and answer chunks as they happen.

**Architecture:** LangGraph native streaming via `astream_events()`, with SSE endpoint and progressive frontend rendering.

**Tech Stack:** FastAPI StreamingResponse, LangGraph astream_events, React fetch ReadableStream

---

## Event Types

```
event: thinking
data: {"step": "retrieve", "message": "Searching internal knowledge..."}

event: thinking
data: {"step": "evaluate", "message": "Found 5 documents, assessing relevance..."}

event: thinking
data: {"step": "research", "message": "Context insufficient, searching web for: AI frameworks..."}

event: thinking
data: {"step": "generate", "message": "Generating response..."}

event: chunk
data: {"content": "Based on the available information, "}

event: chunk
data: {"content": "here are the key frameworks..."}

event: sources
data: {
  "internal": [
    {"id": "uuid", "title": "Tech Trends 2025", "url": "https://deloitte.com/tech-trends-2025.pdf", "snippet": "..."}
  ],
  "external": [
    {"title": "AI Frameworks Guide", "url": "https://example.com/article", "snippet": "..."}
  ]
}

event: done
data: {"research_iterations": 1}

event: error
data: {"step": "research", "message": "Web search failed, continuing with internal knowledge..."}
```

### Event Descriptions

| Event | Purpose |
|-------|---------|
| `thinking` | Agent reasoning steps (informative level) |
| `chunk` | Sentence fragments of the answer |
| `sources` | Final source attribution with original URLs |
| `done` | Completion signal with metadata |
| `error` | Inline error (flow continues) |

### Source URLs

- **Internal sources**: Use original source URL (where document was fetched from), not internal API path
- **External sources**: Keep original URLs from Tavily
- Both are verifiable by clicking through to the original

---

## Backend Architecture

### New Endpoint

**File:** `backend/app/api/query_stream.py`

```python
@router.post("/stream")
async def stream_agentic_query(
    data: AgentQueryRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
):
    return StreamingResponse(
        run_agent_stream(data.query, session, data.max_iterations),
        media_type="text/event-stream",
    )
```

### Streaming Function

**File:** `backend/app/agent/graph.py` (add function)

```python
async def run_agent_stream(query: str, session, max_iterations: int = 3):
    graph = create_agent_graph()
    initial_state = AgentState(query=query, max_iterations=max_iterations)
    config = {"configurable": {"session": session}}

    async for event in graph.astream_events(initial_state, config, version="v2"):
        if event["event"] == "on_chain_start":
            yield format_sse("thinking", build_thinking_message(event))

        if event["event"] == "on_chain_end" and event["name"] == "generate":
            # Chunk the final answer into sentences
            for sentence in chunk_sentences(event["data"]["final_answer"]):
                yield format_sse("chunk", {"content": sentence})

            # Emit sources with original URLs
            yield format_sse("sources", build_sources(event["data"]))

    yield format_sse("done", {"research_iterations": ...})
```

### Helper Functions

- `format_sse(event_type, data)` - Formats event as SSE string
- `build_thinking_message(event)` - Creates informative message per node
- `chunk_sentences(text)` - Splits answer into sentence chunks
- `build_sources(data)` - Formats sources with original URLs

---

## Frontend Integration

### Streaming Fetch

**File:** `frontend/src/pages/ChatPage.tsx`

```typescript
async function sendAgenticQuery(query: string) {
  setThinkingSteps([]);
  setStreamedAnswer("");

  const response = await fetch("/api/query/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
    body: JSON.stringify({ query, max_iterations: 3 }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const events = parseSSE(decoder.decode(value));
    for (const event of events) {
      if (event.type === "thinking") {
        setThinkingSteps(prev => [...prev, event.data]);
      } else if (event.type === "chunk") {
        setStreamedAnswer(prev => prev + event.data.content);
      } else if (event.type === "sources") {
        setSources(event.data);
      }
    }
  }
}
```

### UI Components

- **ThinkingSteps**: Collapsible section above the answer showing reasoning steps
- **SourcesList**: Sources displayed with clickable links (open in new tab)
- Errors styled as warnings (yellow/orange, not red) since flow often recovers

---

## Error Handling

### Backend

```python
async def run_agent_stream(...):
    try:
        async for event in graph.astream_events(...):
            # ... normal processing

    except TavilyAPIError as e:
        yield format_sse("error", {
            "step": "research",
            "message": "Web search failed, continuing with internal knowledge..."
        })
        # Continue with fallback flow

    except Exception as e:
        yield format_sse("error", {
            "step": "unknown",
            "message": f"An error occurred: {str(e)}"
        })
        yield format_sse("done", {"error": True})
```

### Frontend

```typescript
if (event.type === "error") {
  setThinkingSteps(prev => [...prev, {
    step: event.data.step,
    message: event.data.message,
    isError: true  // Style differently
  }]);
  // Don't abort - stream continues
}
```

### Behaviors

- Recoverable errors (Tavily fails) → inline warning, flow continues
- Fatal errors → inline error + `done` event with `error: true`

---

## Testing Strategy

### Backend Tests

**File:** `backend/tests/test_query_stream.py`

```python
async def test_stream_emits_thinking_events():
    """Verify thinking events are emitted for each node."""
    events = []
    async for chunk in run_agent_stream("test query", mock_session):
        events.append(parse_sse(chunk))

    thinking_events = [e for e in events if e["type"] == "thinking"]
    steps = [e["data"]["step"] for e in thinking_events]

    assert "retrieve" in steps
    assert "evaluate" in steps
    assert "generate" in steps

async def test_stream_chunks_answer():
    """Verify answer is chunked into sentences."""
    events = [e async for e in run_agent_stream("test query", mock_session)]
    chunks = [e for e in events if e["type"] == "chunk"]

    assert len(chunks) > 1  # Multiple chunks, not single payload

async def test_stream_sources_have_urls():
    """Verify sources include original URLs."""
    events = [e async for e in run_agent_stream("test query", mock_session)]
    sources_event = next(e for e in events if e["type"] == "sources")

    for source in sources_event["data"]["internal"]:
        assert "url" in source
        assert source["url"].startswith("http")
```

### Frontend Tests

**File:** `frontend/src/components/chat/ChatPage.test.tsx`

```typescript
describe("Streaming query", () => {
  it("renders thinking steps progressively", async () => {
    mockFetchSSE([
      { type: "thinking", data: { step: "retrieve", message: "Searching..." } },
      { type: "thinking", data: { step: "evaluate", message: "Evaluating..." } },
    ]);

    render(<ChatPage />);
    await userEvent.type(screen.getByRole("textbox"), "test query");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText("Searching...")).toBeInTheDocument();
      expect(screen.getByText("Evaluating...")).toBeInTheDocument();
    });
  });

  it("streams answer chunks into message", async () => {
    mockFetchSSE([
      { type: "chunk", data: { content: "First sentence. " } },
      { type: "chunk", data: { content: "Second sentence." } },
    ]);

    render(<ChatPage />);
    // ... trigger query

    await waitFor(() => {
      expect(screen.getByText(/First sentence.*Second sentence/)).toBeInTheDocument();
    });
  });

  it("renders sources as clickable links", async () => {
    mockFetchSSE([
      { type: "sources", data: {
        internal: [{ title: "Tech Report", url: "https://example.com/report.pdf" }],
        external: []
      }},
    ]);

    render(<ChatPage />);
    // ... trigger query

    await waitFor(() => {
      const link = screen.getByRole("link", { name: /Tech Report/i });
      expect(link).toHaveAttribute("href", "https://example.com/report.pdf");
      expect(link).toHaveAttribute("target", "_blank");
    });
  });

  it("displays errors inline without breaking flow", async () => {
    mockFetchSSE([
      { type: "thinking", data: { step: "retrieve", message: "Searching..." } },
      { type: "error", data: { step: "research", message: "Web search failed..." } },
      { type: "chunk", data: { content: "Answer based on internal knowledge." } },
    ]);

    render(<ChatPage />);
    // ... trigger query

    await waitFor(() => {
      expect(screen.getByText(/Web search failed/)).toBeInTheDocument();
      expect(screen.getByText(/Answer based on internal knowledge/)).toBeInTheDocument();
    });
  });
});
```

---

## File Changes Summary

### Files to Create

| File | Purpose |
|------|---------|
| `backend/app/api/query_stream.py` | SSE streaming endpoint |
| `backend/tests/test_query_stream.py` | Backend stream tests |
| `frontend/src/components/chat/ThinkingSteps.tsx` | Thinking steps UI component |
| `frontend/src/lib/sse.ts` | SSE parsing utility |
| `frontend/src/components/chat/ChatPage.test.tsx` | Frontend tests |

### Files to Modify

| File | Changes |
|------|---------|
| `backend/app/agent/graph.py` | Add `run_agent_stream()` function |
| `backend/app/api/__init__.py` | Register new router |
| `frontend/src/pages/ChatPage.tsx` | Integrate streaming + thinking UI |
| `frontend/src/components/chat/SourcesList.tsx` | Add clickable links |

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Streaming approach | LangGraph `astream_events()` | Native framework support, less custom code |
| Thinking detail level | Informative | Balance between minimal and verbose |
| Answer streaming | Sentence chunks | Simpler than token-by-token, acceptable for API-first use case |
| Error handling | Inline in stream | Maintains narrative flow, consistent with graceful degradation |
| Source URLs | Original source | Users can verify information from actual source |

---

## Architecture Flow

```
User types query
       |
       v
POST /api/query/stream
       |
       v
run_agent_stream() uses graph.astream_events()
       |
       v
SSE events emitted: thinking -> thinking -> ... -> chunks -> sources -> done
       |
       v
Frontend renders progressively
```
