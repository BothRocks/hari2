# HARI - Human-Augmented Resource Intelligence

> **A "second digital brain" and agentic assistant that transforms unstructured information overload into actionable knowledge.**

---

## The Problem

Modern professionals face **massive data fragmentation** and **corporate amnesia**:

- Valuable information shared in informal channels (Telegram, Slack, Teams) gets lost
- Documents buried in Google Drive become expensive to retrieve
- Insights from conversations fade from memory ("What was that link about...?")
- Knowledge stays siloed—unavailable to the rest of the organization

Traditional RAG (Retrieval-Augmented Generation) systems fail when the answer isn't in the database—generating hallucinations or empty responses. They're passive retrieval systems, not intelligent assistants.

---

## The Solution

HARI is an **Agentic RAG system** built on a graph-based cognitive architecture. Unlike static pipelines, HARI implements a **cognitive cycle** capable of:

1. **Evaluating its own knowledge** - Determining if retrieved context is sufficient
2. **Autonomous decision-making** - Choosing to search externally when needed
3. **Active information seeking** - Using web search, Drive APIs, and other tools
4. **Self-aware limitations** - Knowing what it doesn't know

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AGENTIC RAG COGNITIVE LOOP                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   User Query ──► Orchestrator (State)                              │
│                       │                                             │
│                       ▼                                             │
│               ┌───────────────┐                                     │
│               │   Retriever   │◄────► PostgreSQL + pgvector        │
│               └───────┬───────┘       (Internal Knowledge)         │
│                       │                                             │
│                       ▼                                             │
│               ┌───────────────┐                                     │
│               │   Evaluator   │  "Is this context sufficient?"     │
│               └───────┬───────┘                                     │
│                       │                                             │
│              ┌────────┴────────┐                                    │
│              ▼                 ▼                                    │
│         Sufficient        Insufficient                              │
│              │                 │                                    │
│              │                 ▼                                    │
│              │         ┌─────────────┐                              │
│              │         │   Router    │                              │
│              │         └──────┬──────┘                              │
│              │                │                                     │
│              │                ▼                                     │
│              │         ┌─────────────┐                              │
│              │         │ Researcher  │◄────► Tavily (Web Search)   │
│              │         │             │◄────► Google Drive API      │
│              │         └──────┬──────┘                              │
│              │                │                                     │
│              └────────┬───────┘                                     │
│                       ▼                                             │
│               ┌───────────────┐                                     │
│               │   Generator   │◄────► LLM (Claude/GPT-4)           │
│               └───────┬───────┘                                     │
│                       │                                             │
│                       ▼                                             │
│               Final Response (with citations)                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Differentiators:**
- **Self-aware autonomy**: HARI knows what it doesn't know and actively seeks answers
- **95% cost reduction**: Local preprocessing before LLM synthesis
- **Modular graph architecture**: New capabilities added as nodes without rewrites
- **Guardrails**: Prevents infinite search loops with configurable limits

---

## Quick Start

### Prerequisites

