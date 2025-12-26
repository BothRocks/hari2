# Document Review & Quality Validation Design

## Overview

Two features to improve data quality:
1. **Document Detail Page** - Admin UI to review and edit document metadata
2. **Quality Validation** - Pipeline step to detect and auto-correct poor metadata

## Data Model Changes

Add to `Document` model:

```python
# New content field
author: Mapped[str | None] = mapped_column(String(500))

# Quality review fields
needs_review: Mapped[bool] = mapped_column(default=False)
review_reasons: Mapped[list | None] = mapped_column(JSON)
original_metadata: Mapped[dict | None] = mapped_column(JSON)
reviewed_at: Mapped[datetime | None] = mapped_column()
reviewed_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
```

**Fields explained:**
- `author` - Document author(s) extracted by synthesizer
- `needs_review` - Flag for admin attention
- `review_reasons` - List of issue codes: `["title_auto_corrected", "generic_author"]`
- `original_metadata` - Pre-correction values for admin reference
- `reviewed_at/reviewed_by_id` - Audit trail when admin clears flag

## Quality Validation Pipeline Step

### Position in Pipeline

```
1. fetch → 2. clean → 3. extractive_summarize → 4. synthesize → 5. validate → 6. embed → 7. score
```

Runs after synthesize (needs metadata to validate) and before embed (so corrections are embedded).

### Two-Pass Approach

**Pass 1: Rule-based detection (no LLM cost)**

```python
GENERIC_TITLES = {"template", "untitled", "document", "doc", "file", "copy", "draft"}
GENERIC_AUTHORS = {"author", "admin", "user", "unknown"}
GENERIC_KEYWORDS = {"business", "report", "document", "information", "data"}

def detect_issues(doc_data: dict) -> list[str]:
    issues = []
    title = (doc_data.get("title") or "").lower().strip()
    author = (doc_data.get("author") or "").lower().strip()

    # Title checks
    if title in GENERIC_TITLES:
        issues.append("generic_title")
    if len(title.split()) == 1 and len(title) < 20:
        issues.append("single_word_title")
    if looks_like_filename(title):
        issues.append("filename_as_title")

    # Author checks
    if author in GENERIC_AUTHORS:
        issues.append("generic_author")
    if looks_like_email_or_username(author):
        issues.append("author_looks_like_username")

    # Summary checks
    summary = doc_data.get("summary") or ""
    if len(summary.split()) < 50:
        issues.append("short_summary")

    # Keywords checks
    keywords = set(k.lower() for k in (doc_data.get("keywords") or []))
    if len(keywords) < 3:
        issues.append("few_keywords")
    if keywords and keywords.issubset(GENERIC_KEYWORDS):
        issues.append("generic_keywords")

    return issues
```

**Pass 2: LLM correction (only if issues found)**

```python
VALIDATION_PROMPT = """Analyze this document and fix the metadata issues identified.

DOCUMENT CONTENT (first 5000 chars):
{content}

CURRENT METADATA:
- Title: {title}
- Author: {author}
- Summary: {summary}
- Keywords: {keywords}

ISSUES DETECTED: {issues}

Based on the actual document content, provide corrected values ONLY for fields with issues.
Respond with valid JSON:
{{
  "title": "Corrected title based on content" or null if no fix needed,
  "author": "Corrected author" or null if no fix needed,
  "summary": "Corrected summary" or null if no fix needed,
  "keywords": ["corrected", "keywords"] or null if no fix needed
}}
"""
```

### Validator Output

```python
{
    "needs_review": True,
    "review_reasons": ["title_auto_corrected", "few_keywords"],
    "original_metadata": {"title": "template", "author": null},
    # Corrected fields (overwrite synthesizer output)
    "title": "Artificial Intelligence Market Trends 2025",
    "author": "Deloitte Research Team",
}
```

## Synthesizer Prompt Update

Add author extraction to existing prompt:

```json
{
  "summary": "Extended summary (300-500 words)...",
  "quick_summary": "2-3 sentence executive summary",
  "author": "Author name(s) if identifiable from the document, null otherwise",
  "keywords": ["keyword1", "keyword2"],
  "industries": ["industry1", "industry2"],
  "language": "en"
}
```

## Backend API

### New Endpoints

```
GET  /api/documents/{id}           - Get full document details
PUT  /api/documents/{id}           - Update editable fields (title, author)
POST /api/documents/{id}/reprocess - Trigger full pipeline re-run
POST /api/documents/{id}/review    - Mark as reviewed (clears flag)
```

### Response Schema: DocumentDetail

```python
class DocumentDetail(BaseModel):
    id: UUID
    url: str | None
    source_type: str
    title: str | None
    author: str | None
    content: str | None
    summary: str | None
    quick_summary: str | None
    keywords: list[str] | None
    industries: list[str] | None
    language: str | None
    quality_score: float | None
    processing_status: str
    error_message: str | None
    token_count: int | None
    processing_cost_usd: float | None
    # Review fields
    needs_review: bool
    review_reasons: list[str] | None
    original_metadata: dict | None
    reviewed_at: datetime | None
    reviewed_by: str | None  # User email
    # Timestamps
    created_at: datetime
    updated_at: datetime
```

### Request Schema: DocumentUpdate

```python
class DocumentUpdate(BaseModel):
    title: str | None = None
    author: str | None = None
```

### POST /api/documents/{id}/reprocess

- Creates new PROCESS_DOCUMENT job with `document_id` in payload
- Re-runs full pipeline, overwrites all fields
- Returns `{"job_id": "uuid"}`

### POST /api/documents/{id}/review

- Sets `needs_review = False`
- Sets `reviewed_at = now()`
- Sets `reviewed_by_id = current_user.id`
- Returns updated document

## Frontend: Document Detail Page

### Route

`/admin/documents/:id`

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ← Back to Documents                          [Re-process]  │
├─────────────────────────────────────────────────────────────┤
│  ⚠️ Needs Review: title_auto_corrected, few_keywords        │
│  Original title was: "template"                              │
├─────────────────────────────────────────────────────────────┤
│  Title: [Artificial Intelligence Market Trends 2025    ] ✏️  │
│  Author: [Deloitte Research Team                       ] ✏️  │
│  Status: COMPLETED        Quality Score: 85                  │
│  Source: DRIVE            URL: [link to Drive file]          │
├─────────────────────────────────────────────────────────────┤
│  Quick Summary                                               │
│  This report analyzes AI market trends...                    │
├─────────────────────────────────────────────────────────────┤
│  Full Summary                                                │
│  [Longer summary text displayed read-only...]                │
├─────────────────────────────────────────────────────────────┤
│  Keywords: AI, Market, Trends, Technology                    │
│  Industries: Technology, Finance                             │
│  Language: en                                                │
├─────────────────────────────────────────────────────────────┤
│  Metadata                                                    │
│  Token Count: 4,521    Processing Cost: $0.0023              │
│  Created: 2025-12-20   Processed: 2025-12-20                │
│  Content Hash: a1b2c3...                                     │
├─────────────────────────────────────────────────────────────┤
│  [Mark as Reviewed]   [Delete Document]                      │
└─────────────────────────────────────────────────────────────┘
```

### Interactions

- Title and Author are inline-editable (save on blur or Enter)
- "Mark as Reviewed" clears flag, only visible when `needs_review=true`
- "Re-process" triggers full pipeline, shows job progress
- "Delete" with confirmation dialog

### Link from DocumentsTable

Add click handler to table rows or a "View" button to navigate to detail page.

## Implementation Order

1. Database migration (add new fields)
2. Update synthesizer prompt (add author)
3. Create validator service
4. Integrate validator into pipeline
5. Backend API endpoints
6. Frontend detail page
7. Link from DocumentsTable
8. Tests for validator and API
