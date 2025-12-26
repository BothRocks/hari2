# HARI Implementation TODO

This document tracks features described in the Capstone presentation.

---

## Implementation Status Summary

| Phase | Feature | Status |
|-------|---------|--------|
| 1.1 | LangGraph Integration | ✅ Complete |
| 1.2 | Retriever Node | ✅ Complete |
| 1.3 | Evaluator Node | ✅ Complete |
| 1.4 | Router Node | ✅ Complete |
| 1.5 | Researcher Node | ✅ Complete |
| 1.6 | Generator Node | ✅ Complete |
| 1.7 | Guardrails | ⚠️ Partial (max iterations only) |
| 2.1 | SSE Streaming | ✅ Complete |
| 2.2 | Frontend Streaming | ✅ Complete |
| 2.3 | Chat Response Formatting | ❌ Not started |
| 3.1 | Tavily Web Search | ✅ Complete |
| 3.2 | Telegram Bot | ❌ Not started |
| 3.3 | Slack Bot | ❌ Not started |
| 3.4 | Drive Upload (for chatbots) | ❌ Not started |
| 4.1 | Document Quality Validation | ✅ Complete |
| 4.2 | Admin Document Review Page | ✅ Complete |
| 4.x | Answer Quality Validation | ❌ Not started |
| 5.x | Taxonomy Management | ❌ Not started |
| 6.x | Observability | ❌ Not started |

**Last Updated:** 2025-12-26

---

## Phase 1: Agentic Query System (Critical Priority)

The core differentiator of HARI—the cognitive loop that evaluates knowledge sufficiency and autonomously seeks external information.

### 1.1 LangGraph Integration

**Status:** ✅ IMPLEMENTED (2025-12-26)

**Completed:**
- [x] Added `langgraph>=0.2.0` dependency to `pyproject.toml`
- [x] Created `backend/app/agent/` module structure:
  ```
  agent/
  ├── __init__.py
  ├── graph.py           # LangGraph StateGraph definition
  ├── state.py           # AgentState, EvaluationResult, SourceReference
  └── nodes/
      ├── __init__.py
      ├── retriever.py   # Search internal knowledge
      ├── evaluator.py   # Assess context sufficiency
      ├── router.py      # Decision logic
      ├── researcher.py  # External search tools
      └── generator.py   # Final response synthesis
  ```

**API Endpoint:** `POST /api/query/agent`

### 1.2 Retriever Node

**Status:** ✅ IMPLEMENTED

**Completed:**
- [x] Wraps existing `HybridSearch` as a LangGraph node
- [x] Returns retrieved documents to state for evaluation
- [x] Tracks retrieval metadata (scores, count, sources)

**File:** `backend/app/agent/nodes/retriever.py`

### 1.3 Evaluator Node

**Status:** ✅ IMPLEMENTED

**Completed:**
- [x] LLM call to assess retrieved context (Claude Sonnet with temperature=0.0)
- [x] Output schema via `EvaluationResult` Pydantic model:
  ```python
  {
      "is_sufficient": bool,
      "confidence": float,  # 0.0-1.0
      "missing_information": list[str],
      "reasoning": str
  }
  ```
- [x] Robust JSON parsing (handles raw JSON and markdown-wrapped)
- [x] Defaults to "sufficient" on parse errors to prevent infinite loops

**File:** `backend/app/agent/nodes/evaluator.py`

### 1.4 Router Node

**Status:** ✅ IMPLEMENTED

**Completed:**
- [x] Decision logic based on evaluator output
- [x] Routes:
  - `sufficient` → Generator node
  - `insufficient` → Researcher node
- [x] Respects max_iterations limit

**File:** `backend/app/agent/nodes/router.py`

### 1.5 Researcher Node

**Status:** ✅ IMPLEMENTED

**Completed:**
- [x] Integrated Tavily API for web search
- [x] `TAVILY_API_KEY` in environment config
- [x] Query refinement using `missing_information` from evaluator
- [x] Merges external results with internal context
- [ ] Optional: Google Drive search as additional tool (future)

**Files:**
- `backend/app/agent/nodes/researcher.py`
- `backend/app/services/tavily.py`

### 1.6 Generator Node

**Status:** ✅ IMPLEMENTED

**Completed:**
- [x] Full LangGraph node implementation
- [x] Accepts combined internal + external context
- [x] Source attribution (internal vs external) via `SourceReference`
- [x] Structured output with citations

