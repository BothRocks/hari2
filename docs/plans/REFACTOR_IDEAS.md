# Refactor Ideas

This file captures technical-debt and coding-practice findings, with a short explanation and recommended remediation for each.

## 1) Blocking SDKs used in async code (HIGH)

**Where**: `backend/app/services/drive/client.py`, `backend/app/services/jobs/worker.py`, `backend/app/services/pipeline/pdf_extractor.py`

**Issue**: The Google Drive client (googleapiclient) and PDF parsing (PyPDF2) are synchronous and run inside async endpoints/worker tasks. This can block the event loop and degrade concurrency under load.

**Recommended remediation**:
- Move blocking calls to a threadpool (`anyio.to_thread.run_sync` / `asyncio.to_thread`).
- Alternatively, wrap Drive operations behind a dedicated worker/service with sync boundaries.
- Document which services are sync-only and enforce non-async usage.

---

## 2) Inconsistent processing cost metadata keys (MEDIUM)

**Where**: `backend/app/api/documents.py`, `backend/app/services/jobs/worker.py`

**Issue**: One code path reads `llm_metadata.cost_usd`, another expects `llm_metadata.total_cost_usd`. This silently drops cost data depending on where processing occurs.

**Recommended remediation**:
- Normalize the metadata shape in the pipeline (single key name).
- Add a small helper to extract cost from `llm_metadata` and reuse it everywhere.
- Add a regression test for cost attribution.

---

## 3) Legacy job path that does no work (MEDIUM)

**Where**: `backend/app/services/jobs/worker.py`

**Issue**: When a PROCESS_DOCUMENT job lacks `document_id`, the worker logs a “legacy” message and completes the job without processing anything. This hides failures and skews job stats.

**Recommended remediation**:
- Treat missing `document_id` as a hard error and mark job failed.
- If URL-only jobs are still needed, implement the full processing path and document it.
- Add validation to prevent enqueuing incomplete payloads.

---

## 4) Document mapping logic duplicated across paths (MEDIUM)

**Where**: `backend/app/api/documents.py`, `backend/app/services/jobs/worker.py`

**Issue**: Field assignment from `pipeline_result` to `Document` is repeated in multiple places. This risks drift and inconsistent behavior when fields change.

**Recommended remediation**:
- Centralize mapping in a single helper (e.g., `apply_pipeline_result(document, pipeline_result, *, is_reprocess=False)`).
- Add tests for the mapping helper to lock behavior.

---

## 5) Private method access across layers (LOW)

**Where**: `backend/app/api/drive.py`

**Issue**: The API layer calls `DriveService._load_credentials`, a private method. This creates a leaky abstraction and makes refactors brittle.

**Recommended remediation**:
- Expose a public method on `DriveService` (e.g., `get_service_account_email()`).
- Keep parsing/validation within the service layer.

---

## 6) Integration error handling swallows failures (LOW)

**Where**: `backend/app/integrations/telegram/webhook.py`, `backend/app/integrations/slack/events.py`

**Issue**: Exceptions are logged but responses return success. This hides operational failures and makes retries or alerting difficult.

**Recommended remediation**:
- Return non-2xx responses for unexpected errors in production (or configurable behavior).
- Add structured error logging and optional alert hooks.
- Consider idempotency keys to safely retry on transient failures.
