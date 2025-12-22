# Background Processing & OAuth Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Google OAuth SSO, background job infrastructure, and Google Drive folder sync to HARI.

**Architecture:** asyncio-based job queue with PostgreSQL state persistence, Google OAuth for web UI authentication, and service account for Drive API access.

**Tech Stack:** FastAPI, asyncpg, Google OAuth 2.0, Google Drive API, Google Service Account

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        HARI Backend                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Google OAuth │    │  Job Queue   │    │ Drive Sync   │      │
│  │    (SSO)     │───▶│  (asyncio)   │◀───│  (polling)   │      │
│  └──────────────┘    └──────┬───────┘    └──────────────┘      │
│         │                   │                    │              │
│         ▼                   ▼                    ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │    Users     │    │     Jobs     │    │ Drive Folders│      │
│  │   Sessions   │    │   JobLogs    │    │  Drive Files │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                             │                                   │
│                             ▼                                   │
│                    ┌──────────────┐                            │
│                    │  Documents   │                            │
│                    │  (existing)  │                            │
│                    └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

**Authentication:**
- Web UI → Google OAuth → Session cookie → Access API
- Scripts/Bots → API key header → Access API (unchanged)

---

## 1. Google OAuth SSO

### OAuth Flow

```
┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐
│Frontend│     │Backend │     │Google  │     │Database│
└───┬────┘     └───┬────┘     └───┬────┘     └───┬────┘
    │              │              │              │
    │ Click Login  │              │              │
    ├─────────────▶│              │              │
    │              │              │              │
    │ Redirect URL │              │              │
    │◀─────────────┤              │              │
    │              │              │              │
    │ Redirect to Google          │              │
    ├────────────────────────────▶│              │
    │              │              │              │
    │ Auth code callback          │              │
    │◀────────────────────────────┤              │
    │              │              │              │
    │ Code         │              │              │
    ├─────────────▶│              │              │
    │              │ Exchange code│              │
    │              ├─────────────▶│              │
    │              │ Tokens       │              │
    │              │◀─────────────┤              │
    │              │              │              │
    │              │ Create/update user + session│
    │              ├─────────────────────────────▶
    │              │              │              │
    │ Session cookie              │              │
    │◀─────────────┤              │              │
```

### Database Tables

**users:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| email | VARCHAR(255) | Google email |
| name | VARCHAR(255) | Display name |
| picture_url | TEXT | Avatar URL |
| google_id | VARCHAR(255) | Google sub claim |
| role | ENUM | admin / user |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**sessions:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| token_hash | VARCHAR(64) | SHA256 of session token |
| expires_at | TIMESTAMP | 7 days from creation |
| created_at | TIMESTAMP | |

### OAuth Scopes

- `openid email profile` - For SSO (name, email, avatar)

### Session Handling

- HTTP-only cookie with session token
- 7-day expiry, refreshed on activity
- Logout clears session from DB

---

## 2. Job Queue Infrastructure

### Abstract Interface

```python
class JobQueue:
    async def enqueue(self, job_type: str, payload: dict) -> UUID
    async def get_status(self, job_id: UUID) -> JobStatus
    async def cancel(self, job_id: UUID) -> bool

# Current implementation
class AsyncioJobQueue(JobQueue):
    # In-memory queue, state persisted to PostgreSQL
    # Jobs survive restarts via "pending" status in DB

# Future implementation
class RedisJobQueue(JobQueue):
    # Redis-backed queue, same interface
```

### Database Tables

**jobs:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| job_type | VARCHAR(50) | process_document, sync_drive_folder, etc. |
| status | ENUM | pending / running / completed / failed |
| payload | JSONB | Job-specific data |
| created_by | UUID | FK to users (nullable for system jobs) |
| created_at | TIMESTAMP | |
| started_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |

**job_logs:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| job_id | UUID | FK to jobs |
| level | ENUM | info / warn / error |
| message | TEXT | Log message |
| details | JSONB | Structured data |
| created_at | TIMESTAMP | |

### Job Types

- `process_document` - Single URL or PDF
- `process_batch` - Multiple documents (creates child jobs)
- `sync_drive_folder` - Discover new files in a folder
- `process_drive_file` - Download and process one Drive file

### Worker Behavior

1. On startup: Resume any jobs with status=running (crash recovery)
2. Pick jobs from DB where status=pending, oldest first
3. Update status to running, process, then completed/failed
4. All steps logged to job_logs with timestamps

---

## 3. Google Drive Sync

### Service Account Model

- App has a service account (e.g., `hari@your-project.iam.gserviceaccount.com`)
- Users share/invite the service account to their folders
- Service account credentials stored in backend via `GOOGLE_SERVICE_ACCOUNT_JSON`
- No user refresh tokens needed