**File:** `backend/app/agent/nodes/generator.py`

### 1.7 Guardrails

**Status:** ✅ PARTIALLY IMPLEMENTED

**Completed:**
- [x] Max research iterations (configurable, default: 3)
- [x] Graceful degradation when max iterations reached

**Remaining:**
- [ ] Per-query cost ceiling
- [ ] Timeout per query

---

## Phase 2: Real-Time Streaming (High Priority)

Users should see the agent's reasoning process in real-time.

### 2.1 SSE (Server-Sent Events) Endpoint

**Status:** ✅ IMPLEMENTED (2025-12-26)

**Completed:**
- [x] Created `/api/query/stream` endpoint with SSE support
- [x] Event types implemented:
  ```
  event: thinking
  data: {"step": "retrieve", "message": "Searching internal knowledge..."}

  event: thinking
  data: {"step": "evaluate", "message": "Assessing context sufficiency..."}

  event: thinking
  data: {"step": "research", "message": "Searching web via Tavily..."}

  event: chunk
  data: {"content": "partial response text..."}

  event: sources
  data: {"internal": [...], "external": [...]}

  event: done
  data: {}
  ```
- [x] `StreamingResponse` from FastAPI with proper SSE formatting
- [x] SSE utilities module (`backend/app/api/sse_utils.py`)
- [x] Streaming agent function with yield-based event generation

**Files:**
- `backend/app/api/query_stream.py` - SSE endpoint
- `backend/app/api/sse_utils.py` - SSE formatting utilities
- `backend/app/agent/streaming.py` - Streaming agent implementation

### 2.2 Frontend Streaming Support

**Status:** ✅ IMPLEMENTED (2025-12-26)

**Completed:**
- [x] SSE parser utility (`frontend/src/lib/sse.ts`)
- [x] ThinkingSteps component for real-time reasoning display
- [x] ChatMessage component with clickable source references
- [x] Streaming API function in `frontend/src/lib/api.ts`
- [x] ChatPage integration with streaming support
- [x] Incremental response rendering (typewriter effect)
- [x] Internal vs external source distinction with visual indicators

**Files:**
- `frontend/src/lib/sse.ts` - SSE event parser
- `frontend/src/components/chat/ThinkingSteps.tsx` - Thinking steps display
- `frontend/src/components/chat/ChatMessage.tsx` - Message with sources
- `frontend/src/pages/ChatPage.tsx` - Integrated streaming chat

### 2.3 Chat Response Formatting

**Status:** NOT IMPLEMENTED

**Required:**
- [ ] Markdown rendering for agent responses (headers, lists, bold, code)
- [ ] Syntax highlighting for code blocks
- [ ] Proper paragraph spacing and typography
- [ ] Citation styling (inline references to sources)

**Scope:** Frontend-only, cosmetic improvements to ChatMessage component.

**Files to modify:**
- `frontend/src/components/chat/ChatMessage.tsx`

---

## Phase 3: External Integrations (Medium Priority)

### 3.1 Tavily Web Search

**Status:** ✅ IMPLEMENTED (2025-12-26)

**Completed:**
- [x] Added `tavily-python>=0.5.0` dependency
- [x] Created `backend/app/services/tavily.py` with `TavilyService` class
- [x] Implemented search with result parsing (`TavilyResult` model)
- [x] Configured in `.env`: `TAVILY_API_KEY`
- [x] Integrated with researcher node for agentic queries

**File:** `backend/app/services/tavily.py`

### 3.2 Telegram Bot

**Status:** NOT IMPLEMENTED

**Required:**
- [ ] Add `python-telegram-bot` dependency
- [ ] Create `backend/app/integrations/telegram/` module
- [ ] Webhook handler for incoming messages
- [ ] State translation: Telegram message → LangGraph state
- [ ] Response formatting for Telegram

**Reference:** Capstone Section 4.3 - "Bot connector"

### 3.3 Slack Bot

**Status:** NOT IMPLEMENTED

**Required:**
- [ ] Add `slack-bolt` dependency
- [ ] Create `backend/app/integrations/slack/` module
- [ ] Event subscription for messages
- [ ] Slack-formatted responses with blocks

### 3.4 Drive Upload (Chatbot Prerequisite)

**Status:** NOT IMPLEMENTED

**Description:** Allow chatbots to upload user-submitted documents to a designated Google Drive folder for processing. This enables users to share documents via Telegram/Slack that get ingested into HARI's knowledge base.

