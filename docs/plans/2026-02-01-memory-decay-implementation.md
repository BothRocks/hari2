# Memory Decay Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce relevance of old documents in search results based on age, with option to disable.

**Architecture:** Apply decay multiplier to similarity scores post-query in Python. Propagate `ignore_decay` flag from frontend checkbox through API to search service.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, React, TypeScript

---

## Task 1: Add decay settings to config

**Files:**
- Modify: `backend/app/core/config.py`

**Step 1: Add decay settings to Settings class**

Add after line 52 (after `git_commit`):

```python
    # Memory decay settings
    decay_threshold_stale_months: int = 18
    decay_threshold_obsolete_months: int = 24
    decay_weight_stale: float = 0.70
    decay_weight_obsolete: float = 0.50
```

**Step 2: Verify config loads**

Run: `cd backend && uv run python -c "from app.core.config import settings; print(settings.decay_threshold_stale_months)"`

Expected: `18`

**Step 3: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat(decay): add memory decay settings to config"
```

---

## Task 2: Implement decay function in semantic search

**Files:**
- Modify: `backend/app/services/search/semantic.py`

**Step 1: Add decay helper function**

Add after the imports (line 5):

```python
from datetime import datetime, timezone
from app.core.config import settings


def apply_decay(
    raw_similarity: float,
    created_at: datetime,
    ignore_decay: bool = False,
) -> float:
    """Apply time-based decay to similarity score.

    Args:
        raw_similarity: Original similarity score (0-1)
        created_at: Document creation timestamp
        ignore_decay: If True, return raw score unchanged

    Returns:
        Decayed similarity score
    """
    if ignore_decay:
        return raw_similarity

    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_months = (now - created_at).days / 30.0

    if age_months <= settings.decay_threshold_stale_months:
        weight = 1.0
    elif age_months <= settings.decay_threshold_obsolete_months:
        weight = settings.decay_weight_stale
    else:
        weight = settings.decay_weight_obsolete

    return raw_similarity * weight
```

**Step 2: Update SQL query to include created_at**

Replace the SQL query (lines 33-47) with:

```python
        sql = text("""
            SELECT
                id,
                title,
                quick_summary,
                keywords,
                url,
                created_at,
                1 - (embedding <=> cast(:embedding as vector)) as raw_similarity
            FROM documents
            WHERE processing_status = 'COMPLETED'::processingstatus
                AND embedding IS NOT NULL
            ORDER BY embedding <=> cast(:embedding as vector)
            LIMIT :limit
        """)
```

**Step 3: Update search method signature and apply decay**

Replace the `search` method (lines 11-69) with:

```python
    async def search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.5,
        ignore_decay: bool = False,
        session: AsyncSession | None = None,
    ) -> list[dict]:
        """Search documents by semantic similarity with time decay."""
        db = session or self.session
        if not db:
            raise ValueError("Database session required")

        query_embedding = await generate_embedding(query)
        if not query_embedding:
            return []

        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        sql = text("""
            SELECT
                id,
                title,
                quick_summary,
                keywords,
                url,
                created_at,
                1 - (embedding <=> cast(:embedding as vector)) as raw_similarity
            FROM documents
            WHERE processing_status = 'COMPLETED'::processingstatus
                AND embedding IS NOT NULL
            ORDER BY embedding <=> cast(:embedding as vector)
            LIMIT :limit
        """)

        result = await db.execute(
            sql,
            {
                "embedding": embedding_str,
                "limit": limit * 2,  # Fetch more to allow filtering after decay
            }
        )

        rows = result.fetchall()

        # Apply decay, filter by threshold, and sort
        results = []
        for row in rows:
            decayed_similarity = apply_decay(
                row.raw_similarity,
                row.created_at,
                ignore_decay,
            )
            if decayed_similarity >= threshold:
                results.append({
                    "id": str(row.id),
                    "title": row.title,
                    "quick_summary": row.quick_summary,
                    "keywords": row.keywords,
                    "url": row.url,
                    "similarity": float(decayed_similarity),
                })

        # Sort by decayed similarity and limit
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]
```

**Step 4: Verify syntax**

Run: `cd backend && uv run python -c "from app.services.search.semantic import SemanticSearch, apply_decay; print('OK')"`

Expected: `OK`

**Step 5: Commit**

```bash
git add backend/app/services/search/semantic.py
git commit -m "feat(decay): implement time-based decay in semantic search"
```

---

## Task 3: Propagate ignore_decay through hybrid search

**Files:**
- Modify: `backend/app/services/search/hybrid.py`

**Step 1: Add ignore_decay parameter to HybridSearch.search**

Replace the `search` method (lines 38-59) with:

```python
    async def search(
        self,
        query: str,
        limit: int = 10,
        semantic_weight: float = 0.7,
        ignore_decay: bool = False,
        session: AsyncSession | None = None,
    ) -> list[dict]:
        """Hybrid search combining semantic and keyword search."""
        db = session or self.session

        # Run both searches
        semantic_results = await self.semantic.search(
            query, limit=limit * 2, ignore_decay=ignore_decay, session=db
        )
        keyword_results = await self.keyword.search(
            query, limit=limit * 2, session=db
        )

        # Combine with RRF
        combined = reciprocal_rank_fusion(semantic_results, keyword_results)

        return combined[:limit]
