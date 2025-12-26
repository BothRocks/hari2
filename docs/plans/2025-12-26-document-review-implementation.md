# Document Review & Quality Validation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add admin document detail page with editable fields and pipeline validation step that auto-corrects poor metadata.

**Architecture:** Database migration adds author and review fields to Document model. New validator service in pipeline detects/corrects issues. API endpoints support detail view, updates, and re-processing. React frontend adds detail page with inline editing.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, TanStack Query, shadcn/ui

---

## Task 1: Database Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_add_review_fields_to_documents.py`
- Modify: `backend/app/models/document.py`

**Step 1: Update Document model with new fields**

Edit `backend/app/models/document.py` to add after line 55 (processing_cost_usd):

```python
    # Author
    author: Mapped[str | None] = mapped_column(String(500))

    # Quality review fields
    needs_review: Mapped[bool] = mapped_column(default=False)
    review_reasons: Mapped[list | None] = mapped_column(JSON)
    original_metadata: Mapped[dict | None] = mapped_column(JSON)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
```

Add import at top:
```python
from sqlalchemy import String, Text, Enum, Float, Integer, JSON, DateTime, ForeignKey
from datetime import datetime
```

**Step 2: Generate migration**

Run: `cd backend && uv run alembic revision --autogenerate -m "add author and review fields to documents"`

**Step 3: Run migration**

Run: `cd backend && uv run alembic upgrade head`
Expected: Migration applies successfully

**Step 4: Verify with test**

Run: `cd backend && uv run pytest tests/test_models_document.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/models/document.py backend/alembic/versions/
git commit -m "feat: add author and review fields to Document model"
```

---

## Task 2: Update Synthesizer Prompt

**Files:**
- Modify: `backend/app/services/pipeline/synthesizer.py`
- Test: `backend/tests/test_synthesizer.py`

**Step 1: Update the prompt to include author extraction**

Edit `backend/app/services/pipeline/synthesizer.py`, replace SYNTHESIS_PROMPT (lines 7-20):

```python
SYNTHESIS_PROMPT = """Analyze the following text and provide a structured summary.

TEXT:
{text}

Respond with valid JSON only, no other text:
{{
  "title": "Document title extracted or inferred from content",
  "author": "Author name(s) if identifiable from the document, null otherwise",
  "summary": "Extended summary (300-500 words) covering main points, key insights, and conclusions",
  "quick_summary": "2-3 sentence executive summary",
  "keywords": ["keyword1", "keyword2", ...],  // 5-10 relevant keywords
  "industries": ["industry1", "industry2"],   // Relevant industry classifications
  "language": "en"  // Detected language code
}}
"""
```

**Step 2: Run existing tests**

Run: `cd backend && uv run pytest tests/test_synthesizer.py -v`
Expected: PASS (existing tests should still pass)

**Step 3: Commit**

```bash
git add backend/app/services/pipeline/synthesizer.py
git commit -m "feat: add author and title extraction to synthesizer prompt"
```

---

## Task 3: Create Validator Service

**Files:**
- Create: `backend/app/services/pipeline/validator.py`
- Create: `backend/tests/test_validator.py`

**Step 1: Write tests first**

Create `backend/tests/test_validator.py`:

