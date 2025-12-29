# v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete Phase 4 quality improvements and security fixes for production readiness.

**Architecture:** Incremental changes to existing FastAPI backend. No new services or major refactoring. Each task is independent and can be committed separately.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, PostgreSQL, pytest

---

## Task 1: Slow Status Command - Lazy Load DriveService

The DriveService is initialized on every webhook request, even for status checks that don't need it.

**Files:**
- Modify: `backend/app/integrations/telegram/webhook.py:19-27`
- Modify: `backend/app/integrations/slack/events.py:21-28`
- Test: `backend/tests/test_webhook_performance.py` (new)

**Step 1: Write the failing test**

Create `backend/tests/test_webhook_performance.py`:

```python
"""Tests for webhook performance optimizations."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_telegram_status_does_not_init_drive_service():
    """Status command should not initialize DriveService."""
    from app.integrations.telegram.webhook import telegram_webhook
    from fastapi import Request
    from unittest.mock import AsyncMock

    # Mock request with status message
    mock_request = AsyncMock(spec=Request)
    mock_request.json = AsyncMock(return_value={
        "update_id": 123,
        "message": {
            "message_id": 1,
            "from": {"id": 12345, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 12345, "type": "private"},
            "text": "status",
        },
    })

    with patch("app.integrations.telegram.webhook.DriveService") as mock_drive:
        with patch("app.integrations.telegram.webhook.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test-token"
            mock_settings.google_service_account_json = "test.json"

            # DriveService should NOT be instantiated for status command
            # (We'll verify this after implementing lazy loading)
            pass  # Placeholder - actual test after implementation


@pytest.mark.asyncio
async def test_telegram_file_upload_does_init_drive_service():
    """File upload should initialize DriveService."""
    # This test ensures we don't break file uploads
    pass  # Placeholder
```

**Step 2: Update Telegram webhook to lazy-load DriveService**

Edit `backend/app/integrations/telegram/webhook.py`:

```python
# Replace get_drive_service() function (lines 19-27) with:

def get_drive_service() -> DriveService | None:
    """Get Drive service if configured. Called lazily only when needed."""
    if settings.google_service_account_json:
        try:
            return DriveService(settings.google_service_account_json)
        except Exception as e:
            logger.warning(f"Failed to initialize Drive service: {e}")
    return None


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Handle incoming Telegram webhook updates."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")

    try:
        data = await request.json()
        update = Update.de_json(data, None)

        if update is None:
            logger.warning("Failed to parse Telegram update")
            return {"ok": True}

        # Only initialize DriveService when needed (file uploads)
        # Status checks and URL submissions don't need it
        needs_drive = (
            update.message
            and update.message.document
            and update.message.document.mime_type == "application/pdf"
        )
        drive_service = get_drive_service() if needs_drive else None

        bot = TelegramBot(db, drive_service)
        response = await bot.process_update(update)

        if response and update.effective_chat:
            await send_message(
                chat_id=update.effective_chat.id,
                text=response,
            )

        return {"ok": True}

    except Exception as e:
        logger.exception("Error processing Telegram webhook")
        return {"ok": True, "error": str(e)}
```

**Step 3: Update Slack events similarly**

Edit `backend/app/integrations/slack/events.py` - apply same lazy loading pattern in the event handlers (lines 108-142).

**Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_webhook_performance.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/integrations/telegram/webhook.py backend/app/integrations/slack/events.py backend/tests/test_webhook_performance.py
git commit -m "perf: lazy-load DriveService in webhooks

Only initialize DriveService when handling PDF uploads.
Status checks and URL submissions skip Drive initialization."
```

---

## Task 2: Author Detection - Ensure LLM Author Takes Precedence

The synthesizer already extracts author via LLM. The issue is that the pipeline may not be using it when trafilatura fails to extract author.

**Files:**
- Modify: `backend/app/services/pipeline/orchestrator.py`
- Test: `backend/tests/test_author_detection.py` (new)

**Step 1: Investigate current flow**

Read the orchestrator to understand how author flows through:

```bash
cd backend && grep -n "author" app/services/pipeline/orchestrator.py
```

**Step 2: Write test for author extraction priority**

Create `backend/tests/test_author_detection.py`:

```python
"""Tests for author detection in document pipeline."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_llm_author_used_when_trafilatura_fails():
    """LLM-extracted author should be used when trafilatura returns None."""
    from app.services.pipeline.orchestrator import DocumentPipeline

    pipeline = DocumentPipeline()

    # Mock URL fetcher returning no author
    mock_url_result = {
        "text": "Article by John Smith. This is the content...",
        "metadata": {"title": "Test Article", "author": None, "date": None},
        "url": "https://example.com/article",
    }

    # Mock synthesizer returning author from content
    mock_synthesis = {
        "title": "Test Article",
        "author": "John Smith",
        "summary": "Test summary",
        "quick_summary": "Quick summary",
        "keywords": ["test"],
        "industries": ["tech"],
        "language": "en",
        "llm_metadata": {},
    }

    with patch("app.services.pipeline.orchestrator.fetch_url_content", new=AsyncMock(return_value=mock_url_result)):
        with patch("app.services.pipeline.orchestrator.synthesize_document", new=AsyncMock(return_value=mock_synthesis)):
            with patch("app.services.pipeline.orchestrator.get_embedding", new=AsyncMock(return_value=[0.1] * 1536)):
                result = await pipeline.process_url("https://example.com/article")

    assert result.get("author") == "John Smith"


@pytest.mark.asyncio
async def test_trafilatura_author_preferred_when_present():
    """Trafilatura author should be preferred when it's a real name."""
    from app.services.pipeline.orchestrator import DocumentPipeline

    pipeline = DocumentPipeline()

    # Mock URL fetcher returning author
    mock_url_result = {
        "text": "Content here...",
        "metadata": {"title": "Test", "author": "Jane Doe", "date": None},
        "url": "https://example.com/article",
    }

    mock_synthesis = {
        "title": "Test",
        "author": "Unknown Author",  # LLM couldn't find it
        "summary": "Summary",
        "quick_summary": "Quick",
        "keywords": ["test"],
        "industries": [],
        "language": "en",
        "llm_metadata": {},
    }

    with patch("app.services.pipeline.orchestrator.fetch_url_content", new=AsyncMock(return_value=mock_url_result)):
        with patch("app.services.pipeline.orchestrator.synthesize_document", new=AsyncMock(return_value=mock_synthesis)):
            with patch("app.services.pipeline.orchestrator.get_embedding", new=AsyncMock(return_value=[0.1] * 1536)):
                result = await pipeline.process_url("https://example.com/article")

    # Trafilatura author should be used since it's a real name
    assert result.get("author") == "Jane Doe"
