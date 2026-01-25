# HARI Refinements - Design Document

**Date:** 2026-01-25
**Status:** Approved (Revised after Codex review)

## Overview

This document covers eight improvements to HARI: agent guardrails, author detection, status command performance, dashboard UX, drive folder counts, sync frequency, job timeouts, and encrypted PDF support.

---

## 1. Agent Guardrails (TODO 1.7)

**Goal:** Add cost ceiling, timeout, and date injection to agentic queries.

**Files:**
- `backend/app/agent/state.py` - add fields: `cost_spent_usd`, `start_time`, `timeout_seconds`, `cost_ceiling_usd`
- `backend/app/agent/graph.py` - accept new parameters, initialize state with them
- `backend/app/agent/nodes/evaluator.py` - add date to prompt, track cost after LLM call
- `backend/app/agent/nodes/researcher.py` - add date, track cost, check limits before LLM call
- `backend/app/agent/nodes/generator.py` - add date, track cost
- `backend/app/api/query.py` - accept optional `timeout_seconds` param (NOT query_stream.py)
- `backend/app/schemas/agent.py` - add `timeout_seconds` to request schema

**Pricing Map:**
Create `backend/app/agent/pricing.py`:
```python
# USD per 1M tokens (input, output)
PRICING = {
    ("anthropic", "claude-sonnet-4-20250514"): (3.00, 15.00),
    ("anthropic", "claude-3-5-sonnet-20241022"): (3.00, 15.00),
    ("openai", "gpt-4o"): (2.50, 10.00),
    # fallback
    ("default", "default"): (5.00, 15.00),
}

def calculate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    key = (provider, model)
    if key not in PRICING:
        key = ("default", "default")
    input_rate, output_rate = PRICING[key]
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
```

**Date Injection:**
Create helper in `backend/app/agent/utils.py`:
```python
from datetime import date

def get_date_context() -> str:
    today = date.today()
    return f"Today's date is {today.strftime('%B %d, %Y')}. "
```

Use in all agent prompts as system message prefix.

**Graceful Exit:**
When timeout or cost exceeded:
1. Set `state.exceeded_limit = "timeout"` or `"cost"`
2. Router detects this and routes directly to generator
3. Generator produces response with disclaimer: "Note: This response may be incomplete due to [timeout/cost limits]."
4. For SSE streaming, emit `event: warning` with limit info before final response

**Defaults:**
- Cost ceiling: $1.00
- Timeout: 120 seconds (API can pass up to 300 for extended retry)

---

## 2. Author Detection (TODO 4.3)

**Goal:** Improve author extraction for URLs by passing source context to LLM.

**Approach:**
1. Investigate Trafilatura on 2-3 failing URLs first
2. Pass URL and filename to synthesizer prompt

**Files:**
- `backend/app/services/pipeline/synthesizer.py` - update function signature and prompt
- `backend/app/services/pipeline/orchestrator.py` - pass URL/filename to synthesizer

**Function Signature Change:**
```python
# Before
async def synthesize_document(text: Optional[str], llm_client: Optional[LLMClient] = None) -> dict:

# After
async def synthesize_document(
    text: Optional[str],
    url: Optional[str] = None,
    filename: Optional[str] = None,
    llm_client: Optional[LLMClient] = None
) -> dict:
```

**Updated Prompt:**
```
SOURCE INFORMATION:
URL: {url or "N/A"}
Filename: {filename or "N/A"}

When extracting author, also check:
- Author names in the URL (e.g., substack.com/@authorname)
- Author names in the filename (e.g., John_Smith_Report.pdf)

TEXT:
{text}
```

---

## 3. Slow Status Command (TODO 4.5)

**Goal:** Diagnose and fix slow status command in chatbots.

**Note:** Codex correctly points out that document_id is inside job.payload, so a SQL JOIN won't help. The two queries are unavoidable unless we denormalize.

**Approach:**
1. Add timing logs to `bot_base.py` handle_status()
2. Identify actual bottleneck:
   - Memory lookup (should be instant)
   - DB session acquisition (connection pool?)
   - Job query (should be fast, PK lookup)
   - Document query (if job completed)
   - Webhook response time
3. Fix based on findings:
   - If connection overhead: check pool settings
   - If queries slow: add logging to see actual query time
   - Consider caching completed job status (immutable once done)

**Files:**
- `backend/app/integrations/bot_base.py`

---

## 4. Dashboard Search, Filters, Pagination

**Goal:** Add search, filters, column sorting, and pagination to Jobs page. Documents page already has pagination.

**Note:** Codex correctly identified that `GET /api/documents/` already supports `page`, `page_size`, `status`, `needs_review`. Only Jobs needs the full treatment.

**Backend API changes:**

`GET /api/admin/jobs/` (note: `/admin/jobs`, not `/api/jobs`):
- Add `search` - filter by filename (from payload), error message
- Keep existing `status`, `job_type` filters
- Add `sort_by` - column name (created_at, status, job_type)
- Add `sort_order` - asc/desc (default: desc)
- Change response to paginated format: `{ items: [...], total: N, page: N, page_size: N }`

`GET /api/documents/` - add only:
- `search` - filter by title, author (new)
- `sort_by`, `sort_order` (new)
- Keep existing: `page`, `page_size`, `status`, `needs_review`

**Frontend:**
- Update JobsPage.tsx to use paginated response, add search input, sortable columns
- Update DocumentsPage/AdminPage.tsx to add search, sortable columns
- Optionally create shared pagination/sorting components