```python
"""Tests for document metadata validator."""
import pytest
from app.services.pipeline.validator import detect_issues, validate_and_correct


class TestDetectIssues:
    """Tests for rule-based issue detection."""

    def test_detects_generic_title(self):
        issues = detect_issues({"title": "template"})
        assert "generic_title" in issues

    def test_detects_single_word_title(self):
        issues = detect_issues({"title": "Report"})
        assert "single_word_title" in issues

    def test_detects_filename_as_title(self):
        issues = detect_issues({"title": "report_v2_final.pdf"})
        assert "filename_as_title" in issues

    def test_detects_generic_author(self):
        issues = detect_issues({"author": "admin"})
        assert "generic_author" in issues

    def test_detects_short_summary(self):
        issues = detect_issues({"summary": "This is short."})
        assert "short_summary" in issues

    def test_detects_few_keywords(self):
        issues = detect_issues({"keywords": ["one", "two"]})
        assert "few_keywords" in issues

    def test_detects_generic_keywords(self):
        issues = detect_issues({"keywords": ["business", "report", "document"]})
        assert "generic_keywords" in issues

    def test_no_issues_for_good_metadata(self):
        issues = detect_issues({
            "title": "Artificial Intelligence Market Analysis 2025",
            "author": "John Smith, PhD",
            "summary": " ".join(["word"] * 100),
            "keywords": ["AI", "machine learning", "neural networks", "automation", "robotics"],
        })
        assert len(issues) == 0


class TestValidateAndCorrect:
    """Tests for LLM-based correction."""

    @pytest.mark.asyncio
    async def test_returns_no_changes_when_no_issues(self):
        result = await validate_and_correct(
            content="Some document content",
            metadata={
                "title": "Good Title Here",
                "author": "Real Author",
                "summary": " ".join(["word"] * 100),
                "keywords": ["specific", "relevant", "keywords", "here", "now"],
            }
        )
        assert result["needs_review"] is False
        assert result["review_reasons"] == []

    @pytest.mark.asyncio
    async def test_flags_when_issues_detected(self, mocker):
        # Mock LLM to return corrections
        mock_llm = mocker.patch("app.services.pipeline.validator.LLMClient")
        mock_llm.return_value.complete = mocker.AsyncMock(return_value={
            "content": '{"title": "Corrected Title"}',
            "provider": "anthropic",
            "model": "claude-3-haiku",
            "input_tokens": 100,
            "output_tokens": 50,
        })

        result = await validate_and_correct(
            content="Some document content about AI trends",
            metadata={
                "title": "template",
                "author": None,
                "summary": " ".join(["word"] * 100),
                "keywords": ["AI", "trends", "technology", "market", "analysis"],
            }
        )
        assert result["needs_review"] is True
        assert "title_auto_corrected" in result["review_reasons"]
        assert result["original_metadata"]["title"] == "template"
        assert result["title"] == "Corrected Title"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_validator.py -v`
Expected: FAIL with "No module named 'app.services.pipeline.validator'"

**Step 3: Implement validator**

Create `backend/app/services/pipeline/validator.py`:

