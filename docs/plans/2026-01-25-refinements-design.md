# HARI Refinements - Design Document

**Date:** 2026-01-25
**Status:** Approved

## Overview

This document covers eight improvements to HARI: agent guardrails, author detection, status command performance, dashboard UX, drive folder counts, sync frequency, job timeouts, and encrypted PDF support.

---

## 1. Agent Guardrails (TODO 1.7)

**Goal:** Add cost ceiling, timeout, and date injection to agentic queries.

**Files:**
- `backend/app/agent/state.py` - add fields
- `backend/app/agent/graph.py` - accept new parameters
- `backend/app/agent/nodes/evaluator.py` - add date to prompt
- `backend/app/agent/nodes/researcher.py` - add date, track cost, check limits
- `backend/app/agent/nodes/generator.py` - add date, track cost
- `backend/app/api/query_stream.py` - accept optional timeout param

**Implementation:**
- Add to AgentState: `cost_spent_usd: float`, `start_time: float`, `timeout_seconds: int`
- Each LLM call adds cost (calculated from token counts) to `cost_spent_usd`
- Before each node: check `time.time() - start_time > timeout_seconds` → exit gracefully
- Before each LLM call: check `cost_spent_usd > cost_ceiling` → exit gracefully
- Date prefix in prompts: `"Today's date is January 25, 2026. "`

**Defaults:**
- Cost ceiling: $1.00
- Timeout: 120 seconds (API can pass 300 for extended retry)

---

## 2. Author Detection (TODO 4.3)

**Goal:** Improve author extraction for URLs by passing source context to LLM.

**Approach:**
1. Investigate Trafilatura on 2-3 failing URLs first
2. Pass URL and filename to synthesizer prompt

**Files:**
- `backend/app/services/pipeline/synthesizer.py` - add URL/filename to prompt
- `backend/app/services/pipeline/orchestrator.py` - pass URL/filename to synthesizer

**Updated prompt addition:**
```
SOURCE INFORMATION:
URL: {url or "N/A"}
Filename: {filename or "N/A"}

When extracting author, also check:
- Author names in the URL (e.g., substack.com/@authorname)
- Author names in the filename (e.g., John_Smith_Report.pdf)
```

---

## 3. Slow Status Command (TODO 4.5)

**Goal:** Diagnose and fix slow status command in chatbots.

**Approach:**
1. Add timing logs to `bot_base.py` handle_status()
2. Identify bottleneck (memory lookup, DB query, connection overhead)
3. Fix based on findings (likely: use JOIN instead of two queries)

**Files:**
- `backend/app/integrations/bot_base.py`

---

## 4. Dashboard Search, Filters, Pagination

**Goal:** Add search, filters, column sorting, and pagination to Jobs and Documents pages.

**Backend API changes:**

`GET /api/jobs/`:
- `search` - filter by filename, error message
- `status` - filter by status
- `sort_by` - column name (created_at, status, etc.)
- `sort_order` - asc/desc
- `page`, `page_size` - pagination (default 20)
- Response: `{ items: [...], total: N, page: N, page_size: N }`

`GET /api/documents/`:
- `search` - filter by title, author
- `status` - processing status
- `needs_review` - boolean filter
- `sort_by`, `sort_order`, `page`, `page_size`

**Frontend:**
- Shared `<DataTable>` component with search, filters, sortable headers, pagination
- Apply to JobsPage and DocumentsPage

**Files:**
- `backend/app/api/jobs.py`
- `backend/app/api/documents.py`
- `frontend/src/components/ui/DataTable.tsx` (new)
- `frontend/src/pages/JobsPage.tsx`
- `frontend/src/pages/AdminPage.tsx` or DocumentsPage

---

## 5. Drive Page - Unprocessed Docs Count

**Goal:** Show pending/failed document counts per folder.

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

SQL:
```sql
SELECT folder_id,
       COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
       COUNT(*) FILTER (WHERE status = 'failed') as failed_count
FROM drive_files
GROUP BY folder_id
```

**Frontend:**
- Display badges: "3 new" (blue), "2 failed" (red)

**Files:**
- `backend/app/api/drive.py`
- `frontend/src/pages/DrivePage.tsx`

---

## 6. Folder Sync Frequency

**Goal:** Reduce auto-sync from 15 minutes to 24 hours, with immediate sync on registration.

**Changes:**
1. `backend/app/core/config.py`: change default to `1440` (24 hours)
2. `backend/app/api/drive.py`: create SYNC_DRIVE_FOLDER job immediately on folder registration
3. Update `.env.example` documentation

---

## 7. Automatic Job Timeout

**Goal:** Auto-fail jobs that run longer than 10 minutes.

**Implementation:**
```python
async def process_job(self, job: Job):
    try:
        async with asyncio.timeout(600):  # 10 minutes
            await self._execute_job(job)
    except asyncio.TimeoutError:
        await self._mark_failed(job, "Job timed out after 10 minutes")
```

**Files:**
- `backend/app/services/jobs/worker.py`

---

## 8. PyCryptodome for Encrypted PDFs

**Goal:** Support encrypted PDFs and improve error messages.

**Changes:**
1. Add `pycryptodome>=3.20.0` to `backend/pyproject.toml`
2. Improve error handling in PDF extractor:
   - Try empty password for encrypted PDFs
   - Clear error for password-protected: "PDF is password-protected and cannot be processed"

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
8. Dashboard search/filters/pagination (largest change, both pages)

---

## Testing

Each change should include:
- Unit tests for new logic
- Manual verification in dev environment
- Update TODO.md status after completion
