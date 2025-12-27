# Chatbot Integration Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable document ingestion via Telegram and Slack bots.

**Architecture:** Shared abstraction layer for both platforms, with PDF archival to Google Drive.

**Tech Stack:** python-telegram-bot, slack-bolt

---

## Scope

**In scope:**
- Upload documents (PDF files, URLs)
- Check processing status (last upload)
- Shared bot abstraction for code reuse
- PDF archival to Google Drive before processing

**Out of scope:**
- Querying HARI (done via web interface/API)
- Multi-tenant deployment (single instance per workspace)
- User authentication (trust platform access control)

---

## Architecture

### File Structure

```
backend/app/integrations/
├── __init__.py
├── bot_base.py              # Abstract base class
├── user_state.py            # In-memory user → last_job_id tracking
├── telegram/
│   ├── __init__.py
│   ├── bot.py               # TelegramBot implementation
│   └── webhook.py           # POST /api/integrations/telegram/webhook
└── slack/
    ├── __init__.py
    ├── bot.py               # SlackBot implementation
    └── events.py            # POST /api/integrations/slack/events
```

### Flow Diagrams

**PDF Upload:**
```
User sends PDF
    → Bot receives file
    → Upload to Drive (archive)
    → Create HARI document (source_type=DRIVE)
    → Store job_id for user
    → Reply with confirmation
```

**URL Upload:**
```
User sends URL
    → Bot receives message
    → Create HARI document directly
    → Store job_id for user
    → Reply with confirmation
```

**Status Check:**
```
User says "status"
    → Bot looks up last job_id for user
    → Fetch job status from database
    → Reply with status
```

---

## Bot Base Abstraction

```python
# backend/app/integrations/bot_base.py
from abc import ABC, abstractmethod

class BotBase(ABC):
    """Abstract base for chat platform integrations."""

    @abstractmethod
    async def handle_file(self, user_id: str, file_bytes: bytes, filename: str) -> str:
        """Handle uploaded file. Returns reply message."""
        pass

    @abstractmethod
    async def handle_url(self, user_id: str, url: str) -> str:
        """Handle URL submission. Returns reply message."""
        pass

    @abstractmethod
    async def handle_status(self, user_id: str) -> str:
        """Handle status request. Returns reply message."""
        pass

    @abstractmethod
    async def handle_unknown(self) -> str:
        """Handle unknown input. Returns help message."""
        pass
```

---

## User State Tracking

Simple in-memory dict (no database needed for MVP):

```python
# backend/app/integrations/user_state.py
from dataclasses import dataclass
from uuid import UUID

@dataclass
class UserUpload:
    job_id: UUID
    filename: str

# Key: "{platform}:{user_id}" e.g. "telegram:123456" or "slack:U12345"
_user_state: dict[str, UserUpload] = {}

def set_last_upload(platform: str, user_id: str, job_id: UUID, filename: str) -> None:
    _user_state[f"{platform}:{user_id}"] = UserUpload(job_id, filename)

def get_last_upload(platform: str, user_id: str) -> UserUpload | None:
    return _user_state.get(f"{platform}:{user_id}")
```

---

## Drive Upload Service

Add to `backend/app/services/drive.py`:

```python
async def upload_file_to_drive(
    file_content: bytes,
    filename: str,
) -> str:
    """
    Upload file to the uploads archive folder.
    Returns the Drive file ID.
    """
    folder_id = settings.drive_uploads_folder_id
    if not folder_id:
        raise ValueError("DRIVE_UPLOADS_FOLDER_ID not configured")

    # Use existing service account credentials
    # Upload file to folder
    # Return file_id
```

---

## Bot Interactions

| Input | Action | Reply |
|-------|--------|-------|
| PDF file | Upload to Drive → Process | "✅ Document uploaded!\nFile: {name}\nJob ID: {id}\nStatus: PROCESSING" |
| URL | Process directly | "✅ URL submitted!\nURL: {url}\nJob ID: {id}\nStatus: PROCESSING" |
| "status" / "/status" | Check last job | "📄 {filename}\nStatus: {status}\nScore: {score}" |
| Anything else | Show help | "Send me a PDF or URL to add to the knowledge base. Say 'status' to check your last upload." |

---

## Configuration

Add to `backend/app/core/config.py`:

```python
# Google Drive uploads folder
drive_uploads_folder_id: str | None = None

# Telegram
telegram_bot_token: str | None = None

# Slack
slack_bot_token: str | None = None
slack_signing_secret: str | None = None
```

Add to `.env`:

```bash
# Drive folder for archiving uploaded PDFs
DRIVE_UPLOADS_FOLDER_ID=1abc...

# Telegram bot
TELEGRAM_BOT_TOKEN=123456:ABC...

# Slack bot
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
```

---

## API Endpoints

### Telegram Webhook

```
POST /api/integrations/telegram/webhook
```

Receives updates from Telegram, processes messages/files.

### Slack Events

```
POST /api/integrations/slack/events
```

Receives events from Slack Events API, processes messages/files.

---

## Dependencies

```toml
# pyproject.toml
python-telegram-bot = "^21.0"
slack-bolt = "^1.18"
```

---

## Implementation Tasks

### Task 1: Configuration & Dependencies
- Add dependencies to pyproject.toml
- Add config fields for tokens and Drive folder ID
- Update .env.example

### Task 2: Drive Upload Service
- Add `upload_file_to_drive()` to drive.py
- Test with service account

### Task 3: Bot Base & User State
- Create integrations module structure
- Implement BotBase abstract class
- Implement user_state tracking

### Task 4: Telegram Bot
- Implement TelegramBot(BotBase)
- Create webhook endpoint
- Handle files, URLs, status, help

### Task 5: Slack Bot
- Implement SlackBot(BotBase)
- Create events endpoint
- Handle files, URLs, status, help

### Task 6: Integration Tests
- Test Telegram webhook with mock updates
- Test Slack events with mock payloads
- Test Drive upload flow

---

## Estimated Effort

Medium - 6 tasks, roughly half a day of focused work.