```python
"""Document metadata validator with auto-correction."""
import json
import re
from typing import Any

from app.services.llm.client import LLMClient

GENERIC_TITLES = {"template", "untitled", "document", "doc", "file", "copy", "draft", "new", "test"}
GENERIC_AUTHORS = {"author", "admin", "user", "unknown", "anonymous", "n/a", "na", "none"}
GENERIC_KEYWORDS = {"business", "report", "document", "information", "data", "file", "content"}

FILENAME_PATTERN = re.compile(r"^[\w\-]+\.(pdf|doc|docx|txt|xlsx?)$", re.IGNORECASE)
USERNAME_PATTERN = re.compile(r"^[\w.]+@|^\w+_\w+$|^user\d+$", re.IGNORECASE)


def looks_like_filename(title: str) -> bool:
    """Check if title looks like a filename."""
    return bool(FILENAME_PATTERN.match(title.strip()))


def looks_like_username(author: str) -> bool:
    """Check if author looks like a username or email."""
    return bool(USERNAME_PATTERN.match(author.strip()))


def detect_issues(metadata: dict[str, Any]) -> list[str]:
    """
    Detect quality issues in document metadata using rules.

    Returns list of issue codes.
    """
    issues = []

    # Title checks
    title = (metadata.get("title") or "").lower().strip()
    if title in GENERIC_TITLES:
        issues.append("generic_title")
    elif title and len(title.split()) == 1 and len(title) < 20:
        issues.append("single_word_title")
    if looks_like_filename(metadata.get("title") or ""):
        issues.append("filename_as_title")

    # Author checks
    author = (metadata.get("author") or "").lower().strip()
    if author in GENERIC_AUTHORS:
        issues.append("generic_author")
    if author and looks_like_username(author):
        issues.append("author_looks_like_username")

    # Summary checks
    summary = metadata.get("summary") or ""
    if summary and len(summary.split()) < 50:
        issues.append("short_summary")

    # Keywords checks
    keywords = [k.lower() for k in (metadata.get("keywords") or [])]
    if 0 < len(keywords) < 3:
        issues.append("few_keywords")
    if keywords and set(keywords).issubset(GENERIC_KEYWORDS):
        issues.append("generic_keywords")

    return issues


CORRECTION_PROMPT = """Analyze this document and fix the metadata issues identified.

DOCUMENT CONTENT (first 5000 chars):
{content}

CURRENT METADATA:
- Title: {title}
- Author: {author}
- Summary: {summary}
- Keywords: {keywords}

ISSUES DETECTED: {issues}

Based on the actual document content, provide corrected values ONLY for fields with issues.
Respond with valid JSON only:
{{
  "title": "Corrected title based on content" or null if no fix needed,
  "author": "Corrected author" or null if no fix needed,
  "summary": "Corrected summary" or null if no fix needed,
  "keywords": ["corrected", "keywords"] or null if no fix needed
}}
"""


async def validate_and_correct(
    content: str,
    metadata: dict[str, Any],
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """
    Validate document metadata and auto-correct issues.

    Args:
        content: Document text content
        metadata: Extracted metadata (title, author, summary, keywords)
        llm_client: Optional LLM client

    Returns:
        Dictionary with:
            - needs_review: bool
            - review_reasons: list of issue codes
            - original_metadata: dict of original values (if corrected)
            - Corrected field values (title, author, etc.)
    """
    issues = detect_issues(metadata)

    if not issues:
        return {
            "needs_review": False,
            "review_reasons": [],
        }

    # Prepare result
    result = {
        "needs_review": True,
        "review_reasons": list(issues),
        "original_metadata": {},
    }

    # Try to auto-correct using LLM
    client = llm_client or LLMClient()

    prompt = CORRECTION_PROMPT.format(
        content=content[:5000],
        title=metadata.get("title"),
        author=metadata.get("author"),
        summary=metadata.get("summary", "")[:500],
        keywords=metadata.get("keywords"),
        issues=", ".join(issues),
    )

    try:
        response = await client.complete(
            prompt=prompt,
            system="You are a document metadata correction assistant. Respond only with valid JSON.",
            max_tokens=1000,
            temperature=0.3,
        )

        # Parse response
        content_text = response["content"]
        if "```json" in content_text:
            content_text = content_text.split("```json")[1].split("```")[0]
        elif "```" in content_text:
            content_text = content_text.split("```")[1].split("```")[0]

        corrections = json.loads(content_text.strip())

        # Apply corrections and track originals
        for field in ["title", "author", "summary", "keywords"]:
            if corrections.get(field) is not None:
                result["original_metadata"][field] = metadata.get(field)
                result[field] = corrections[field]
                # Update review reason to show it was auto-corrected
                result["review_reasons"] = [
                    f"{r}_auto_corrected" if r.startswith(field.split("_")[0]) or field in r else r
                    for r in result["review_reasons"]
                ]
                if f"{field}_auto_corrected" not in result["review_reasons"]:
                    # Add auto_corrected flag for this field
                    for i, reason in enumerate(result["review_reasons"]):
                        if field in reason or reason.startswith(field[:4]):
                            result["review_reasons"][i] = f"{reason.replace('_auto_corrected', '')}_auto_corrected"
                            break

        # Simplify review_reasons to just show what was corrected
        corrected_fields = list(result["original_metadata"].keys())
        result["review_reasons"] = [f"{f}_auto_corrected" for f in corrected_fields] + [
            r for r in issues if not any(f in r for f in corrected_fields)
        ]

    except Exception:
        # If LLM fails, just flag without correction
        pass

    return result
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_validator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/pipeline/validator.py backend/tests/test_validator.py
git commit -m "feat: add document metadata validator with auto-correction"
```

---

## Task 4: Integrate Validator into Pipeline

**Files:**
- Modify: `backend/app/services/pipeline/orchestrator.py`
- Modify: `backend/tests/test_pipeline_orchestrator.py`

**Step 1: Update orchestrator**

Edit `backend/app/services/pipeline/orchestrator.py`:

Add import at top:
```python
from app.services.pipeline.validator import validate_and_correct
```

Replace `_process_text` method (lines 43-93) with:

```python
    async def _process_text(self, text: str, metadata: dict[str, Any], source_url: str) -> dict[str, Any]:
        """Process extracted text through remaining pipeline stages."""
        # Stage 2: Clean
        cleaned_text = clean_text(text)
        if not cleaned_text:
            return {"status": "failed", "error": "No content extracted"}

        token_count = count_tokens(cleaned_text)

        # Stage 3: Extractive summary (for long texts)
        if token_count > 2000:
            extractive = extractive_summarize(cleaned_text, sentence_count=30)
        else:
            extractive = cleaned_text

        # Stage 4: LLM synthesis
        synthesis = await synthesize_document(extractive)
        if "error" in synthesis:
            return {"status": "failed", "error": synthesis["error"]}

        # Stage 5: Validate and auto-correct metadata
        validation = await validate_and_correct(
            content=cleaned_text,
            metadata={
                "title": metadata.get("title") or synthesis.get("title"),
                "author": synthesis.get("author"),
                "summary": synthesis.get("summary"),
                "keywords": synthesis.get("keywords"),
            }
        )

        # Merge corrections into synthesis
        final_title = validation.get("title") or metadata.get("title") or synthesis.get("title")
        final_author = validation.get("author") or synthesis.get("author")
        final_summary = validation.get("summary") or synthesis.get("summary")
        final_keywords = validation.get("keywords") or synthesis.get("keywords")

        # Stage 6: Generate embedding (use corrected summary)
        embed_text = final_summary or cleaned_text[:5000]
        embedding = await generate_embedding(embed_text)

        # Stage 7: Quality scoring
        quality_score = calculate_quality_score(
            summary=final_summary,
            quick_summary=synthesis.get("quick_summary"),
            keywords=final_keywords,
            industries=synthesis.get("industries"),
            has_embedding=embedding is not None,
        )

        # Generate content hash for deduplication
        content_hash = hashlib.sha256(cleaned_text.encode()).hexdigest()

        return {
            "status": "completed",
            "content": cleaned_text,
            "content_hash": content_hash,
            "title": final_title,
            "author": final_author,
            "summary": final_summary,
            "quick_summary": synthesis.get("quick_summary"),
            "keywords": final_keywords,
            "industries": synthesis.get("industries"),
            "language": synthesis.get("language"),
            "embedding": embedding,
            "quality_score": quality_score,
            "token_count": token_count,
            "llm_metadata": synthesis.get("llm_metadata"),
            # Validation results
            "needs_review": validation.get("needs_review", False),
            "review_reasons": validation.get("review_reasons"),
            "original_metadata": validation.get("original_metadata"),
        }