- PostgreSQL 17 with pgvector extension
- Python 3.11+ with [uv](https://github.com/astral-sh/uv)
- Node.js 18+
- API keys: Anthropic or OpenAI (for LLM), OpenAI (for embeddings)

### Setup

```bash
# 1. Create database
createdb hari2
psql hari2 -c "CREATE EXTENSION vector;"

# 2. Configure backend
cd backend
cp .env.example .env  # Edit with your API keys
uv sync
uv run alembic upgrade head

# 3. Configure frontend
cd ../frontend
npm install

# 4. Run
# Terminal 1:
cd backend && uv run uvicorn app.main:app --reload

# Terminal 2:
cd frontend && npm run dev
```

### First Steps

1. Open http://localhost:5173
2. Set API key in browser console: `localStorage.setItem('api_key', 'gorgonzola')`
3. Upload a document: `./scripts/upload.sh https://example.com/article`
4. Start chatting!

### Agentic Query (NEW)

The agentic query endpoint evaluates internal knowledge sufficiency and automatically searches the web when needed:

```bash
curl -X POST http://localhost:8000/api/query/agent \
  -H "Content-Type: application/json" \
  -H "X-API-Key: gorgonzola" \
  -d '{"query": "What are the latest trends in AI?", "max_iterations": 3}'
```

Response includes:
- `answer`: Synthesized response from internal + external sources
- `sources`: Array of source references with `source_type` ("internal" or "external")
- `research_iterations`: Number of external research loops performed (0 = internal only)

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Document Ingestion | ✅ Complete | URL, PDF, Google Drive |
| Hybrid Search | ✅ Complete | Keyword + Semantic with RRF |
| LangGraph Agent | ✅ Complete | Cognitive loop with 5 nodes |
| Tavily Web Search | ✅ Complete | Integrated with researcher node |
| Agentic Query API | ✅ Complete | `POST /api/query/agent` |
| SSE Streaming | ❌ Not started | Real-time reasoning visibility |
| Telegram/Slack Bots | ❌ Not started | Messaging platform connectors |

See [TODO.md](TODO.md) for detailed implementation tracking.

---

## Table of Contents

- [Implementation Status](#implementation-status)
- [Architecture](#architecture)
- [Core Components](#core-components)
- [Document Ingestion Pipeline](#document-ingestion-pipeline)
- [Agentic Query System](#agentic-query-system)
- [Supported Content Types](#supported-content-types)
- [Search & Retrieval](#search--retrieval)
- [API Design](#api-design)
- [Technology Stack](#technology-stack)
- [Cost Optimization](#cost-optimization)
- [Quality Control](#quality-control)
- [Observability](#observability)
- [Messaging Platform Integration](#messaging-platform-integration)
- [Deployment](#deployment)
- [Delivery Priorities](#delivery-priorities)

---

## Architecture

### System Overview

HARI follows an **API-First headless architecture**, decoupling the agentic backend from any specific frontend:

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLIENTS                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐             │
│   │  Admin      │   │  Chat UI    │   │  Telegram/  │             │
│   │  Dashboard  │   │  (Web)      │   │  Slack Bot  │             │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘             │
│          │                 │                 │                      │
│          │      REST API   │    Webhooks     │                      │
│          └─────────────────┼─────────────────┘                      │
│                            ▼                                        │
├─────────────────────────────────────────────────────────────────────┤
│                      HARI BACKEND                                    │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                  FastAPI Gateway                             │  │
│   │  • Authentication (OAuth, API Keys)                         │  │
│   │  • Rate Limiting                                            │  │
│   │  • Request Validation                                       │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                            │                                        │
│          ┌─────────────────┼─────────────────┐                     │
│          ▼                 ▼                 ▼                      │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐             │
│   │  Ingestion  │   │  Agentic    │   │   Admin     │             │
│   │  Pipeline   │   │  Query      │   │   Services  │             │
│   │             │   │  (LangGraph)│   │             │             │
│   └─────────────┘   └─────────────┘   └─────────────┘             │
│          │                 │                 │                      │
│          └─────────────────┼─────────────────┘                      │
│                            ▼                                        │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                    Data Layer                                │  │
│   │  PostgreSQL + pgvector  │  LLM APIs  │  External Tools      │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Same conversation started on web, continued on Telegram (shared context in DB)
- Independent scaling of ingestion vs query workloads
- Native webhook support for messaging platforms
- Easy integration with external systems

---

## Core Components

### 1. Ingestion Pipeline (Memory Formation)

Processes documents into the knowledge base with cost optimization:

```
URL/PDF/Drive ──► Fetch ──► Clean ──► Extract ──► Synthesize ──► Embed ──► Store
                   │         │          │            │            │          │
                   │         │          │            │            │          │
                 $0.00     $0.00      $0.00       ~$0.003      ~$0.00002   $0.00
                (local)   (local)   (local)      (LLM)      (embeddings)
```

**Total cost per document: ~$0.003-0.005** (vs $0.05-0.10 for naive approaches)

### 2. Agentic Query System (Cognitive Loop)

Powered by **LangGraph** for stateful, graph-based reasoning:

| Node | Purpose | Tools |
|------|---------|-------|
| **Orchestrator** | Manages conversation state | - |
| **Retriever** | Searches internal knowledge | pgvector |
| **Evaluator** | Assesses context sufficiency | Lightweight LLM |
| **Router** | Decides next action | Decision logic |
| **Researcher** | Gathers external information | Tavily, Deep Research, Drive API |
| **Generator** | Produces final response | Claude/GPT-4 |

### 3. Admin Services

- User management (roles, API keys)
- Drive folder registration and sync
- Batch job orchestration
- Quality monitoring and remediation
- Cost tracking and reporting
- **Taxonomy management**: Configurable industry classifications, keyword normalization rules

---

## Document Ingestion Pipeline

### 7-Stage Processing

```
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 1: Content Acquisition                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│  │  Web URL    │    │  PDF File   │    │ Google Drive│                 │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                 │
│         └──────────────────┼──────────────────┘                         │
│                            ▼                                            │
│  • Trafilatura (primary) - local, ML-based extraction                  │
│  • Jina AI (fallback) - handles JavaScript-heavy sites                 │
│  • Circuit breaker pattern for resilience                              │
│  • Cost: $0 (local) or ~$0.001 (Jina fallback)                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 2: Text Cleaning & Analysis                                      │
│  • Remove boilerplate, ads, navigation                                  │
│  • Language detection                                                   │
│  • Structure extraction (sections, headings)                           │
│  • Token counting for cost planning                                     │
│  • Cost: $0 (local processing)                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 3: Extractive Summarization                                      │
│  • Algorithm: TextRank (graph-based sentence ranking)                  │
│  • Library: Sumy (with LexRank fallback)                               │
│  • Reduction: 50-70% of original tokens                                │
│  • Multi-language: EN, ES, FR, DE, IT, PT, RU, ZH, JA                 │
│  • Cost: $0 (local processing)                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 4: LLM Synthesis (Abstractive)                                   │
│  • Primary: Claude Sonnet (~$3/1M input tokens)                        │
│  • Fallback: GPT-4 Turbo (automatic on Claude failure)                 │
│  • Output: Structured JSON                                              │
│    - summary (extended)                                                │
│    - quick_summary (2-3 sentences)                                     │
│    - keywords (5-10 terms)                                             │
│    - industries (classification)                                       │
│  • Quality validation with auto-retry                                  │
│  • Cost: ~$0.003-0.005 per document                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 5: Metadata Extraction                                           │
│  • Title: From HTML meta tags, PDF metadata, or LLM inference          │
│  • Author: From source metadata                                        │
│  • Language: Detected from content                                     │
│  • Industries: LLM-classified taxonomy                                 │
│  • Cost: Included in Stage 4                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 6: Vector Embeddings                                             │
│  • Model: OpenAI text-embedding-3-small (1536 dimensions)              │
│  • Alternative: text-embedding-3-large (3072 dims) for higher quality  │
│  • Batch processing support                                            │
│  • Cost: ~$0.02/1M tokens (~$0.00002 per document)                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 7: Storage & Caching                                             │
│  • PostgreSQL: Documents, summaries, metadata, usage tracking          │
│  • pgvector: Semantic embeddings for similarity search                 │
│  • Cache: Content-hash based deduplication, configurable TTL           │
│  • Metrics: Processing time, token counts, costs per stage             │
│  • Cost: $0 (infrastructure only)                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Cost Comparison

| Approach | Cost per Document | Processing Time |
|----------|-------------------|-----------------|
| Naive GPT-4 (full text) | $0.05-0.10 | 30-60s |
| HARI Pipeline | $0.003-0.005 | 5-10s |
| **Savings** | **95%** | **70%** |

---

## Agentic Query System

### LangGraph Cognitive Loop

Unlike traditional RAG that blindly retrieves and generates, HARI's agentic system makes intelligent decisions:

```python
# Simplified LangGraph structure
from langgraph.graph import StateGraph

graph = StateGraph(ConversationState)

# Define nodes
graph.add_node("retrieve", retriever_node)      # Search internal knowledge
graph.add_node("evaluate", evaluator_node)      # Assess sufficiency
graph.add_node("route", router_node)            # Decide next action
graph.add_node("research", researcher_node)     # External search
graph.add_node("generate", generator_node)      # Final response

# Define edges (decision logic)
graph.add_edge("retrieve", "evaluate")
graph.add_conditional_edges(
    "evaluate",
    should_research,  # Decision function
    {
        "sufficient": "generate",
        "insufficient": "route"
    }
)
graph.add_edge("route", "research")
graph.add_edge("research", "generate")
```

### Decision Logic

The **Evaluator Node** uses a lightweight LLM to assess retrieved context:

```
Input: User query + Retrieved documents
Output: {
  "is_sufficient": boolean,
  "confidence": 0.0-1.0,
  "missing_information": ["specific gaps identified"],
  "reasoning": "explanation"
}
```

### Guardrails

To prevent infinite loops and runaway costs:

- **Max research iterations**: 3 attempts before graceful degradation
- **Cost ceiling**: Per-query budget limit
- **Timeout**: Maximum processing time per query
- **Fallback response**: Acknowledges limitations if all attempts fail

### Reasoning Transparency (SSE/WebSockets)

Users see the agent's cognitive process in real-time via **Server-Sent Events (SSE)** or **WebSockets**:

```
User: "What are the latest tourism trends in Spain?"

[Searching internal knowledge...]
[Found 3 relevant documents, evaluating...]
[Context insufficient for 2024 trends, searching web...]
[Found 2 recent articles via Tavily...]
[Generating response...]

Based on your knowledge base and recent research, here are the key
tourism trends in Spain for 2024...
```

---

## Supported Content Types

### Input Sources

| Source | Method | Features |
|--------|--------|----------|
| **Web URLs** | Trafilatura + Jina AI | JS rendering, paywall handling |
| **PDF URLs** | Auto-detection (`%PDF` signature) | Direct download + extraction |
| **PDF Uploads** | Multipart form upload | Size limits, validation |
| **Google Drive** | Service Account API | Batch sync, change detection |

### Content Processing

| Content Type | Extraction | Metadata |
|--------------|------------|----------|
| **HTML** | Trafilatura ML extraction | Title, author, publish date |
| **PDF** | PyPDF2 text extraction | Title, author, page count |
| **Drive PDF** | Same as PDF | + Drive metadata (modified, owner) |

### Google Drive Integration

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DRIVE BATCH PROCESSING                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Register Folder                                                 │
│     POST /api/admin/drive-folders                                   │
│     {"folder_id": "1ABC...", "name": "Research Papers"}            │
│                                                                     │
│  2. Sync (Discover Files)                                          │
│     POST /api/admin/drive-folders/{uuid}/sync                      │
│     → Finds new/modified PDFs via MD5 checksums                    │
│                                                                     │
│  3. Process Batch                                                   │
│     POST /api/admin/drive-folders/start-batch                      │
│     → Background job with progress tracking                        │
│     → Concurrent processing (configurable parallelism)             │
│                                                                     │
│  4. Monitor & Handle Failures                                       │
│     GET /api/admin/batch-jobs/{job_id}                             │
│     GET /api/admin/drive-files/failed                              │
│     POST /api/admin/drive-files/{uuid}/retry                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Search & Retrieval

### Hybrid Search

HARI implements **hybrid search** combining keyword and semantic approaches:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HYBRID SEARCH                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   User Query                                                        │
│       │                                                             │
│       ├────────────────────┬────────────────────┐                  │
│       ▼                    ▼                    ▼                   │
│   ┌────────┐          ┌────────┐          ┌────────┐              │
│   │Keyword │          │Semantic│          │Filters │              │
│   │TSVector│          │pgvector│          │        │              │
│   └───┬────┘          └───┬────┘          └───┬────┘              │
│       │                   │                   │                    │
│       │   BM25 ranking    │  Cosine similarity│  Industry, source │
│       │                   │                   │  type, date range │
│       │                   │                   │                    │
│       └───────────────────┼───────────────────┘                    │
│                           ▼                                         │
│                   Score Fusion (RRF)                                │
│                           │                                         │
│                           ▼                                         │
│                   Ranked Results                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

| Method | Technology | Strengths |
|--------|------------|-----------|
| **Keyword** | PostgreSQL TSVector | Exact matches, rare terms, acronyms |
| **Semantic** | pgvector (cosine) | Meaning, synonyms, concepts |
| **Fusion** | Reciprocal Rank Fusion | Best of both approaches |

```python
# Hybrid search with filters
results = await search(
    query="luxury travel trends in Mediterranean",
    limit=10,
    threshold=0.5,
    filters={
        "industries": ["Travel & Tourism"],
        "source_type": "url",
        "date_range": ("2024-01-01", None)
    }
)
```

### Keyword Refinement

Automatic query expansion with domain-specific synonyms:

| Original Query | Expanded Query |
|----------------|----------------|
| `tourist trends` | `(tourist | tourism | travel) & (trend | trends)` |
| `luxury retail` | `(luxury | premium | high-end) & (retail | shopping)` |
| `fintech innovation` | `(fintech | financial technology) & (innovation)` |

**Built-in Synonym Groups:**
- Travel & Tourism: tourist, tourism, travel, vacation, holiday
- Technology: tech, technology, digital, software, IT
- Business: business, corporate, enterprise, company
- Finance: finance, financial, banking, investment
- Luxury: luxury, premium, high-end, upscale

### Context-Aware Search

Inject customer/domain context for better relevance:

```python
results = await search(
    query="market trends",
    context={
        "customer_profile": "Travel agency in Barcelona",
        "domain": "Mediterranean tourism",
        "time_frame": "2024-2025"
    }
)
```

### Similar Document Discovery

Find semantically related documents:

```python
similar = await find_similar(document_id, limit=10)
```

---

## API Design

### Authentication Tiers

| Method | Use Case | Capabilities |
|--------|----------|--------------|
| **Google OAuth** | Interactive users | Full access based on role |
| **User API Key** | Programmatic access | Search, view, process |
| **Admin API Key** | System administration | All operations |

### Access Levels

| Level | Authentication | Operations |
|-------|----------------|------------|
| **Public** | None | Health check |
| **User** | OAuth or User API Key | Search, view documents, submit URLs |
| **Admin** | Admin API Key or admin role | + Drive management, batch jobs, users, quality |

### Core Endpoints

#### Document Processing

```http
POST /summarize
Content-Type: application/json
X-API-Key: <key>

{"url": "https://example.com/article"}
```

```http
POST /summarize_pdf
Content-Type: multipart/form-data
X-API-Key: <key>

file: <pdf_binary>
```

#### Agentic Query

```http
POST /api/query
Content-Type: application/json
X-API-Key: <key>

{
  "query": "What are the latest tourism trends?",
  "stream": true,
  "include_thinking": true
}
```

Response (streamed):
```
event: thinking
data: {"step": "retrieve", "message": "Searching internal knowledge..."}

event: thinking
data: {"step": "evaluate", "message": "Found 3 documents, assessing..."}

event: thinking
data: {"step": "research", "message": "Searching web for recent data..."}

event: response
data: {"content": "Based on your knowledge base and recent research..."}

event: sources
data: {"internal": [...], "external": [...]}
```

#### Search

```http
GET /api/search?q=tourism+trends&limit=10
X-API-Key: <key>
```

```http
POST /api/search
Content-Type: application/json
X-API-Key: <key>

{
  "query": "luxury travel Mediterranean",
  "limit": 10,
  "threshold": 0.5,
  "context": {"domain": "Spanish market"}
}
```

#### Admin: Drive Management

```http
POST /api/admin/drive-folders
{"folder_id": "1ABC...", "name": "Research"}

POST /api/admin/drive-folders/{uuid}/sync

POST /api/admin/drive-folders/start-batch
{"folder_uuids": ["uuid1", "uuid2"], "concurrency": 3}

GET /api/admin/batch-jobs/{job_id}
```

#### Admin: Quality Control

```http
GET /api/admin/quality/report

POST /api/admin/quality/remediate-bulk
{"strategy": "METADATA_ENHANCEMENT", "max_items": 50}
```

#### Admin: Taxonomy Management

```http
# List industry taxonomy
GET /api/admin/taxonomy/industries

# Add custom industry
POST /api/admin/taxonomy/industries
{"name": "Sustainable Tourism", "parent": "Travel & Tourism"}

# Update keyword normalization rules
PUT /api/admin/taxonomy/synonyms
{"group": "luxury", "terms": ["luxury", "premium", "high-end", "upscale", "exclusive"]}
```

#### Health

```http
GET /health

Response:
{
  "status": "healthy",
  "version": "1.0.0",
  "commit": "abc1234",
  "environment": "production"
}
```

---

## Technology Stack

### Core

| Component | Technology | Purpose |
|-----------|------------|---------|
| **API Framework** | FastAPI | Async REST + WebSocket |
| **Agent Orchestration** | LangGraph | Stateful graph-based reasoning |
| **Database** | PostgreSQL 15+ | Primary data store |
| **Vector Search** | pgvector | Semantic similarity |
| **ORM** | SQLAlchemy (async) | Database abstraction |
| **Migrations** | Alembic | Schema versioning |

### AI/ML

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Primary LLM** | Claude Sonnet | Synthesis + evaluation |
| **Fallback LLM** | GPT-4 Turbo | Reliability |
| **Embeddings** | OpenAI text-embedding-3-small | Vector generation |
| **Extractive Summary** | Sumy (TextRank) | Token reduction |
| **Content Extraction** | Trafilatura | Web scraping |
| **JS Fallback** | Jina AI | JavaScript rendering |

### External Tools

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Web Search** | Tavily API | Agentic research |
| **Document Storage** | Google Drive API | Batch ingestion |
| **Auth Provider** | Google OAuth 2.0 | User authentication |

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Language Detection** | langdetect | Multi-language support |
| **PDF Processing** | PyPDF2 | Text extraction |
| **Background Jobs** | asyncio + Redis (optional) | Batch processing, job queue |
| **Caching** | PostgreSQL or Redis | TTL + size-based eviction |

---

## Cost Optimization

### Per-Stage Cost Tracking

Every processing stage logs:
- Input/output token counts
- Latency (milliseconds)
- Cost in USD
- Provider and model used

```json
{
  "document_id": "uuid",
  "stages": {
    "fetch": {"latency_ms": 450, "cost_usd": 0},
    "extract": {"latency_ms": 120, "cost_usd": 0},
    "synthesize": {"latency_ms": 2100, "cost_usd": 0.0034, "tokens": 3200},
    "embed": {"latency_ms": 80, "cost_usd": 0.00002}
  },
  "total_cost_usd": 0.00342
}
```

### Optimization Strategies

1. **Extractive Pre-processing**: 50-70% token reduction before LLM
2. **Smart Caching**: Content-hash deduplication, configurable TTL
3. **Model Selection**: Claude Sonnet (cheap) primary, GPT-4 (reliable) fallback
4. **Batch Processing**: Amortized overhead for bulk operations
5. **Lightweight Evaluation**: Small/fast model for sufficiency checks

---

## Quality Control

### Automated Assessment

```
┌─────────────────────────────────────────────────────────────────────┐
│                    QUALITY SCORE (0-100)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Summary Quality (40%)                                              │
│  ├── Length (800-2500 chars optimal)                               │
│  ├── Coherence                                                     │
│  └── Quick summary presence                                        │
│                                                                     │
│  Metadata Quality (30%)                                             │
│  ├── Title extracted                                               │
│  ├── Keywords (5-10 terms)                                         │
│  └── Industry classification                                       │
│                                                                     │
│  Technical Quality (30%)                                            │
│  ├── Embeddings generated                                          │
│  └── No failed stages                                              │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  GRADES:  A (90+) │ B (70-89) │ C (50-69) │ D (<50)               │
└─────────────────────────────────────────────────────────────────────┘
```

### Ingest-Time Validation

- Automatic quality check during processing
- Score threshold triggers auto-retry (default: 50)
- Temperature adjustment for retries (0.3 for focused output)
- Best result selection from attempts

### Remediation Strategies

| Strategy | Trigger | Cost | Action |
|----------|---------|------|--------|
| `NONE` | Score >= 90 | $0 | No action |
| `METADATA_ENHANCEMENT` | Missing fields | ~$0.001 | Re-extract |
| `FULL_REPROCESS` | Score 50-69 | ~$0.005 | Retry same LLM |
| `ALTERNATIVE_LLM` | Persistent issues | ~$0.02 | Different provider |
| `DELETE` | Critical failures | $0 | Remove document |

---

## Observability

### Structured Logging

All components emit structured JSON logs with correlation IDs:

```json
{
  "timestamp": "2024-12-17T10:30:45Z",
  "level": "info",
  "correlation_id": "req_abc123",
  "component": "pipeline.synthesizer",
  "event": "llm_call_complete",
  "provider": "anthropic",
  "model": "claude-sonnet",
  "latency_ms": 2340,
  "tokens": {"input": 2450, "output": 890},
  "cost_usd": 0.0034
}
```

### Metrics (Prometheus/OpenTelemetry)

| Metric | Type | Labels |
|--------|------|--------|
| `hari_documents_processed_total` | Counter | source_type, status |
| `hari_pipeline_stage_duration_seconds` | Histogram | stage |
| `hari_llm_requests_total` | Counter | provider, model, status |
| `hari_llm_cost_usd_total` | Counter | provider, model |
| `hari_cache_hits_total` | Counter | cache_type |
| `hari_search_requests_total` | Counter | search_type |
| `hari_agent_research_loops_total` | Counter | outcome |
| `hari_batch_jobs_active` | Gauge | status |

### Dashboards

Key metrics surfaced in admin dashboard:

- **Cost tracking**: Daily/weekly spend by provider, cost per document trend
- **Performance**: Pipeline latency percentiles, cache hit rate
- **Quality**: Grade distribution, remediation rates
- **Agent behavior**: Research trigger rate, loop terminations, external search usage
- **Queue health**: Job backlog, failure rates, retry counts

---

## Messaging Platform Integration

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BOT CONNECTOR LAYER                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Telegram API ────┐                                                │
│                    │                                                │
│   Slack API ───────┼────► Webhook Handler ────► State Translator   │
│                    │              │                    │            │
│   (Future) ────────┘              │                    │            │
│                                   ▼                    ▼            │
│                           Message Queue         LangGraph State     │
│                                   │                    │            │
│                                   └────────┬───────────┘            │
│                                            ▼                        │
│                                    Agentic Query System             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Cross-Platform Continuity

Conversations persist in PostgreSQL, enabling:
- Start query on web, continue on Telegram
- Reference previous interactions from any platform
- Shared context across all interfaces

### Capture Modes

1. **Passive Monitoring**: HARI listens and stores relevant links/information
2. **Direct Queries**: Users ask HARI questions directly (@hari, how do I...?)
3. **Private Prompts**: Users confirm relevance before storing ("Save this link?")

---

## Deployment

### Environment Configuration

```bash
# Core
DATABASE_URL=postgresql+asyncpg://user:pass@host/hari
ENVIRONMENT=production

# LLM Providers
ANTHROPIC_API_KEY=sk-...
OPENAI_API_KEY=sk-...

# External Tools (Agentic Research)
TAVILY_API_KEY=tvly-...   # Required for agentic web search
GOOGLE_CREDENTIALS_JSON=<base64 encoded service account>

# Auth
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
HARI_ADMIN_API_KEY=<secure random string>

# Optional
JINA_API_KEY=jina_...  # For JS-heavy site fallback
```

### Database Setup

```sql
-- Requires PostgreSQL 15+ with pgvector
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### Health Check

```bash
curl https://hari.example.com/health
```

---

## Project Structure

```
hari/
├── api.py                    # FastAPI application
├── config.py                 # Pydantic settings
├── hari/
│   ├── auth/                 # OAuth, sessions, API keys
│   ├── database/
│   │   ├── models.py         # SQLAlchemy models
│   │   └── connection.py     # Async session management
│   ├── pipeline/
│   │   ├── fetcher.py        # Content acquisition
│   │   ├── cleaner.py        # Text processing
│   │   ├── extractor.py      # Extractive summarization
│   │   ├── synthesizer.py    # LLM abstraction
│   │   ├── embedder.py       # Vector generation
│   │   └── orchestrator.py   # Pipeline coordination
│   ├── agent/
│   │   ├── graph.py          # LangGraph definition
│   │   ├── nodes/            # Individual agent nodes
│   │   │   ├── retriever.py
│   │   │   ├── evaluator.py
│   │   │   ├── router.py
│   │   │   ├── researcher.py
│   │   │   └── generator.py
│   │   └── tools/            # Agent tools (Tavily, Drive)
│   ├── search/               # Semantic search
│   ├── quality/              # Assessment & remediation
│   ├── drive/                # Google Drive integration
│   └── batch/                # Background job management
├── alembic/                  # Database migrations
├── tests/                    # pytest suite
└── static/                   # Dashboard UI
```

---

## Delivery Priorities

Recommended implementation sequence:

### Phase 1: Foundation
- API-first backend with FastAPI
- Authentication (API keys, OAuth) and RBAC (user/admin roles)
- PostgreSQL + pgvector setup with Alembic migrations
- Document ingestion pipeline (URL/PDF/Drive)
- Local preprocessing (Trafilatura, Sumy) + LLM synthesis
- Embeddings generation and storage
- Basic caching layer

### Phase 2: Search & Metrics
- Hybrid search (TSVector + pgvector with RRF fusion)
- Filter support (industry, source type, date range)
- Cost tracking per stage and provider
- Quality assessment framework
- Admin endpoints for document and cost visibility

### Phase 3: Agentic Query
- LangGraph integration
- Retrieve → Evaluate → Route → Generate flow
- Researcher node with Tavily/Deep Research
- Guardrails (attempt budget, loop prevention, cost ceiling)
- Internal Drive search as research tool

### Phase 4: Background Processing
- Redis queue integration (optional, can start with asyncio)
- Batch job management for Drive folder sync
- Progress tracking, retries, failure surfacing
- Orphan job recovery on startup

### Phase 5: Real-Time & Frontends
- SSE/WebSocket endpoints for reasoning traces
- Web chat UI with thinking visibility
- Admin dashboard (metrics, jobs, quality, taxonomy)
- Connect frontends to agentic query system

### Phase 6: Hardening
- Observability (structured logging, Prometheus metrics)
- Admin controls (taxonomy editing, bulk remediation)
- Telegram/Slack bot connectors
- Load testing and performance tuning
- Security audit and rate limiting

---

## Summary

HARI transforms the challenge of information overload into an opportunity for collective intelligence:

| Challenge | HARI Solution |
|-----------|---------------|
| Information scattered across channels | Centralized knowledge base with multi-source ingestion |
| RAG fails when answer isn't in DB | Agentic system actively seeks external information |
| High LLM costs | 95% reduction via local preprocessing |
| Poor quality summaries | Automated quality control with remediation |
| Platform lock-in | API-first headless architecture |
| Lost conversation context | Cross-platform continuity via shared state |

**HARI knows what it doesn't know—and actively seeks the answer.**

---

## License

MIT License