### Folder Registration Flow

```
Admin registers folder
       │
       ▼
Backend tries to list folder with service account
       │
       ├── Success → Save folder, ready to sync
       │
       └── 403 Forbidden → "Please share folder with hari@project.iam.gserviceaccount.com"
```

### Sync Process

```
┌─────────────────────────────────────────────────────────┐
│                    Sync Folder Job                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. List files in folder via Drive API                  │
│     - Filter: PDFs and Google Docs only                 │
│     - Get: file_id, name, md5Checksum, modifiedTime     │
│                                                          │
│  2. Compare against drive_files table                   │
│     - New file? → Create record, status=pending         │
│     - Hash changed? → Update record, status=pending     │
│     - Deleted from Drive? → Mark status=removed         │
│                                                          │
│  3. Enqueue process_drive_file job for each pending     │
│                                                          │
│  4. Update folder.last_sync_at                          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Database Tables

**drive_folders:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| google_folder_id | VARCHAR(255) | Drive folder ID |
| name | VARCHAR(255) | Folder name |
| owner_id | UUID | FK to users |
| is_active | BOOLEAN | Enable/disable sync |
| last_sync_at | TIMESTAMP | |
| created_at | TIMESTAMP | |

**drive_files:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| folder_id | UUID | FK to drive_folders |
| google_file_id | VARCHAR(255) | Drive file ID |
| name | VARCHAR(500) | File name |
| md5_hash | VARCHAR(64) | For change detection |
| status | ENUM | pending / processing / completed / failed / removed |
| document_id | UUID | FK to documents (after processing) |
| error_message | TEXT | |
| created_at | TIMESTAMP | |
| processed_at | TIMESTAMP | |

### Scheduled Polling

- Background task checks all active folders every 15 minutes
- Configurable via `DRIVE_SYNC_INTERVAL_MINUTES` env var
- Skips folders synced within the interval

---

## 4. Admin Dashboard - Jobs UI

### Jobs Overview Page (`/admin/jobs`)

```
┌─────────────────────────────────────────────────────────────┐
│  Background Jobs                                    [Refresh]│
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Pending │ │ Running │ │Completed│ │ Failed  │           │
│  │   12    │ │    3    │ │   847   │ │    5    │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│                                                              │
│  Filter: [All Types ▼] [All Status ▼]    [Bulk Retry Failed]│
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Type            │ Status  │ Created    │ Actions     │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ process_document│ failed  │ 2 min ago  │ [Logs][Retry]│  │
│  │ sync_drive      │ running │ 5 min ago  │ [Logs]      │   │
│  │ process_batch   │ completed│ 1 hr ago  │ [Logs]      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Job Detail Modal

- Job metadata: type, status, payload, timestamps
- Log entries with level badges (info/warn/error)
- Full error details expandable
- Retry button for failed jobs

### Drive Folders Tab (`/admin/drive`)

- List registered folders with last sync time
- [Sync Now] button per folder
- [Add Folder] with instructions to share with service account

---

## 5. Error Handling & Logging

### Structured Job Logs

```python
await job_log(job_id, "info", "Fetching URL", {"url": url})
await job_log(job_id, "info", "Extracted content", {"chars": 15420})
await job_log(job_id, "warn", "Extractive summary short", {"ratio": 0.12})
await job_log(job_id, "error", "LLM API failed", {
    "provider": "anthropic",
    "status_code": 529,
    "message": "API overloaded",
    "attempt": 1
})
```

### Error Capture on Failure

- Full exception type and message
- Stack trace (truncated to last 10 frames)
- Processing stage where it failed
- Input that caused the failure (URL, file name)
- Any partial results (e.g., content fetched but synthesis failed)

### Retry Behavior

- No automatic retries
- Admin reviews logs, fixes issue if needed, clicks Retry
- Retry creates new job linked to original (for audit trail)

### Crash Recovery on Startup

1. Query: `SELECT * FROM jobs WHERE status = 'running'`
2. Log warning: "Found orphaned job, marking as failed"
3. Set status=failed with message "Server restarted during processing"
4. Admin can retry these manually

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_CLIENT_ID` | OAuth client ID | required |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | required |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account credentials (JSON string or file path) | required for Drive |
| `DRIVE_SYNC_INTERVAL_MINUTES` | Polling frequency | 15 |

---

## Not Included (YAGNI)

- Redis integration (designed for, not implemented)
- Real-time job progress via WebSocket
- Cost tracking per job
- Multiple OAuth providers (Google only)
- Automatic retries (manual only)