```

**Step 2: Run pipeline tests**

Run: `cd backend && uv run pytest tests/test_pipeline_orchestrator.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/app/services/pipeline/orchestrator.py
git commit -m "feat: integrate validator into document pipeline"
```

---

## Task 5: Update Document API Endpoints

**Files:**
- Modify: `backend/app/schemas/document.py`
- Modify: `backend/app/api/documents.py`
- Modify: `backend/tests/test_api_documents.py`

**Step 1: Update schemas**

Replace `backend/app/schemas/document.py`:

```python
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class DocumentCreate(BaseModel):
    url: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    author: str | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str | None
    source_type: str
    title: str | None
    author: str | None
    quick_summary: str | None
    keywords: list[str] | None
    industries: list[str] | None
    quality_score: float | None
    processing_status: str
    needs_review: bool
    created_at: datetime


class DocumentDetail(DocumentResponse):
    summary: str | None
    content: str | None
    language: str | None
    error_message: str | None
    token_count: int | None
    processing_cost_usd: float | None
    review_reasons: list[str] | None
    original_metadata: dict | None
    reviewed_at: datetime | None
    reviewed_by_email: str | None = None
    updated_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class ReprocessResponse(BaseModel):
    job_id: UUID
    message: str
```

**Step 2: Add new API endpoints**

Add to `backend/app/api/documents.py` after the delete endpoint:

```python
from app.schemas.document import DocumentUpdate, ReprocessResponse
from app.models.job import Job, JobType, JobStatus