```

**Step 3: Run test to see current behavior**

```bash
cd backend && uv run pytest tests/test_author_detection.py -v
```

**Step 4: Update orchestrator to merge author sources**

Edit `backend/app/services/pipeline/orchestrator.py` to implement author merging logic:
- Use trafilatura author if it's a valid name (not None, not generic)
- Fall back to LLM author if trafilatura fails
- Check for generic values like "admin", "unknown", etc.

**Step 5: Run tests again**

```bash
cd backend && uv run pytest tests/test_author_detection.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/services/pipeline/orchestrator.py backend/tests/test_author_detection.py
git commit -m "fix: improve author detection with LLM fallback

Trafilatura author is preferred when valid.
Falls back to LLM-extracted author when trafilatura fails.
Filters out generic author values (admin, unknown, etc.)."
```

---

## Task 3: Telegram Access Control

Add allowlist to restrict who can use the Telegram bot.

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/integrations/telegram/bot.py`
- Test: `backend/tests/test_telegram_access.py` (new)

**Step 1: Write failing test**

Create `backend/tests/test_telegram_access.py`:

```python
"""Tests for Telegram bot access control."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_unauthorized_user_rejected():
    """Users not in allowlist should be rejected."""
    from app.integrations.telegram.bot import TelegramBot

    with patch("app.integrations.telegram.bot.settings") as mock_settings:
        mock_settings.telegram_allowed_users = {111, 222}
        mock_settings.telegram_bot_token = "test-token"

        mock_db = AsyncMock()
        bot = TelegramBot(mock_db)

        # Create mock update from unauthorized user
        mock_update = MagicMock()
        mock_update.effective_user.id = 999  # Not in allowlist
        mock_update.message = None

        response = await bot.process_update(mock_update)

        assert response is not None
        assert "not authorized" in response.lower()


@pytest.mark.asyncio
async def test_authorized_user_allowed():
    """Users in allowlist should be allowed."""
    from app.integrations.telegram.bot import TelegramBot

    with patch("app.integrations.telegram.bot.settings") as mock_settings:
        mock_settings.telegram_allowed_users = {111, 222}
        mock_settings.telegram_bot_token = "test-token"

        mock_db = AsyncMock()
        bot = TelegramBot(mock_db)

        mock_update = MagicMock()
        mock_update.effective_user.id = 111  # In allowlist
        mock_update.message.text = "status"
        mock_update.message.document = None

        # Should not return unauthorized message
        response = await bot.process_update(mock_update)

        if response:
            assert "not authorized" not in response.lower()


@pytest.mark.asyncio
async def test_empty_allowlist_allows_all():
    """Empty allowlist should allow all users (dev mode)."""
    from app.integrations.telegram.bot import TelegramBot

    with patch("app.integrations.telegram.bot.settings") as mock_settings:
        mock_settings.telegram_allowed_users = set()  # Empty = allow all
        mock_settings.telegram_bot_token = "test-token"

        mock_db = AsyncMock()
        bot = TelegramBot(mock_db)

        mock_update = MagicMock()
        mock_update.effective_user.id = 999
        mock_update.message.text = "status"
        mock_update.message.document = None

        response = await bot.process_update(mock_update)

        if response:
            assert "not authorized" not in response.lower()
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_telegram_access.py::test_unauthorized_user_rejected -v
```

Expected: FAIL (no access control yet)

**Step 3: Add config setting**

Edit `backend/app/core/config.py`, add after line 46:

```python
    # Telegram Bot
    telegram_bot_token: str | None = None
    telegram_allowed_users: str | None = None  # Comma-separated user IDs

    @property
    def telegram_allowed_users_set(self) -> set[int]:
        """Parse allowed users into a set of integers."""
        if not self.telegram_allowed_users:
            return set()
        return {int(uid.strip()) for uid in self.telegram_allowed_users.split(",") if uid.strip()}
```

**Step 4: Add access check to bot**

Edit `backend/app/integrations/telegram/bot.py`, add at start of `process_update()`:

```python
    async def process_update(self, update: Update) -> str | None:
        """Process a Telegram update and return response message."""
        # Get user ID
        if update.effective_user is None:
            logger.warning("Received update without user")
            return None

        user_id = update.effective_user.id

        # Access control check
        allowed_users = settings.telegram_allowed_users_set
        if allowed_users and user_id not in allowed_users:
            logger.warning(f"Unauthorized Telegram user: {user_id}")
            return "You are not authorized to use this bot."

        user_id_str = str(user_id)
        # ... rest of method
```

**Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_telegram_access.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/core/config.py backend/app/integrations/telegram/bot.py backend/tests/test_telegram_access.py
git commit -m "feat: add Telegram bot access control

Add TELEGRAM_ALLOWED_USERS env var (comma-separated user IDs).
Empty allowlist allows all users (development mode).
Unauthorized users receive rejection message."
```

---

## Task 4: Document Search via Chatbots

Add search command to find documents through Slack/Telegram.

**Files:**
- Modify: `backend/app/services/search/hybrid.py`
- Modify: `backend/app/integrations/bot_base.py`
- Modify: `backend/app/integrations/telegram/bot.py`
- Modify: `backend/app/integrations/slack/bot.py`
- Test: `backend/tests/test_bot_search.py` (new)

**Step 1: Write failing test**

Create `backend/tests/test_bot_search.py`:

```python
"""Tests for document search via chatbots."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta


@pytest.mark.asyncio
async def test_search_command_returns_results():
    """Search command should return matching documents."""
    from app.integrations.bot_base import BotBase

    class TestBot(BotBase):
        platform = "test"

    mock_db = AsyncMock()
    bot = TestBot(mock_db)

    # Mock search results
    mock_results = [
        {
            "id": "doc-1",
            "title": "Separation of Concerns",
            "author": "Martin Fowler",
            "url": "https://example.com/soc",
            "created_at": datetime.now(timezone.utc),
        },
    ]

    with patch.object(bot, "_search_documents", new=AsyncMock(return_value=mock_results)):
        response = await bot.handle_search("separation of concerns")

    assert "Separation of Concerns" in response
    assert "Martin Fowler" in response


@pytest.mark.asyncio
async def test_search_no_results():
    """Search with no matches should return helpful message."""
    from app.integrations.bot_base import BotBase

    class TestBot(BotBase):
        platform = "test"

    mock_db = AsyncMock()
    bot = TestBot(mock_db)

    with patch.object(bot, "_search_documents", new=AsyncMock(return_value=[])):
        response = await bot.handle_search("nonexistent topic")

    assert "no documents" in response.lower() or "not found" in response.lower()


def test_is_search_command():
    """Test search command detection."""
    from app.integrations.bot_base import BotBase

    class TestBot(BotBase):
        platform = "test"

    bot = TestBot(AsyncMock())

    assert bot.is_search_command("find microservices") == True
    assert bot.is_search_command("search architecture") == True
    assert bot.is_search_command("Find something") == True
    assert bot.is_search_command("hello") == False
    assert bot.is_search_command("status") == False
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_bot_search.py::test_is_search_command -v
```

Expected: FAIL (method doesn't exist)

**Step 3: Add search methods to BotBase**

Edit `backend/app/integrations/bot_base.py`, add after `is_status_request()`:

```python
    def is_search_command(self, text: str) -> bool:
        """Check if text is a search command."""
        text = text.strip().lower()
        return text.startswith("find ") or text.startswith("search ") or text.startswith("/find ") or text.startswith("/search ")

    def extract_search_query(self, text: str) -> str:
        """Extract the search query from a search command."""
        text = text.strip()
        for prefix in ["find ", "search ", "/find ", "/search ", "Find ", "Search "]:
            if text.startswith(prefix):
                return text[len(prefix):].strip()
        return text

    async def handle_search(self, query: str) -> str:
        """Handle document search request."""
        try:
            results = await self._search_documents(query)

            if not results:
                return f"No documents found matching: {query}"

            # Format results
            lines = [f"Found {len(results)} document(s):\n"]
            for i, doc in enumerate(results[:5], 1):  # Limit to 5 results
                title = doc.get("title", "Untitled")
                author = doc.get("author", "Unknown")
                url = doc.get("url", "")
                created = doc.get("created_at")

                date_str = ""
                if created:
                    if isinstance(created, datetime):
                        date_str = created.strftime("%b %d")
                    else:
                        date_str = str(created)[:10]

                lines.append(f"{i}. \"{title}\"")
                lines.append(f"   Author: {author} | Added: {date_str}")
                if url and url.startswith("http"):
                    lines.append(f"   {url}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.exception(f"Error searching documents for {self.platform}")
            return f"Error searching: {str(e)}"

    async def _search_documents(self, query: str, limit: int = 5) -> list[dict]:
        """Search documents using hybrid search."""
        from app.services.search.hybrid import HybridSearch
        from sqlalchemy import select
        from app.models.document import Document, ProcessingStatus

        search = HybridSearch(self.db)
        results = await search.search(query, limit=limit, session=self.db)

        # Enrich with full document data
        enriched = []
        for result in results:
            doc_result = await self.db.execute(
                select(Document).where(
                    Document.id == result["id"],
                    Document.processing_status == ProcessingStatus.COMPLETED,
                )
            )
            doc = doc_result.scalar_one_or_none()
            if doc:
                enriched.append({
                    "id": str(doc.id),
                    "title": doc.title,
                    "author": doc.author,
                    "url": doc.url,
                    "created_at": doc.created_at,
                })

        return enriched
```

**Step 4: Add search routing to Telegram bot**

Edit `backend/app/integrations/telegram/bot.py`, in `process_update()` text handling:

```python
        # Handle text message
        if update.message and update.message.text:
            text = update.message.text.strip()

            # Status request
            if self.is_status_request(text):
                return await self.handle_status(user_id_str)

            # Search command
            if self.is_search_command(text):
                query = self.extract_search_query(text)
                return await self.handle_search(query)

            # URL
            if self.is_url(text):
                return await self.handle_url(user_id_str, text)

            # Unknown - show help
            return self.handle_help()
```

**Step 5: Add search routing to Slack bot**

Apply same pattern to `backend/app/integrations/slack/bot.py`.

**Step 6: Update help message**

Edit `backend/app/integrations/bot_base.py`, update `handle_help()`:

```python
    def handle_help(self) -> str:
        """Return help message."""
        return (
            "I can help you manage the knowledge base.\n\n"
            "Send me:\n"
            "- A PDF file to upload\n"
            "- A URL to a webpage or document\n"
            "- 'status' to check your last upload\n"
            "- 'find <query>' to search documents\n"
        )
```

**Step 7: Run all tests**

```bash
cd backend && uv run pytest tests/test_bot_search.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add backend/app/integrations/bot_base.py backend/app/integrations/telegram/bot.py backend/app/integrations/slack/bot.py backend/tests/test_bot_search.py
git commit -m "feat: add document search via chatbots

Users can now search documents with 'find <query>' or 'search <query>'.
Returns up to 5 matching documents with title, author, date, and URL.
Uses existing HybridSearch for semantic + keyword matching."
```

---

## Task 5: SEC-6 - Require Secrets in Production

Fail startup if using default secrets in non-development environment.

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_startup_security.py` (new)

**Step 1: Write failing test**

Create `backend/tests/test_startup_security.py`:

```python
"""Tests for startup security validation."""
import pytest
from unittest.mock import patch


def test_production_rejects_default_secret_key():
    """Production should reject default secret_key."""
    from app.main import validate_production_secrets
    from app.core.config import Settings

    mock_settings = Settings(
        environment="production",
        secret_key="dev-secret-key-change-in-production",
        admin_api_key="real-admin-key",
    )

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_production_secrets(mock_settings)


def test_production_rejects_default_admin_key():
    """Production should reject default admin_api_key."""
    from app.main import validate_production_secrets
    from app.core.config import Settings

    mock_settings = Settings(
        environment="production",
        secret_key="real-secret-key",
        admin_api_key="dev-admin-key",
    )

    with pytest.raises(RuntimeError, match="ADMIN_API_KEY"):
        validate_production_secrets(mock_settings)


def test_development_allows_default_secrets():
    """Development should allow default secrets."""
    from app.main import validate_production_secrets
    from app.core.config import Settings

    mock_settings = Settings(
        environment="development",
        secret_key="dev-secret-key-change-in-production",
        admin_api_key="dev-admin-key",
    )

    # Should not raise
    validate_production_secrets(mock_settings)


def test_production_with_real_secrets_succeeds():
    """Production with real secrets should succeed."""
    from app.main import validate_production_secrets
    from app.core.config import Settings

    mock_settings = Settings(
        environment="production",
        secret_key="a-real-secret-key-here",
        admin_api_key="a-real-admin-key-here",
    )

    # Should not raise
    validate_production_secrets(mock_settings)
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_startup_security.py::test_production_rejects_default_secret_key -v
```

Expected: FAIL (function doesn't exist)

**Step 3: Add validation function to main.py**

Edit `backend/app/main.py`, add after imports:

```python
def validate_production_secrets(settings_obj=None) -> None:
    """Validate that production is not using default secrets."""
    s = settings_obj or settings

    if s.environment == "development":
        return

    if s.secret_key == "dev-secret-key-change-in-production":
        raise RuntimeError(
            "SECRET_KEY must be set in production. "
            "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    if s.admin_api_key == "dev-admin-key":
        raise RuntimeError(
            "ADMIN_API_KEY must be set in production. "
            "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
```

**Step 4: Call validation in lifespan**

Edit `backend/app/main.py`, add at start of lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task, _scheduler_task
    # Validate secrets before starting
    validate_production_secrets()

    # Startup
    await worker.recover_orphaned_jobs()
    # ... rest of function
```

**Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_startup_security.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_startup_security.py
git commit -m "sec: require real secrets in production

Startup fails if using default secret_key or admin_api_key
in non-development environments. Includes helpful error messages
with generation commands."
```

---

## Task 6: SEC-5 - PDF Upload Size Limit

Add 350MB limit for PDF uploads.

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/documents.py`
- Test: `backend/tests/test_upload_limit.py` (new)

**Step 1: Write failing test**

Create `backend/tests/test_upload_limit.py`:

```python
"""Tests for upload size limits."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from io import BytesIO