**Files:**
- `backend/app/api/jobs.py` - add search, sorting, paginated response
- `backend/app/api/documents.py` - add search, sorting
- `backend/app/schemas/job.py` - add JobListResponse with pagination
- `frontend/src/pages/JobsPage.tsx`
- `frontend/src/components/admin/JobsTable.tsx` (if exists)
- `frontend/src/pages/AdminPage.tsx`

---

## 5. Drive Page - Unprocessed Docs Count

**Goal:** Show pending/failed document counts per folder.

**Status Semantics (from DriveFileStatus enum):**
- `pending_count`: files with status = PENDING (new, not yet processed)
- `failed_count`: files with status = FAILED (processing error)
- Exclude: PROCESSING (in progress), COMPLETED (done), REMOVED (deleted from Drive)

**Backend:**

Modify `GET /api/drive/folders` response:
```json
{
  "id": "folder-123",
  "name": "Research Papers",
  "pending_count": 3,
  "failed_count": 2
}
```

SQL aggregation (in SQLAlchemy):
```python
from sqlalchemy import func, case
from app.models.drive import DriveFile, DriveFileStatus

# Subquery for counts
counts = (
    select(
        DriveFile.folder_id,
        func.count(case((DriveFile.status == DriveFileStatus.PENDING, 1))).label('pending_count'),
        func.count(case((DriveFile.status == DriveFileStatus.FAILED, 1))).label('failed_count'),
    )
    .group_by(DriveFile.folder_id)
    .subquery()
)

# Join with folders query
```

**Frontend:**
- Display badges next to folder name: "3 new" (blue), "2 failed" (red)
- Hide badge if count is 0

**Files:**
- `backend/app/api/drive.py`
- `backend/app/schemas/drive.py` - add counts to FolderResponse
- `frontend/src/pages/DrivePage.tsx`

---

## 6. Folder Sync Frequency

**Goal:** Reduce auto-sync from 15 minutes to 24 hours, with immediate sync on registration.

**Changes:**
1. `backend/app/core/config.py`: change default from 15 to 1440 (24 hours)
2. `backend/app/api/drive.py`: after creating folder record, immediately create SYNC_DRIVE_FOLDER job
3. Update `backend/.env.example` documentation

**Implementation detail for immediate sync:**
```python
# In register_folder endpoint, after session.commit():
job = Job(
    job_type=JobType.SYNC_DRIVE_FOLDER,
    payload={"folder_id": str(folder.id)},
    status=JobStatus.PENDING,
)
session.add(job)
await session.commit()
```

---

## 7. Automatic Job Timeout

**Goal:** Auto-fail jobs that run longer than 10 minutes.

**Note:** Worker uses `process_job()` method directly, not `_execute_job()`. Need to wrap the actual processing.

**Implementation in worker.py:**
```python
async def process_job(self, job: Job, session: AsyncSession) -> None:
    """Process a single job based on its type."""
    queue = AsyncioJobQueue(session)

    try:
        async with asyncio.timeout(600):  # 10 minutes
            if job.job_type == JobType.PROCESS_DOCUMENT:
                await self._process_document(job, queue, session)
            elif job.job_type == JobType.PROCESS_BATCH:
                await self._process_batch(job, queue, session)
            # ... rest of job types

        await queue.update_status(job.id, JobStatus.COMPLETED, completed_at=datetime.now(timezone.utc))
        await session.commit()

    except asyncio.TimeoutError:
        await queue.log(job.id, LogLevel.ERROR, "Job timed out after 10 minutes")
        await queue.update_status(job.id, JobStatus.FAILED, completed_at=datetime.now(timezone.utc))
        await session.commit()

    except Exception as e:
        # existing error handling
```

**Files:**
- `backend/app/services/jobs/worker.py`

---

## 8. PyCryptodome for Encrypted PDFs

**Goal:** Support encrypted PDFs and improve error messages.

**Note:** The existing `cryptography` dependency is for python-jose (JWT auth), not PDF decryption. PyPDF2 requires `pycryptodome` specifically for AES-encrypted PDFs.

**Changes:**
1. Add `pycryptodome>=3.20.0` to `backend/pyproject.toml`
2. Improve error handling in PDF extractor

**Implementation:**
```python
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError

def extract_text_from_pdf(pdf_bytes: bytes) -> dict:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))

        if reader.is_encrypted:
            # Try empty password (some PDFs are "encrypted" but with no password)
            try:
                reader.decrypt("")
            except Exception:
                return {"error": "PDF is password-protected and cannot be processed"}

        # Extract text...

    except FileNotDecryptedError:
        return {"error": "PDF is password-protected and cannot be processed"}
    except Exception as e:
        if "PyCryptodome" in str(e) or "Crypto" in str(e):
            return {"error": "PDF uses unsupported encryption format"}
        return {"error": f"Failed to read PDF: {e}"}
```

**Files:**
- `backend/pyproject.toml`
- `backend/app/services/pipeline/pdf_extractor.py`

---

## Implementation Order

1. PyCryptodome (quick win, one dependency + small code change)
2. Folder sync frequency (config change + small API tweak)
3. Job timeout (isolated change in worker)
4. Agent guardrails (core feature, multiple files)
5. Status command investigation + fix
6. Author detection investigation + fix
7. Drive folder counts (backend + frontend)
8. Dashboard search/filters/pagination (largest change, jobs + minor docs updates)

---

## Testing

Each change should include:
- Unit tests for new logic
- Manual verification in dev environment
- Update TODO.md status after completion