```

**Step 2: Verify syntax**

Run: `cd backend && uv run python -c "from app.services.search.hybrid import HybridSearch; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/services/search/hybrid.py
git commit -m "feat(decay): propagate ignore_decay through hybrid search"
```

---

## Task 4: Add ignore_decay to AgentState

**Files:**
- Modify: `backend/app/agent/state.py`

**Step 1: Add ignore_decay field to AgentState**

Add after line 28 (after `query: str`):

```python
    # Search options
    ignore_decay: bool = False
```

**Step 2: Verify syntax**

Run: `cd backend && uv run python -c "from app.agent.state import AgentState; s = AgentState(query='test', ignore_decay=True); print(s.ignore_decay)"`

Expected: `True`

**Step 3: Commit**

```bash
git add backend/app/agent/state.py
git commit -m "feat(decay): add ignore_decay to AgentState"
```

---

## Task 5: Pass ignore_decay from retriever to search

**Files:**
- Modify: `backend/app/agent/nodes/retriever.py`

**Step 1: Pass ignore_decay to HybridSearch**

Replace the `retriever_node` function (lines 10-34) with:

```python
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
        ignore_decay=state.ignore_decay,
        session=session,
    )

    return {"internal_results": results}
```

**Step 2: Verify syntax**

Run: `cd backend && uv run python -c "from app.agent.nodes.retriever import retriever_node; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/agent/nodes/retriever.py
git commit -m "feat(decay): pass ignore_decay from state to search"
```

---

## Task 6: Add ignore_decay to API schemas

**Files:**
- Modify: `backend/app/schemas/agent.py`
- Modify: `backend/app/schemas/query.py`

**Step 1: Add ignore_decay to AgentQueryRequest**

In `backend/app/schemas/agent.py`, add after line 22 (after `timeout_seconds`):

```python
    ignore_decay: bool = Field(
        default=False,
        description="If true, include old documents without age penalty"
    )
```

**Step 2: Add ignore_decay to QueryRequest**

In `backend/app/schemas/query.py`, add after line 6 (after `limit: int = 5`):

```python
    ignore_decay: bool = False
```

**Step 3: Add ignore_decay to SearchRequest**

In `backend/app/schemas/query.py`, add after line 23 (after `threshold: float = 0.5`):

```python
    ignore_decay: bool = False