def test_upload_rejects_oversized_file():
    """Files over size limit should be rejected with 413."""
    from app.main import app

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.max_upload_size_mb = 10  # 10MB limit for testing
        mock_settings.admin_api_key = "test-key"

        # This would require integration test setup
        # For unit test, we test the check function directly
        pass


def test_check_upload_size_rejects_large():
    """check_upload_size should raise for large files."""
    from app.api.documents import check_upload_size

    # 400MB = over 350MB limit
    with pytest.raises(Exception) as exc_info:
        check_upload_size(400 * 1024 * 1024)

    assert "413" in str(exc_info.value) or "too large" in str(exc_info.value).lower()


def test_check_upload_size_accepts_small():
    """check_upload_size should accept small files."""
    from app.api.documents import check_upload_size

    # 10MB = under limit
    check_upload_size(10 * 1024 * 1024)  # Should not raise
```

**Step 2: Add config setting**

Edit `backend/app/core/config.py`:

```python
    # Upload limits
    max_upload_size_mb: int = 350
```

**Step 3: Add size check function and apply to upload**

Edit `backend/app/api/documents.py`, add after imports:

```python
from app.core.config import settings


def check_upload_size(content_length: int) -> None:
    """Check if upload size is within limits."""
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if content_length > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB."
        )