**Required:**
- [ ] API endpoint to upload file to Drive folder
- [ ] Configure "upload target" folder in Drive settings
- [ ] Service account write permissions to target folder
- [ ] Auto-trigger document processing after upload
- [ ] Return confirmation with document status

**API Design:**
```
POST /api/documents/upload-to-drive
  - file: binary
  - folder_id: optional (uses default if not specified)
  -> Returns: { drive_file_id, document_id, job_id }
```

**Decision needed:** Should this be a prerequisite for chatbots, or can chatbots upload directly to HARI (existing `/api/documents/upload` endpoint)?

---

## Phase 4: Advanced Quality Control (Medium Priority)

### 4.1 Document Quality Validation

**Status:** ✅ IMPLEMENTED (2025-12-26)

**Completed:**
- [x] Two-pass validation approach:
  - Pass 1: Rule-based detection (no LLM cost)
  - Pass 2: LLM correction (only if issues found)
- [x] Rule-based issue detection:
  - `generic_title` - Title in generic list (template, untitled, document, etc.)
  - `single_word_title` - Single word title under 20 chars
  - `filename_as_title` - Title looks like a filename
  - `generic_author` - Author in generic list (admin, user, unknown, etc.)
  - `short_summary` - Summary under 50 words
  - `few_keywords` - Less than 3 keywords
  - `generic_keywords` - All keywords are generic
- [x] LLM auto-correction using document content
- [x] `needs_review` flag for admin attention
- [x] `review_reasons` list for issue tracking
- [x] `original_metadata` preserved for reference
- [x] Integrated into pipeline after synthesize, before embed

**Files:**
- `backend/app/services/pipeline/validator.py` - Validator service
- `backend/app/models/document.py` - New fields (needs_review, review_reasons, etc.)

### 4.2 Admin Document Review Page

**Status:** ✅ IMPLEMENTED (2025-12-26)

**Completed:**
- [x] Document detail page at `/admin/documents/:id`
- [x] Inline editing for title and author fields
- [x] Needs review alert with issue reasons
- [x] Original metadata display (before auto-correction)
- [x] "Mark as Reviewed" button to clear flag
- [x] "Re-process" button to trigger full pipeline re-run
- [x] All metadata display (quality score, tokens, cost, etc.)
- [x] Needs Review toggle filter on documents list

**API Endpoints:**
- `GET /api/documents/{id}` - Full document details
- `PUT /api/documents/{id}` - Update title/author
- `POST /api/documents/{id}/reprocess` - Trigger re-processing
- `POST /api/documents/{id}/review` - Clear needs_review flag

**Files:**
- `frontend/src/pages/DocumentDetailPage.tsx` - Detail page component
- `backend/app/api/documents.py` - New endpoints
- `backend/app/schemas/document.py` - DocumentUpdate, ReprocessResponse

### 4.x Answer Quality Validation (Future)

**Status:** NOT IMPLEMENTED

**Required:**
- [ ] Post-generation quality check
- [ ] Hallucination detection (claims vs source verification)
- [ ] Confidence scoring for answers
- [ ] Flag low-confidence responses

---

## Phase 5: Taxonomy Management (Lower Priority)

### 5.1 Controlled Vocabulary

**Status:** NOT IMPLEMENTED

**Required:**
- [ ] Create `Taxonomy` and `TaxonomyTerm` models
- [ ] Predefined industry categories
- [ ] Keyword normalization rules
- [ ] Validation during document ingestion

### 5.2 Taxonomy API

**Status:** NOT IMPLEMENTED

**Required:**
- [ ] `GET /api/admin/taxonomy/industries` - List taxonomy
- [ ] `POST /api/admin/taxonomy/industries` - Add term
- [ ] `PUT /api/admin/taxonomy/synonyms` - Update synonym groups
- [ ] Hierarchical taxonomy support (parent/child)

**Reference:** README "Admin: Taxonomy Management" section

---

## Phase 6: Observability (Lower Priority)

### 6.1 Prometheus Metrics

**Status:** NOT IMPLEMENTED

**Required:**
- [ ] Add `prometheus-fastapi-instrumentator` dependency
- [ ] Expose `/metrics` endpoint
- [ ] Custom metrics:
  - `hari_documents_processed_total`
  - `hari_llm_requests_total`
  - `hari_llm_cost_usd_total`
  - `hari_agent_research_loops_total`
  - `hari_search_requests_total`