```

**Step 4: Verify syntax**

Run: `cd backend && uv run python -c "from app.schemas.agent import AgentQueryRequest; from app.schemas.query import QueryRequest, SearchRequest; print('OK')"`

Expected: `OK`

**Step 5: Commit**

```bash
git add backend/app/schemas/agent.py backend/app/schemas/query.py
git commit -m "feat(decay): add ignore_decay to API request schemas"
```

---

## Task 7: Wire ignore_decay in query API endpoints

**Files:**
- Modify: `backend/app/api/query.py`

**Step 1: Update query_knowledge_base endpoint**

Replace lines 25-30 with:

```python
    search = HybridSearch(session)
    results = await search.search(
        query=data.query,
        limit=data.limit,
        ignore_decay=data.ignore_decay,
        session=session,
    )
```

**Step 2: Update agentic_query endpoint**

Replace lines 60-65 with:

```python
    result = await run_agent(
        query=data.query,
        session=session,
        max_iterations=data.max_iterations,
        timeout_seconds=data.timeout_seconds,
        ignore_decay=data.ignore_decay,
    )
```

**Step 3: Update stream_agentic_query endpoint**

Replace lines 110-117 with:

```python
    return StreamingResponse(
        run_agent_stream(
            query=data.query,
            session=session,
            max_iterations=data.max_iterations,
            timeout_seconds=data.timeout_seconds,
            ignore_decay=data.ignore_decay,
        ),
        media_type="text/event-stream",
    )
```

**Step 4: Verify syntax**

Run: `cd backend && uv run python -c "from app.api.query import router; print('OK')"`

Expected: `OK`

**Step 5: Commit**

```bash
git add backend/app/api/query.py
git commit -m "feat(decay): wire ignore_decay in query endpoints"
```

---

## Task 8: Wire ignore_decay in search API endpoint

**Files:**
- Modify: `backend/app/api/search.py`

**Step 1: Pass ignore_decay to HybridSearch**

Replace lines 20-25 with:

```python
    search = HybridSearch(session)
    results = await search.search(
        query=data.query,
        limit=data.limit,
        ignore_decay=data.ignore_decay,
        session=session,
    )
```

**Step 2: Verify syntax**

Run: `cd backend && uv run python -c "from app.api.search import router; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/api/search.py
git commit -m "feat(decay): wire ignore_decay in search endpoint"
```

---

## Task 9: Add ignore_decay to agent graph functions

**Files:**
- Modify: `backend/app/agent/graph.py`

**Step 1: Add ignore_decay parameter to run_agent**

Replace the function signature and initial_state creation (lines 91-122) with:

```python
async def run_agent(
    query: str,
    session: AsyncSession | None = None,
    max_iterations: int = 3,
    timeout_seconds: int = 120,
    cost_ceiling_usd: float = 1.0,
    ignore_decay: bool = False,
) -> AgentState:
    """
    Run the agentic RAG pipeline.

    Args:
        query: User's question
        session: Database session for retrieval
        max_iterations: Maximum research iterations
        timeout_seconds: Maximum time before timeout (default: 120s, max: 300s)
        cost_ceiling_usd: Maximum cost in USD (default: $1.00)
        ignore_decay: If True, don't penalize old documents

    Returns:
        Final agent state with answer and sources
    """
    graph = create_agent_graph()

    # Clamp timeout to allowed range
    timeout_seconds = min(max(timeout_seconds, 30), 300)

    initial_state = AgentState(
        query=query,
        max_iterations=max_iterations,
        start_time=time.time(),
        timeout_seconds=timeout_seconds,
        cost_ceiling_usd=cost_ceiling_usd,
        ignore_decay=ignore_decay,
    )
```

**Step 2: Add ignore_decay parameter to run_agent_stream**

Replace the function signature and initial_state creation (lines 136-167) with:

```python
async def run_agent_stream(
    query: str,
    session: AsyncSession | None = None,
    max_iterations: int = 3,
    timeout_seconds: int = 120,
    cost_ceiling_usd: float = 1.0,
    ignore_decay: bool = False,
) -> AsyncIterator[str]:
    """
    Run the agentic RAG pipeline with streaming events.

    Args:
        query: User's question
        session: Database session for retrieval
        max_iterations: Maximum research iterations
        timeout_seconds: Maximum time before timeout (default: 120s, max: 300s)
        cost_ceiling_usd: Maximum cost in USD (default: $1.00)
        ignore_decay: If True, don't penalize old documents

    Yields:
        SSE-formatted event strings
    """
    graph = create_agent_graph()

    # Clamp timeout to allowed range
    timeout_seconds = min(max(timeout_seconds, 30), 300)

    initial_state = AgentState(
        query=query,
        max_iterations=max_iterations,
        start_time=time.time(),
        timeout_seconds=timeout_seconds,
        cost_ceiling_usd=cost_ceiling_usd,
        ignore_decay=ignore_decay,
    )