@router.put("/{document_id}", response_model=DocumentDetail)
async def update_document(
    document_id: UUID,
    update_data: DocumentUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentDetail:
    """Update document editable fields (title, author)."""
    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    if update_data.title is not None:
        document.title = update_data.title
    if update_data.author is not None:
        document.author = update_data.author

    await session.commit()
    await session.refresh(document)

    return DocumentDetail.model_validate(document)


@router.post("/{document_id}/reprocess", response_model=ReprocessResponse)
async def reprocess_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> ReprocessResponse:
    """Trigger full pipeline re-processing for a document."""
    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Create reprocess job
    job = Job(
        job_type=JobType.PROCESS_DOCUMENT,
        payload={"document_id": str(document_id), "reprocess": True},
        created_by_id=user.id,
        status=JobStatus.PENDING,
    )
    session.add(job)
    await session.commit()

    return ReprocessResponse(
        job_id=job.id,
        message=f"Reprocessing job created for document {document_id}"
    )


@router.post("/{document_id}/review", response_model=DocumentDetail)
async def mark_document_reviewed(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentDetail:
    """Mark document as reviewed, clearing the needs_review flag."""
    from datetime import datetime, timezone

    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    document.needs_review = False
    document.reviewed_at = datetime.now(timezone.utc)
    document.reviewed_by_id = user.id

    await session.commit()
    await session.refresh(document)

    return DocumentDetail.model_validate(document)
```

Also update the existing document handlers to save the new fields. Find where documents are saved after pipeline processing (around lines 62-77) and add:

```python
            document.author = pipeline_result.get("author")
            document.needs_review = pipeline_result.get("needs_review", False)
            document.review_reasons = pipeline_result.get("review_reasons")
            document.original_metadata = pipeline_result.get("original_metadata")
```

**Step 3: Run API tests**

Run: `cd backend && uv run pytest tests/test_api_documents.py -v`
Expected: PASS (may need test updates)

**Step 4: Commit**

```bash
git add backend/app/schemas/document.py backend/app/api/documents.py
git commit -m "feat: add document update, reprocess, and review endpoints"
```

---

## Task 6: Update Job Worker for Reprocessing

**Files:**
- Modify: `backend/app/services/jobs/worker.py`

**Step 1: Update _process_document to handle reprocessing**

In `backend/app/services/jobs/worker.py`, update `_process_document` method to handle the reprocess case:

```python
    async def _process_document(self, job: Job, queue: AsyncioJobQueue, session: AsyncSession) -> None:
        """Process a single document."""
        url = job.payload.get("url")
        document_id = job.payload.get("document_id")
        is_reprocess = job.payload.get("reprocess", False)

        if not url and not document_id:
            raise ValueError("Payload must contain either 'url' or 'document_id'")

        await queue.log(
            job.id,
            LogLevel.INFO,
            "Starting document processing",
            {"url": url, "document_id": str(document_id) if document_id else None, "reprocess": is_reprocess}
        )

        if is_reprocess and document_id:
            # Get existing document
            result = await session.execute(
                select(Document).where(Document.id == UUID(document_id))
            )
            document = result.scalar_one_or_none()
            if not document:
                raise ValueError(f"Document {document_id} not found")

            # Reset status
            document.processing_status = ProcessingStatus.PROCESSING
            await session.commit()

            # Reprocess based on source type
            pipeline = DocumentPipeline()
            if document.source_type == SourceType.URL and document.url:
                pipeline_result = await pipeline.process_url(document.url)
            else:
                raise ValueError(f"Cannot reprocess document with source_type {document.source_type}")

            if pipeline_result.get("status") == "failed":
                document.processing_status = ProcessingStatus.FAILED
                document.error_message = pipeline_result.get("error")
            else:
                document.processing_status = ProcessingStatus.COMPLETED
                document.content = pipeline_result.get("content")
                document.content_hash = pipeline_result.get("content_hash")
                document.title = pipeline_result.get("title")
                document.author = pipeline_result.get("author")
                document.summary = pipeline_result.get("summary")
                document.quick_summary = pipeline_result.get("quick_summary")
                document.keywords = pipeline_result.get("keywords")
                document.industries = pipeline_result.get("industries")
                document.language = pipeline_result.get("language")
                document.embedding = pipeline_result.get("embedding")
                document.quality_score = pipeline_result.get("quality_score")
                document.token_count = pipeline_result.get("token_count")
                document.needs_review = pipeline_result.get("needs_review", False)
                document.review_reasons = pipeline_result.get("review_reasons")
                document.original_metadata = pipeline_result.get("original_metadata")
                # Clear previous review
                document.reviewed_at = None
                document.reviewed_by_id = None

            await session.commit()
            await queue.log(job.id, LogLevel.INFO, "Document reprocessing completed")
        else:
            # Original URL processing logic
            await queue.log(job.id, LogLevel.INFO, "Document processing completed")
```

Add import at top:
```python
from app.models.document import Document, SourceType, ProcessingStatus
```

**Step 2: Run worker tests**

Run: `cd backend && uv run pytest tests/test_job_worker.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/app/services/jobs/worker.py
git commit -m "feat: add document reprocessing support to job worker"
```

---

## Task 7: Frontend Document Detail Page

**Files:**
- Create: `frontend/src/pages/DocumentDetailPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Add API functions**

Add to `frontend/src/lib/api.ts`:

```typescript
export const documentsApi = {
  // ... existing methods ...

  get: async (id: string) => {
    const response = await fetchWithAuth(`/api/documents/${id}`);
    return response.json();
  },

  update: async (id: string, data: { title?: string; author?: string }) => {
    const response = await fetchWithAuth(`/api/documents/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return response.json();
  },

  reprocess: async (id: string) => {
    const response = await fetchWithAuth(`/api/documents/${id}/reprocess`, {
      method: 'POST',
    });
    return response.json();
  },

  markReviewed: async (id: string) => {
    const response = await fetchWithAuth(`/api/documents/${id}/review`, {
      method: 'POST',
    });
    return response.json();
  },
};
```

**Step 2: Create DocumentDetailPage**

Create `frontend/src/pages/DocumentDetailPage.tsx`:

```tsx
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ArrowLeft, RefreshCw, Check, ExternalLink, AlertTriangle } from 'lucide-react';
import { useState } from 'react';

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [editingTitle, setEditingTitle] = useState(false);
  const [editingAuthor, setEditingAuthor] = useState(false);
  const [titleValue, setTitleValue] = useState('');
  const [authorValue, setAuthorValue] = useState('');

  const { data: document, isLoading } = useQuery({
    queryKey: ['document', id],
    queryFn: () => documentsApi.get(id!),
    enabled: !!id,
  });

  const updateMutation = useMutation({
    mutationFn: (data: { title?: string; author?: string }) =>
      documentsApi.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      setEditingTitle(false);
      setEditingAuthor(false);
    },
  });

  const reprocessMutation = useMutation({
    mutationFn: () => documentsApi.reprocess(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
    },
  });

  const reviewMutation = useMutation({
    mutationFn: () => documentsApi.markReviewed(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
    },
  });

  if (isLoading) return <div>Loading...</div>;
  if (!document) return <div>Document not found</div>;

  const handleTitleSave = () => {
    updateMutation.mutate({ title: titleValue });
  };

  const handleAuthorSave = () => {
    updateMutation.mutate({ author: authorValue });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={() => navigate('/admin')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Documents
        </Button>
        <Button
          onClick={() => reprocessMutation.mutate()}
          disabled={reprocessMutation.isPending}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${reprocessMutation.isPending ? 'animate-spin' : ''}`} />
          Re-process
        </Button>
      </div>

      {document.needs_review && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <div>
              <strong>Needs Review:</strong> {document.review_reasons?.join(', ')}
              {document.original_metadata?.title && (
                <div className="text-sm text-muted-foreground mt-1">
                  Original title: "{document.original_metadata.title}"
                </div>
              )}
            </div>
            <Button
              size="sm"
              onClick={() => reviewMutation.mutate()}
              disabled={reviewMutation.isPending}
            >
              <Check className="h-4 w-4 mr-1" />
              Mark as Reviewed
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <Card className="p-6 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-muted-foreground">Title</label>
            {editingTitle ? (
              <div className="flex gap-2">
                <Input
                  value={titleValue}
                  onChange={(e) => setTitleValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleTitleSave()}
                />
                <Button size="sm" onClick={handleTitleSave}>Save</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditingTitle(false)}>Cancel</Button>
              </div>
            ) : (
              <p
                className="font-medium cursor-pointer hover:bg-accent p-1 rounded"
                onClick={() => { setTitleValue(document.title || ''); setEditingTitle(true); }}
              >
                {document.title || 'Untitled'}
              </p>
            )}
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Author</label>
            {editingAuthor ? (
              <div className="flex gap-2">
                <Input
                  value={authorValue}
                  onChange={(e) => setAuthorValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAuthorSave()}
                />
                <Button size="sm" onClick={handleAuthorSave}>Save</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditingAuthor(false)}>Cancel</Button>
              </div>
            ) : (
              <p
                className="cursor-pointer hover:bg-accent p-1 rounded"
                onClick={() => { setAuthorValue(document.author || ''); setEditingAuthor(true); }}
              >
                {document.author || 'Unknown'}
              </p>
            )}
          </div>
        </div>

        <div className="flex gap-4">
          <Badge variant={document.processing_status === 'completed' ? 'default' : 'destructive'}>
            {document.processing_status}
          </Badge>
          <span className="text-sm">Quality: {document.quality_score?.toFixed(0) || '-'}</span>
          <span className="text-sm">Source: {document.source_type}</span>
          {document.url && (
            <a href={document.url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-500 flex items-center gap-1">
              <ExternalLink className="h-3 w-3" />
              View Source
            </a>
          )}
        </div>

        <Separator />

        <div>
          <label className="text-sm text-muted-foreground">Quick Summary</label>
          <p className="mt-1">{document.quick_summary || 'No summary'}</p>
        </div>

        <div>
          <label className="text-sm text-muted-foreground">Full Summary</label>
          <p className="mt-1 whitespace-pre-wrap">{document.summary || 'No summary'}</p>
        </div>

        <Separator />

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-muted-foreground">Keywords</label>
            <div className="flex flex-wrap gap-1 mt-1">
              {document.keywords?.map((kw: string) => (
                <Badge key={kw} variant="outline">{kw}</Badge>
              ))}
            </div>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Industries</label>
            <div className="flex flex-wrap gap-1 mt-1">
              {document.industries?.map((ind: string) => (
                <Badge key={ind} variant="outline">{ind}</Badge>
              ))}
            </div>
          </div>
        </div>

        <Separator />

        <div className="grid grid-cols-4 gap-4 text-sm">
          <div>
            <label className="text-muted-foreground">Language</label>
            <p>{document.language || '-'}</p>
          </div>
          <div>
            <label className="text-muted-foreground">Token Count</label>
            <p>{document.token_count?.toLocaleString() || '-'}</p>
          </div>
          <div>
            <label className="text-muted-foreground">Processing Cost</label>
            <p>{document.processing_cost_usd ? `$${document.processing_cost_usd.toFixed(4)}` : '-'}</p>
          </div>
          <div>
            <label className="text-muted-foreground">Content Hash</label>
            <p className="font-mono text-xs truncate">{document.content_hash || '-'}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <label className="text-muted-foreground">Created</label>
            <p>{new Date(document.created_at).toLocaleString()}</p>
          </div>
          <div>
            <label className="text-muted-foreground">Updated</label>
            <p>{new Date(document.updated_at).toLocaleString()}</p>
          </div>
        </div>

        {document.error_message && (
          <>
            <Separator />
            <div>
              <label className="text-sm text-muted-foreground">Error</label>
              <p className="text-destructive mt-1">{document.error_message}</p>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
```

**Step 3: Add route to App.tsx**

Add import and route in `frontend/src/App.tsx`:

```tsx
import { DocumentDetailPage } from '@/pages/DocumentDetailPage';

// In routes:
<Route path="/admin/documents/:id" element={<DocumentDetailPage />} />
```

**Step 4: Update DocumentsTable to link to detail**

In `frontend/src/components/admin/DocumentsTable.tsx`, make title clickable:

```tsx
import { useNavigate } from 'react-router-dom';

// Inside component:
const navigate = useNavigate();

// Replace title cell:
<TableCell
  className="font-medium cursor-pointer hover:underline"
  onClick={() => navigate(`/admin/documents/${doc.id}`)}
>
  {doc.title || doc.url || 'Untitled'}
</TableCell>
```

**Step 5: Run frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add frontend/src/pages/DocumentDetailPage.tsx frontend/src/App.tsx frontend/src/lib/api.ts frontend/src/components/admin/DocumentsTable.tsx
git commit -m "feat: add document detail page with editing and review"
```

---

## Task 8: Add Needs Review Filter to Documents List

**Files:**
- Modify: `backend/app/api/documents.py`
- Modify: `frontend/src/components/admin/DocumentsTable.tsx`

**Step 1: Add needs_review filter to API**

In `backend/app/api/documents.py`, update list_documents:

```python
@router.get("/", response_model=DocumentList)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ProcessingStatus | None = Query(None),
    needs_review: bool | None = Query(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentList:
    """List documents with pagination and filters."""
    query = select(Document)
    count_query = select(func.count()).select_from(Document)

    if status:
        query = query.where(Document.processing_status == status)
        count_query = count_query.where(Document.processing_status == status)

    if needs_review is not None:
        query = query.where(Document.needs_review == needs_review)
        count_query = count_query.where(Document.needs_review == needs_review)

    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Document.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    documents = result.scalars().all()

    return DocumentList(
        items=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )
```

**Step 2: Add filter toggle in frontend**

Update `frontend/src/components/admin/DocumentsTable.tsx` to add a filter:

```tsx
import { useState } from 'react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

// In component:
const [showNeedsReview, setShowNeedsReview] = useState(false);

const { data, isLoading } = useQuery({
  queryKey: ['documents', showNeedsReview],
  queryFn: () => documentsApi.list(showNeedsReview ? { needs_review: true } : {}),
});

// Add filter UI before table:
<div className="flex items-center space-x-2 mb-4">
  <Switch
    id="needs-review"
    checked={showNeedsReview}
    onCheckedChange={setShowNeedsReview}
  />
  <Label htmlFor="needs-review">Show only documents needing review</Label>
</div>
```

Update api.ts list function:
```typescript
list: async (params?: { needs_review?: boolean }) => {
  const searchParams = new URLSearchParams();
  if (params?.needs_review !== undefined) {
    searchParams.set('needs_review', String(params.needs_review));
  }
  const url = searchParams.toString()
    ? `/api/documents/?${searchParams}`
    : '/api/documents/';
  const response = await fetchWithAuth(url);
  return response.json();
},
```

**Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_api_documents.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/api/documents.py frontend/src/components/admin/DocumentsTable.tsx frontend/src/lib/api.ts
git commit -m "feat: add needs_review filter to documents list"
```

---

## Task 9: Run Full Test Suite

**Step 1: Run backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All tests pass

**Step 2: Run frontend tests**

Run: `cd frontend && npm test`
Expected: All tests pass

**Step 3: Run build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Final commit if any fixes needed**

---

## Task 10: Update TODO.md

**Files:**
- Modify: `TODO.md`

Add to completed section:
- Document detail page with editable title/author
- Quality validation pipeline step with auto-correction
- Needs review filtering in admin

Commit:
```bash
git add TODO.md
git commit -m "docs: mark document review and validation as complete"
```