### 6.2 Structured Logging

**Status:** PARTIAL (basic logging exists)

**Required:**
- [ ] Add correlation IDs to all requests
- [ ] JSON-formatted logs with standard fields
- [ ] Include cost/token metadata in LLM calls

**Reference:** README "Observability" section

---

## Implementation Order Recommendation

1. ~~**Phase 1.1-1.7** - Agentic system (this is the core value proposition)~~ ✅ DONE
2. ~~**Phase 3.1** - Tavily integration (required for researcher node)~~ ✅ DONE
3. ~~**Phase 2.1-2.2** - Streaming (critical for UX)~~ ✅ DONE
4. ~~**Phase 4.1-4.2** - Document quality validation and review~~ ✅ DONE
5. **Phase 2.3** - Chat response formatting (quick UX win) ← **NEXT**
6. **Phase 3.4** - Drive upload (prerequisite for chatbots, if needed)
7. **Phase 3.2-3.3** - Telegram/Slack bot integrations
8. **Phase 1.7** - Guardrails completion (cost ceiling, timeout)
9. **Phase 4.x-6.x** - Answer quality, taxonomy, observability

---

## Dependencies to Add

```toml
# pyproject.toml additions
langgraph = "^0.2"                          # ✅ ADDED
tavily-python = "^0.5"                       # ✅ ADDED
python-telegram-bot = "^21.0"                # NOT YET
slack-bolt = "^1.18"                         # NOT YET
prometheus-fastapi-instrumentator = "^6.1"   # NOT YET
```

---

## Environment Variables to Add

```bash
# .env additions
TAVILY_API_KEY=tvly-...          # ✅ ADDED
TELEGRAM_BOT_TOKEN=...           # NOT YET
SLACK_BOT_TOKEN=xoxb-...         # NOT YET
SLACK_SIGNING_SECRET=...         # NOT YET
```

---

## Files to Create

```
backend/app/
├── agent/                        # ✅ CREATED
│   ├── __init__.py               # ✅ CREATED
│   ├── graph.py                  # ✅ CREATED
│   ├── state.py                  # ✅ CREATED
│   └── nodes/                    # ✅ CREATED
│       ├── __init__.py           # ✅ CREATED
│       ├── retriever.py          # ✅ CREATED
│       ├── evaluator.py          # ✅ CREATED
│       ├── router.py             # ✅ CREATED
│       ├── researcher.py         # ✅ CREATED
│       └── generator.py          # ✅ CREATED
├── services/
│   ├── tavily.py                 # ✅ CREATED
│   └── pipeline/
│       └── validator.py          # ✅ CREATED (document quality validation)
├── schemas/
│   └── agent.py                  # ✅ CREATED (API request/response)
├── integrations/
│   ├── telegram/                 # NOT YET
│   │   ├── __init__.py
│   │   ├── bot.py
│   │   └── handlers.py
│   └── slack/                    # NOT YET
│       ├── __init__.py
│       ├── app.py
│       └── handlers.py
└── api/
    ├── query_stream.py           # ✅ CREATED (SSE endpoint)
    └── sse_utils.py              # ✅ CREATED (SSE utilities)

frontend/src/
└── pages/
    └── DocumentDetailPage.tsx    # ✅ CREATED (admin document review)
```

**Tests Created:**
- `backend/tests/test_agent_state.py`
- `backend/tests/test_agent_retriever.py`
- `backend/tests/test_agent_evaluator.py`
- `backend/tests/test_agent_router.py`
- `backend/tests/test_agent_researcher.py`
- `backend/tests/test_agent_generator.py`
- `backend/tests/test_agent_graph.py`
- `backend/tests/test_agent_integration.py`
- `backend/tests/test_api_agent_query.py`
- `backend/tests/test_tavily_service.py`
- `backend/tests/test_validator.py`

---

## Validation Criteria

Per Capstone Section 7, success is measured by:

> "Test comparativo con un set de 20 preguntas complejas que requieran razonamiento o información externa, midiendo la precisión y la completitud de la respuesta generada por HARI frente a un RAG estático estándar."

Create test suite with:
- [ ] 20 complex questions requiring external knowledge
- [ ] Baseline: current RAG implementation
- [ ] Target: agentic implementation with Tavily
- [ ] Metrics: precision, completeness, source attribution