```

**Step 3: Verify syntax**

Run: `cd backend && uv run python -c "from app.agent.graph import run_agent, run_agent_stream; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
git add backend/app/agent/graph.py
git commit -m "feat(decay): add ignore_decay to agent graph functions"
```

---

## Task 10: Add checkbox to frontend ChatInput

**Files:**
- Modify: `frontend/src/components/chat/ChatInput.tsx`

**Step 1: Add ignore_decay state and checkbox**

Replace the entire file with:

```tsx
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface ChatInputProps {
  onSubmit: (message: string, ignoreDecay: boolean) => void;
  isLoading: boolean;
}

export function ChatInput({ onSubmit, isLoading }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [ignoreDecay, setIgnoreDecay] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSubmit(message, ignoreDecay);
      setMessage('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <div className="flex gap-2">
        <Textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Ask a question..."
          className="flex-1 min-h-[60px] resize-none"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
        />
        <Button type="submit" disabled={isLoading || !message.trim()}>
          {isLoading ? 'Thinking...' : 'Ask'}
        </Button>
      </div>
      <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
        <input
          type="checkbox"
          checked={ignoreDecay}
          onChange={(e) => setIgnoreDecay(e.target.checked)}
          className="rounded border-gray-300"
        />
        Include old documents
      </label>
    </form>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/chat/ChatInput.tsx
git commit -m "feat(decay): add ignore decay checkbox to ChatInput"
```

---

## Task 11: Update ChatPage to pass ignoreDecay

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`

**Step 1: Update handleSubmit to accept ignoreDecay**

Replace the `handleSubmit` function (lines 74-94) with:

```tsx
  const handleSubmit = async (message: string, ignoreDecay: boolean = false) => {
    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: message }]);
    setIsLoading(true);

    // Reset streaming state
    currentContentRef.current = '';
    currentThinkingRef.current = [];
    setCurrentThinking([]);
    setCurrentContent('');

    try {
      await queryApi.streamAsk(message, handleEvent, 3, ignoreDecay);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}` },
      ]);
      setIsLoading(false);
    }
  };
```

**Step 2: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx
git commit -m "feat(decay): pass ignoreDecay from ChatPage to API"
```

---

## Task 12: Update API client to send ignore_decay

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Step 1: Update streamAsk to include ignoreDecay**

Replace the `streamAsk` function (lines 32-71) with:

```typescript
  streamAsk: async (
    query: string,
    onEvent: (event: SSEEvent) => void,
    maxIterations = 3,
    ignoreDecay = false
  ): Promise<void> => {
    const apiKey = localStorage.getItem('api_key');

    const response = await fetch(`${API_BASE}/api/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      },
      credentials: 'include',
      body: JSON.stringify({
        query,
        max_iterations: maxIterations,
        ignore_decay: ignoreDecay,
      }),
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
```

**Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(decay): send ignore_decay in API client"
```

---

## Task 13: Final verification

**Step 1: Verify backend starts**

Run: `cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &`

Wait 3 seconds, then check: `curl -s http://localhost:8000/health | head -1`

Expected: `{"status":"healthy"...`

**Step 2: Stop backend**

Run: `pkill -f "uvicorn app.main:app"`

**Step 3: Verify frontend builds**

Run: `cd frontend && npm run build 2>&1 | tail -5`

Expected: Build succeeds without errors

**Step 4: Create final commit if any unstaged changes**

```bash
git status
# If clean, skip. Otherwise:
git add -A && git commit -m "chore: cleanup"
```