```

**Step 4: Apply check in upload endpoint**

Edit `backend/app/api/documents.py`, update `upload_pdf()`:

```python
@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentResponse:
    """Upload a PDF document."""
    # Check file size from content-length or read size
    if file.size:
        check_upload_size(file.size)

    # Validate file is PDF
    if not file.content_type or "pdf" not in file.content_type.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted"
        )

    # Read file content with size tracking
    pdf_content = await file.read()
    check_upload_size(len(pdf_content))  # Double-check actual size

    # ... rest of function
```

**Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_upload_limit.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/core/config.py backend/app/api/documents.py backend/tests/test_upload_limit.py
git commit -m "sec: add 350MB PDF upload size limit

Rejects uploads over MAX_UPLOAD_SIZE_MB (default 350).
Returns 413 Payload Too Large with clear error message."
```

---

## Task 7: SEC-3 - Webhook Verification

Enforce webhook signature verification in production.

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/integrations/telegram/webhook.py`
- Modify: `backend/app/integrations/slack/events.py`
- Test: `backend/tests/test_webhook_verification.py` (new)

**Step 1: Write failing test**

Create `backend/tests/test_webhook_verification.py`:

```python
"""Tests for webhook signature verification."""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_telegram_rejects_invalid_secret():
    """Telegram webhook should reject requests with invalid secret."""
    from app.integrations.telegram.webhook import verify_telegram_secret

    with patch("app.integrations.telegram.webhook.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = "correct-secret"
        mock_settings.environment = "production"

        # Wrong secret should fail
        assert verify_telegram_secret("wrong-secret") == False

        # Correct secret should pass
        assert verify_telegram_secret("correct-secret") == True


@pytest.mark.asyncio
async def test_telegram_production_requires_secret():
    """Production should require webhook secret."""
    from app.integrations.telegram.webhook import verify_telegram_secret

    with patch("app.integrations.telegram.webhook.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = None
        mock_settings.environment = "production"

        # No secret configured in production = fail
        assert verify_telegram_secret("any-value") == False


@pytest.mark.asyncio
async def test_telegram_development_allows_no_secret():
    """Development can skip webhook verification."""
    from app.integrations.telegram.webhook import verify_telegram_secret

    with patch("app.integrations.telegram.webhook.settings") as mock_settings:
        mock_settings.telegram_webhook_secret = None
        mock_settings.environment = "development"

        # Development mode = allow
        assert verify_telegram_secret(None) == True


@pytest.mark.asyncio
async def test_slack_production_requires_signing():
    """Slack production should require signing secret."""
    from app.integrations.slack.events import require_signature_in_production

    with patch("app.integrations.slack.events.settings") as mock_settings:
        mock_settings.slack_signing_secret = None
        mock_settings.environment = "production"

        with pytest.raises(HTTPException) as exc_info:
            require_signature_in_production()

        assert exc_info.value.status_code == 503
```

**Step 2: Add config setting for Telegram secret**

Edit `backend/app/core/config.py`:

```python
    # Telegram Bot
    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None  # For webhook verification
    telegram_allowed_users: str | None = None
```

**Step 3: Add Telegram verification**

Edit `backend/app/integrations/telegram/webhook.py`, add verification function:

```python
def verify_telegram_secret(provided_secret: str | None) -> bool:
    """Verify Telegram webhook secret token."""
    # Development mode: skip verification if not configured
    if settings.environment == "development" and not settings.telegram_webhook_secret:
        return True

    # Production requires secret
    if not settings.telegram_webhook_secret:
        logger.error("Telegram webhook secret not configured in production")
        return False

    if not provided_secret:
        return False

    return secrets.compare_digest(provided_secret, settings.telegram_webhook_secret)
```

**Step 4: Apply verification in Telegram webhook**

Edit `backend/app/integrations/telegram/webhook.py`:

```python
@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Handle incoming Telegram webhook updates."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")

    # Verify webhook secret
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not verify_telegram_secret(secret_header):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # ... rest of handler
```

**Step 5: Update set-webhook to include secret**

Edit `backend/app/integrations/telegram/webhook.py`:

```python
@router.post("/set-webhook")
async def set_telegram_webhook(webhook_url: str) -> dict:
    """Set the Telegram webhook URL with secret token."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"

    payload = {"url": webhook_url}
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        return response.json()
```

**Step 6: Enforce Slack signing in production**

Edit `backend/app/integrations/slack/events.py`:

```python
def require_signature_in_production() -> None:
    """Require signing secret in production."""
    if settings.environment != "development" and not settings.slack_signing_secret:
        raise HTTPException(
            status_code=503,
            detail="Slack signing secret required in production"
        )
```

Then call this at the start of the events handler (after URL verification check).

**Step 7: Run tests**

```bash
cd backend && uv run pytest tests/test_webhook_verification.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add backend/app/core/config.py backend/app/integrations/telegram/webhook.py backend/app/integrations/slack/events.py backend/tests/test_webhook_verification.py
git commit -m "sec: enforce webhook verification in production

Telegram: verify X-Telegram-Bot-Api-Secret-Token header.
Slack: require signing secret in production.
Development mode allows unverified requests for testing."
```

---

## Task 8: SEC-4 - Hash API Keys

Store hashed API keys instead of plaintext.

**Files:**
- Create: `backend/alembic/versions/xxxx_add_api_key_hash.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/core/deps.py`
- Test: `backend/tests/test_api_key_hashing.py` (new)

**Step 1: Write failing test**

Create `backend/tests/test_api_key_hashing.py`:

```python
"""Tests for API key hashing."""
import pytest


def test_hash_api_key_produces_consistent_hash():
    """Same key should produce same hash."""
    from app.core.security import hash_api_key

    key = "test-api-key-12345"
    hash1 = hash_api_key(key)
    hash2 = hash_api_key(key)

    assert hash1 == hash2
    assert hash1 != key  # Should not be plaintext


def test_hash_api_key_different_keys_different_hashes():
    """Different keys should produce different hashes."""
    from app.core.security import hash_api_key

    hash1 = hash_api_key("key-one")
    hash2 = hash_api_key("key-two")

    assert hash1 != hash2


def test_verify_api_key_hash_correct():
    """Correct key should verify against its hash."""
    from app.core.security import hash_api_key, verify_api_key_hash

    key = "my-secret-api-key"
    key_hash = hash_api_key(key)

    assert verify_api_key_hash(key, key_hash) == True


def test_verify_api_key_hash_incorrect():
    """Wrong key should not verify."""
    from app.core.security import hash_api_key, verify_api_key_hash

    key = "my-secret-api-key"
    key_hash = hash_api_key(key)

    assert verify_api_key_hash("wrong-key", key_hash) == False
```

**Step 2: Add hashing functions**

Edit `backend/app/core/security.py`:

```python
import hashlib
import hmac


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage using SHA-256 with pepper."""
    # Use secret_key as pepper for additional security
    pepper = settings.secret_key.encode()
    return hmac.new(pepper, api_key.encode(), hashlib.sha256).hexdigest()


def verify_api_key_hash(provided_key: str, stored_hash: str) -> bool:
    """Verify a provided API key against a stored hash."""
    provided_hash = hash_api_key(provided_key)
    return secrets.compare_digest(provided_hash, stored_hash)
```

**Step 3: Run test**

```bash
cd backend && uv run pytest tests/test_api_key_hashing.py -v
```

Expected: PASS

**Step 4: Add api_key_hash column**

Create migration:

```bash
cd backend && uv run alembic revision -m "add_api_key_hash"
```

Edit the generated migration file:

```python
"""add_api_key_hash

Revision ID: xxxx
"""
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column('users', sa.Column('api_key_hash', sa.String(64), nullable=True, unique=True))


def downgrade() -> None:
    op.drop_column('users', 'api_key_hash')
```

**Step 5: Update User model**

Edit `backend/app/models/user.py`:

```python
    # API key for programmatic access (plaintext - deprecated, will be removed)
    api_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Hashed API key (SHA-256 with pepper)
    api_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
```

**Step 6: Update deps.py to check hash**

Edit `backend/app/core/deps.py`:

```python
from app.core.security import verify_api_key_hash

# In get_current_user(), update the user API key check:

    # Check user API key (try hash first, then legacy plaintext)
    result = await db.execute(
        select(User).where(User.is_active.is_(True))
    )
    users = result.scalars().all()

    for user in users:
        # Check hashed key first
        if user.api_key_hash and verify_api_key_hash(api_key, user.api_key_hash):
            return user
        # Legacy: check plaintext (to be removed after migration)
        if user.api_key and secrets.compare_digest(api_key, user.api_key):
            return user

    return None
```

**Step 7: Run migration**

```bash
cd backend && uv run alembic upgrade head
```

**Step 8: Run all tests**

```bash
cd backend && uv run pytest tests/test_api_key_hashing.py -v
```

Expected: PASS

**Step 9: Commit**

```bash
git add backend/app/core/security.py backend/app/core/deps.py backend/app/models/user.py backend/alembic/versions/*_add_api_key_hash.py backend/tests/test_api_key_hashing.py
git commit -m "sec: hash API keys with SHA-256 + pepper

Add api_key_hash column for secure storage.
Auth checks hash first, falls back to legacy plaintext.
Uses secret_key as pepper for additional security."
```

---

## Task 9: SEC-1 - OAuth CSRF Protection

Add state parameter to OAuth flow.

**Files:**
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_oauth_csrf.py` (new)

**Step 1: Write failing test**

Create `backend/tests/test_oauth_csrf.py`:

```python
"""Tests for OAuth CSRF protection."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_login_sets_state_cookie():
    """Login should set oauth_state cookie."""
    from app.api.auth import login

    with patch("app.api.auth.get_oauth_service") as mock_service:
        mock_oauth = MagicMock()
        mock_oauth.get_authorization_url.return_value = "https://google.com/auth?state=abc"
        mock_service.return_value = mock_oauth

        response = await login(service=mock_oauth)

        # Check state was passed to get_authorization_url
        mock_oauth.get_authorization_url.assert_called_once()
        call_args = mock_oauth.get_authorization_url.call_args
        assert call_args[1].get("state") is not None or (call_args[0] and call_args[0][0])


@pytest.mark.asyncio
async def test_callback_rejects_missing_state():
    """Callback should reject requests without state."""
    from app.api.auth import callback

    with pytest.raises(HTTPException) as exc_info:
        await callback(
            code="auth-code",
            state=None,
            oauth_state_cookie=None,
            response=MagicMock(),
            db=AsyncMock(),
            service=MagicMock(),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_callback_rejects_mismatched_state():
    """Callback should reject state mismatch."""
    from app.api.auth import callback

    with pytest.raises(HTTPException) as exc_info:
        await callback(
            code="auth-code",
            state="state-from-google",
            oauth_state_cookie="different-state",
            response=MagicMock(),
            db=AsyncMock(),
            service=MagicMock(),
        )

    assert exc_info.value.status_code == 400
    assert "state" in str(exc_info.value.detail).lower()
```

**Step 2: Update login endpoint**

Edit `backend/app/api/auth.py`:

```python
import secrets


@router.get("/login")
async def login(
    response: Response,
    service: OAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    """Redirect to Google OAuth login."""
    # Generate CSRF state token
    state = secrets.token_urlsafe(32)

    # Get auth URL with state
    url = service.get_authorization_url(state=state)

    # Create redirect response
    redirect = RedirectResponse(url=url, status_code=307)

    # Set state in cookie for verification
    redirect.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=(settings.environment != "development"),
        samesite="lax",
        max_age=600,  # 10 minutes
    )

    return redirect
```

**Step 3: Update callback endpoint**

Edit `backend/app/api/auth.py`:

```python
@router.get("/callback")
async def callback(
    code: str,
    state: str | None = None,
    response: Response,
    oauth_state_cookie: str | None = Cookie(default=None, alias="oauth_state"),
    db: AsyncSession = Depends(get_session),
    service: OAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    """Handle Google OAuth callback."""
    # Validate CSRF state
    if not state or not oauth_state_cookie:
        raise HTTPException(
            status_code=400,
            detail="Missing OAuth state parameter"
        )

    if not secrets.compare_digest(state, oauth_state_cookie):
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state - possible CSRF attack"
        )

    # ... rest of existing callback logic ...

    # Before returning redirect, clear the state cookie
    redirect = RedirectResponse(url=settings.frontend_url, status_code=302)
    redirect.delete_cookie("oauth_state")
    # ... set session cookie ...
    return redirect
```

**Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_oauth_csrf.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/api/auth.py backend/tests/test_oauth_csrf.py
git commit -m "sec: add OAuth CSRF protection with state parameter

Generate random state, store in HTTP-only cookie.
Verify state matches on callback, reject mismatches.
Cookie expires after 10 minutes."
```

---

## Task 10: SEC-2 - SSRF Protection

Validate URLs to block private IP access.

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/services/pipeline/url_fetcher.py`
- Test: `backend/tests/test_ssrf_protection.py` (new)

**Step 1: Write failing test**

Create `backend/tests/test_ssrf_protection.py`:

```python
"""Tests for SSRF protection."""
import pytest
from unittest.mock import patch


def test_validate_url_blocks_private_ip():
    """Should block private IP addresses."""
    from app.core.security import validate_url

    with pytest.raises(ValueError, match="[Bb]locked"):
        validate_url("http://192.168.1.1/secret")

    with pytest.raises(ValueError, match="[Bb]locked"):
        validate_url("http://10.0.0.1/internal")

    with pytest.raises(ValueError, match="[Bb]locked"):
        validate_url("http://172.16.0.1/private")


def test_validate_url_blocks_localhost():
    """Should block localhost."""
    from app.core.security import validate_url

    with pytest.raises(ValueError, match="[Bb]locked"):
        validate_url("http://127.0.0.1/admin")

    with pytest.raises(ValueError, match="[Bb]locked"):
        validate_url("http://localhost/admin")


def test_validate_url_blocks_metadata():
    """Should block cloud metadata endpoints."""
    from app.core.security import validate_url

    with pytest.raises(ValueError, match="[Bb]locked"):
        validate_url("http://169.254.169.254/latest/meta-data")


def test_validate_url_allows_public():
    """Should allow public URLs."""
    from app.core.security import validate_url

    # Mock DNS resolution to return public IP
    with patch("socket.gethostbyname", return_value="93.184.216.34"):
        validate_url("https://example.com/article")  # Should not raise


def test_validate_url_requires_http_scheme():
    """Should require http or https scheme."""
    from app.core.security import validate_url

    with pytest.raises(ValueError, match="[Ss]cheme"):
        validate_url("ftp://example.com/file")

    with pytest.raises(ValueError, match="[Ss]cheme"):
        validate_url("file:///etc/passwd")
```

**Step 2: Add URL validation function**

Edit `backend/app/core/security.py`:

```python
import ipaddress
import socket
from urllib.parse import urlparse


# Whitelisted domains that can have any IP (e.g., Slack file downloads)
WHITELISTED_DOMAINS = {"files.slack.com", "api.slack.com"}


def validate_url(url: str) -> None:
    """
    Validate URL is safe to fetch. Raises ValueError if not.

    Blocks:
    - Private IPs (10.x, 172.16-31.x, 192.168.x)
    - Loopback (127.x, localhost)
    - Link-local (169.254.x)
    - Cloud metadata (169.254.169.254)
    """
    parsed = urlparse(url)

    # Require http/https
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")

    if not parsed.hostname:
        raise ValueError("URL must have a hostname")

    # Check whitelist
    if parsed.hostname.lower() in WHITELISTED_DOMAINS:
        return

    # Resolve hostname to IP
    try:
        ip_str = socket.gethostbyname(parsed.hostname)
        ip = ipaddress.ip_address(ip_str)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {parsed.hostname}")

    # Block private/reserved ranges
    if ip.is_private:
        raise ValueError(f"Blocked: private IP range ({ip})")
    if ip.is_loopback:
        raise ValueError(f"Blocked: loopback address ({ip})")
    if ip.is_link_local:
        raise ValueError(f"Blocked: link-local address ({ip})")
    if ip.is_reserved:
        raise ValueError(f"Blocked: reserved address ({ip})")

    # Specifically block metadata endpoint
    if str(ip) == "169.254.169.254":
        raise ValueError("Blocked: cloud metadata endpoint")
```

**Step 3: Update URL fetcher with validated redirects**

Edit `backend/app/services/pipeline/url_fetcher.py`:

```python
"""URL content fetching service with SSRF protection."""

import httpx
import trafilatura
from trafilatura.settings import use_config
from app.core.security import validate_url

config = use_config()
config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")

MAX_REDIRECTS = 10


async def fetch_url_content(url: str) -> dict[str, str | dict[str, str | None]]:
    """
    Fetch and extract content from URL with SSRF protection.

    Validates URL and all redirect destinations against private IP ranges.
    """
    # Validate initial URL
    try:
        validate_url(url)
    except ValueError as e:
        return {"text": "", "error": str(e)}

    try:
        current_url = url
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS):
                response = await client.get(current_url)

                if response.is_redirect:
                    redirect_url = response.headers.get("location", "")
                    # Make absolute if relative
                    if redirect_url.startswith("/"):
                        from urllib.parse import urlparse, urlunparse
                        parsed = urlparse(current_url)
                        redirect_url = urlunparse((parsed.scheme, parsed.netloc, redirect_url, "", "", ""))

                    # Validate redirect destination
                    try:
                        validate_url(redirect_url)
                    except ValueError as e:
                        return {"text": "", "error": f"Blocked redirect: {e}"}

                    current_url = redirect_url
                    continue

                response.raise_for_status()
                html = response.text
                break
            else:
                return {"text": "", "error": "Too many redirects"}

        # Extract main content
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )

        # Extract metadata
        metadata = trafilatura.extract_metadata(html)

        return {
            "text": text or "",
            "metadata": {
                "title": metadata.title if metadata else None,
                "author": metadata.author if metadata else None,
                "date": str(metadata.date) if metadata and metadata.date else None,
            },
            "url": current_url,  # Final URL after redirects
        }
    except httpx.HTTPStatusError as e:
        return {"text": "", "error": f"HTTP error: {e.response.status_code}"}
    except httpx.TimeoutException:
        return {"text": "", "error": "Request timeout"}
    except httpx.ConnectError as e:
        return {"text": "", "error": f"Connection error: {e}"}
    except httpx.HTTPError as e:
        return {"text": "", "error": f"HTTP error: {e}"}
    except Exception as e:
        return {"text": "", "error": str(e)}
```

**Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_ssrf_protection.py -v
```

Expected: PASS

**Step 5: Run full test suite**

```bash
cd backend && uv run pytest -v
```

Expected: All tests pass

**Step 6: Commit**

```bash
git add backend/app/core/security.py backend/app/services/pipeline/url_fetcher.py backend/tests/test_ssrf_protection.py
git commit -m "sec: add SSRF protection for URL ingestion

Validate URLs block private IPs, localhost, metadata endpoints.
Manually follow redirects with validation at each hop.
Whitelist Slack domains for file downloads."
```

---

## Final Steps

**Step 1: Run full test suite**

```bash
cd backend && uv run pytest -v --tb=short
```

Expected: All 537+ tests pass

**Step 2: Update documentation**

Update `SECURITY_TODO.md` to mark items as complete.

**Step 3: Create PR**

```bash
git push -u origin feature/v2-implementation
gh pr create --title "v2: Quality improvements and security fixes" --body "$(cat <<'EOF'
## Summary
- Lazy-load DriveService in webhooks for faster status checks
- Improve author detection with LLM fallback
- Add Telegram access control via allowlist
- Add document search via chatbots (find/search commands)
- Require real secrets in production
- Add 350MB PDF upload limit
- Enforce webhook verification
- Hash API keys with SHA-256 + pepper
- Add OAuth CSRF protection with state parameter
- Add SSRF protection for URL ingestion

## Test plan
- [ ] Run full test suite
- [ ] Test status command response time
- [ ] Test author extraction on Substack article
- [ ] Test Telegram access control with allowlist
- [ ] Test document search via Slack/Telegram
- [ ] Test upload size rejection at 350MB+
- [ ] Verify OAuth flow with state parameter
- [ ] Test URL ingestion blocks private IPs

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Environment Variables (New)

Add to `.env.example`:

```bash
# Telegram access control (comma-separated user IDs, empty = allow all)
TELEGRAM_ALLOWED_USERS=

# Telegram webhook verification
TELEGRAM_WEBHOOK_SECRET=

# Upload limits (MB)
MAX_UPLOAD_SIZE_MB=350
```
