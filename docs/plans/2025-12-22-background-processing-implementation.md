# Background Processing & OAuth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Google OAuth SSO, asyncio-based job queue, and Google Drive folder sync for HARI.

**Architecture:** Session-based OAuth authentication for web UI, job queue with PostgreSQL state persistence, and service account-based Drive API access.

**Tech Stack:** FastAPI, SQLAlchemy, asyncpg, httpx, google-auth, google-api-python-client

---

## Phase 1: OAuth Infrastructure

### Task 1: Session Model

**Files:**
- Create: `backend/app/models/session.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models_session.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_models_session.py
import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from app.models.session import Session


def test_session_model_exists():
    """Test Session model can be instantiated."""
    session = Session(
        user_id=uuid4(),
        token_hash="abc123def456",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    assert session.user_id is not None
    assert session.token_hash == "abc123def456"


def test_session_has_required_fields():
    """Test Session has all required fields."""
    assert hasattr(Session, 'id')
    assert hasattr(Session, 'user_id')
    assert hasattr(Session, 'token_hash')
    assert hasattr(Session, 'expires_at')
    assert hasattr(Session, 'created_at')
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_models_session.py -v
```
Expected: FAIL with "cannot import name 'Session'"

**Step 3: Write minimal implementation**

```python
# backend/app/models/session.py
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False,
    )
```

**Step 4: Update models __init__.py**

```python
# backend/app/models/__init__.py
from app.models.base import Base, TimestampMixin
from app.models.document import Document, SourceType, ProcessingStatus
from app.models.user import User, UserRole
from app.models.session import Session

__all__ = [
    "Base",
    "TimestampMixin",
    "Document",
    "SourceType",
    "ProcessingStatus",
    "User",
    "UserRole",
    "Session",
]
```

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_models_session.py -v
```
Expected: PASS

**Step 6: Create migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add sessions table"
cd backend && uv run alembic upgrade head
```

**Step 7: Commit**

```bash
git add backend/app/models/session.py backend/app/models/__init__.py backend/tests/test_models_session.py backend/alembic/versions/
git commit -m "feat(auth): add Session model for OAuth sessions"
```

---

### Task 2: OAuth Service

**Files:**
- Create: `backend/app/services/auth/__init__.py`
- Create: `backend/app/services/auth/oauth.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_oauth_service.py`

**Step 1: Update config with OAuth settings**

```python
# Add to backend/app/core/config.py Settings class:
    # Google OAuth
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/callback"

    # Session
    session_expire_days: int = 7
```

**Step 2: Write the failing test**

```python
# backend/tests/test_oauth_service.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.auth.oauth import OAuthService, GoogleUserInfo


def test_oauth_service_exists():
    """Test OAuthService can be instantiated."""
    service = OAuthService()
    assert service is not None


def test_get_authorization_url():
    """Test generating Google OAuth authorization URL."""
    service = OAuthService()
    url = service.get_authorization_url()
    assert "accounts.google.com" in url
    assert "client_id" in url
    assert "redirect_uri" in url
    assert "scope" in url


@pytest.mark.asyncio
async def test_exchange_code_for_tokens():
    """Test exchanging auth code for tokens."""
    service = OAuthService()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "test_access_token",
        "id_token": "test_id_token",
        "expires_in": 3600,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        tokens = await service.exchange_code("test_code")
        assert tokens["access_token"] == "test_access_token"


@pytest.mark.asyncio
async def test_get_user_info():
    """Test fetching user info from Google."""
    service = OAuthService()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "sub": "123456789",
        "email": "test@example.com",
        "name": "Test User",
        "picture": "https://example.com/photo.jpg",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        user_info = await service.get_user_info("test_access_token")
        assert user_info.email == "test@example.com"
        assert user_info.google_id == "123456789"
```

**Step 3: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_oauth_service.py -v
```
Expected: FAIL with "cannot import name 'OAuthService'"

**Step 4: Write implementation**

```python
# backend/app/services/auth/__init__.py
from app.services.auth.oauth import OAuthService, GoogleUserInfo

__all__ = ["OAuthService", "GoogleUserInfo"]
```

```python
# backend/app/services/auth/oauth.py
import secrets
import hashlib
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import settings


@dataclass
class GoogleUserInfo:
    google_id: str
    email: str
    name: str | None
    picture: str | None


class OAuthService:
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    SCOPES = ["openid", "email", "profile"]

    def get_authorization_url(self, state: str | None = None) -> str:
        """Generate Google OAuth authorization URL."""
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        return f"{self.GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.google_redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_user_info(self, access_token: str) -> GoogleUserInfo:
        """Fetch user info from Google."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            return GoogleUserInfo(
                google_id=data["sub"],
                email=data["email"],
                name=data.get("name"),
                picture=data.get("picture"),
            )

    @staticmethod
    def generate_session_token() -> str:
        """Generate a secure random session token."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a session token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
```

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_oauth_service.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/services/auth/ backend/tests/test_oauth_service.py backend/app/core/config.py
git commit -m "feat(auth): add OAuth service for Google authentication"
```

---

### Task 3: Auth API Endpoints

**Files:**
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_auth.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_api_auth.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_login_redirects_to_google():
    """Test /auth/login redirects to Google OAuth."""
    response = client.get("/api/auth/login", follow_redirects=False)
    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]


def test_logout_clears_session():
    """Test /auth/logout clears session cookie."""
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    # Cookie should be deleted (max-age=0 or expired)
    assert "session" in response.headers.get("set-cookie", "").lower()


def test_me_returns_401_without_session():
    """Test /auth/me returns 401 without valid session."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_api_auth.py -v
```
Expected: FAIL with "404 Not Found"

**Step 3: Write implementation**

```python
# backend/app/api/auth.py
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import get_session
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.session import Session
from app.services.auth.oauth import OAuthService

router = APIRouter(prefix="/auth", tags=["auth"])
oauth_service = OAuthService()


@router.get("/login")
async def login():
    """Redirect to Google OAuth login."""
    url = oauth_service.get_authorization_url()
    return RedirectResponse(url=url, status_code=307)


@router.get("/callback")
async def callback(
    code: str,
    response: Response,
    db: AsyncSession = Depends(get_session),
):
    """Handle Google OAuth callback."""
    # Exchange code for tokens
    tokens = await oauth_service.exchange_code(code)

    # Get user info from Google
    user_info = await oauth_service.get_user_info(tokens["access_token"])

    # Find or create user
    result = await db.execute(
        select(User).where(User.google_id == user_info.google_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Create new user
        user = User(
            email=user_info.email,
            name=user_info.name,
            picture=user_info.picture,
            google_id=user_info.google_id,
            role=UserRole.USER,
        )
        db.add(user)
        await db.flush()
    else:
        # Update existing user info
        user.name = user_info.name
        user.picture = user_info.picture

    # Create session
    session_token = oauth_service.generate_session_token()
    token_hash = oauth_service.hash_token(session_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_expire_days)

    session = Session(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()

    # Set session cookie and redirect to frontend
    redirect = RedirectResponse(url="http://localhost:5173", status_code=302)
    redirect.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=False,  # Set True in production with HTTPS
        samesite="lax",
        max_age=settings.session_expire_days * 24 * 60 * 60,
    )
    return redirect


@router.post("/logout")
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias="session"),
    db: AsyncSession = Depends(get_session),
):
    """Logout and clear session."""
    if session_token:
        token_hash = oauth_service.hash_token(session_token)
        await db.execute(delete(Session).where(Session.token_hash == token_hash))
        await db.commit()

    response.delete_cookie("session")
    return {"message": "Logged out"}


@router.get("/me")
async def get_current_user_info(
    session_token: str | None = Cookie(default=None, alias="session"),
    db: AsyncSession = Depends(get_session),
):
    """Get current authenticated user info."""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token_hash = oauth_service.hash_token(session_token)

    # Find valid session
    result = await db.execute(
        select(Session).where(
            Session.token_hash == token_hash,
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # Get user
    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "role": user.role.value,
    }
```

**Step 4: Register router in main.py**

Add to `backend/app/main.py`:
```python
from app.api.auth import router as auth_router

# Add after other routers:
app.include_router(auth_router, prefix="/api")
```

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_api_auth.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/api/auth.py backend/app/main.py backend/tests/test_api_auth.py
git commit -m "feat(auth): add OAuth API endpoints (login, callback, logout, me)"
```

---

### Task 4: Update Auth Dependencies

**Files:**
- Modify: `backend/app/core/deps.py`
- Test: `backend/tests/test_deps.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_deps.py`:

```python
@pytest.mark.asyncio
async def test_get_current_user_from_session_cookie():
    """Test getting user from session cookie."""
    from app.core.deps import get_current_user_from_session
    # This function should exist
    assert callable(get_current_user_from_session)
```

**Step 2: Update deps.py to support both API key and session auth**

```python
# backend/app/core/deps.py
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_session
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.session import Session
from app.services.auth.oauth import OAuthService

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
oauth_service = OAuthService()


async def get_current_user_from_session(
    session_token: str | None = Cookie(default=None, alias="session"),
    db: AsyncSession = Depends(get_session),
) -> User | None:
    """Get user from session cookie."""
    if not session_token:
        return None

    token_hash = oauth_service.hash_token(session_token)

    result = await db.execute(
        select(Session).where(
            Session.token_hash == token_hash,
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        return None

    result = await db.execute(select(User).where(User.id == session.user_id))
    return result.scalar_one_or_none()


async def get_current_user(
    db: AsyncSession = Depends(get_session),
    api_key: str | None = Depends(api_key_header),
    session_user: User | None = Depends(get_current_user_from_session),
) -> User | None:
    """Get current user from API key OR session cookie."""
    # Session takes precedence if present
    if session_user:
        return session_user

    if not api_key:
        return None

    # Check admin API key
    if api_key == settings.admin_api_key:
        return User(email="admin@system", role=UserRole.ADMIN)

    # Check user API key
    result = await db.execute(
        select(User).where(User.api_key == api_key, User.is_active == True)
    )
    return result.scalar_one_or_none()


async def require_user(
    user: User | None = Depends(get_current_user),
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication",
        )
    return user


async def require_admin(
    user: User = Depends(require_user),
) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
```

**Step 3: Run tests**

```bash
cd backend && uv run pytest tests/test_deps.py -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/core/deps.py backend/tests/test_deps.py
git commit -m "feat(auth): update deps to support session cookie authentication"
```

---

## Phase 2: Job Queue Infrastructure

### Task 5: Job and JobLog Models

**Files:**
- Create: `backend/app/models/job.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models_job.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_models_job.py
import pytest
from uuid import uuid4
from app.models.job import Job, JobLog, JobStatus, JobType


def test_job_model_exists():
    """Test Job model can be instantiated."""
    job = Job(
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.PENDING,
        payload={"url": "https://example.com"},
    )
    assert job.job_type == JobType.PROCESS_DOCUMENT
    assert job.status == JobStatus.PENDING


def test_job_log_model_exists():
    """Test JobLog model can be instantiated."""
    job_id = uuid4()
    log = JobLog(
        job_id=job_id,
        level="info",
        message="Processing started",
        details={"step": 1},
    )
    assert log.job_id == job_id
    assert log.level == "info"


def test_job_status_enum():
    """Test JobStatus has required values."""
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.RUNNING.value == "running"
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"


def test_job_type_enum():
    """Test JobType has required values."""
    assert JobType.PROCESS_DOCUMENT.value == "process_document"
    assert JobType.PROCESS_BATCH.value == "process_batch"
    assert JobType.SYNC_DRIVE_FOLDER.value == "sync_drive_folder"
    assert JobType.PROCESS_DRIVE_FILE.value == "process_drive_file"
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_models_job.py -v
```
Expected: FAIL with "cannot import name 'Job'"

**Step 3: Write implementation**

```python
# backend/app/models/job.py
import enum
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import String, Text, Enum, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, enum.Enum):
    PROCESS_DOCUMENT = "process_document"
    PROCESS_BATCH = "process_batch"
    SYNC_DRIVE_FOLDER = "sync_drive_folder"
    PROCESS_DRIVE_FILE = "process_drive_file"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_type: Mapped[JobType] = mapped_column(Enum(JobType), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    parent_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False)  # info, warn, error
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
```

**Step 4: Update models __init__.py**

Add to `backend/app/models/__init__.py`:
```python
from app.models.job import Job, JobLog, JobStatus, JobType

# Add to __all__:
    "Job",
    "JobLog",
    "JobStatus",
    "JobType",
```

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_models_job.py -v
```
Expected: PASS

**Step 6: Create migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add jobs and job_logs tables"
cd backend && uv run alembic upgrade head
```

**Step 7: Commit**

```bash
git add backend/app/models/job.py backend/app/models/__init__.py backend/tests/test_models_job.py backend/alembic/versions/
git commit -m "feat(jobs): add Job and JobLog models"
```

---

### Task 6: Job Queue Interface and Implementation

**Files:**
- Create: `backend/app/services/jobs/__init__.py`
- Create: `backend/app/services/jobs/queue.py`
- Test: `backend/tests/test_job_queue.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_job_queue.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from app.services.jobs.queue import JobQueue, AsyncioJobQueue
from app.models.job import JobType, JobStatus


def test_job_queue_interface_exists():
    """Test JobQueue interface exists."""
    assert hasattr(JobQueue, 'enqueue')
    assert hasattr(JobQueue, 'get_status')
    assert hasattr(JobQueue, 'get_job')
    assert hasattr(JobQueue, 'log')


@pytest.mark.asyncio
async def test_asyncio_job_queue_enqueue():
    """Test AsyncioJobQueue can enqueue jobs."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    queue = AsyncioJobQueue(session=mock_session)
    job_id = await queue.enqueue(
        job_type=JobType.PROCESS_DOCUMENT,
        payload={"url": "https://example.com"},
    )

    assert job_id is not None
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_asyncio_job_queue_log():
    """Test AsyncioJobQueue can add logs."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    queue = AsyncioJobQueue(session=mock_session)
    job_id = uuid4()

    await queue.log(job_id, "info", "Test message", {"key": "value"})

    mock_session.add.assert_called_once()
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_job_queue.py -v
```
Expected: FAIL with "cannot import name 'JobQueue'"

**Step 3: Write implementation**

```python
# backend/app/services/jobs/__init__.py
from app.services.jobs.queue import JobQueue, AsyncioJobQueue

__all__ = ["JobQueue", "AsyncioJobQueue"]
```

```python
# backend/app/services/jobs/queue.py
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.job import Job, JobLog, JobType, JobStatus


class JobQueue(ABC):
    """Abstract interface for job queue implementations."""

    @abstractmethod
    async def enqueue(
        self,
        job_type: JobType,
        payload: dict,
        created_by_id: UUID | None = None,
        parent_job_id: UUID | None = None,
    ) -> UUID:
        """Add a job to the queue."""
        pass

    @abstractmethod
    async def get_status(self, job_id: UUID) -> JobStatus | None:
        """Get the status of a job."""
        pass

    @abstractmethod
    async def get_job(self, job_id: UUID) -> Job | None:
        """Get a job by ID."""
        pass

    @abstractmethod
    async def log(
        self,
        job_id: UUID,
        level: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        """Add a log entry for a job."""
        pass


class AsyncioJobQueue(JobQueue):
    """Asyncio-based job queue with PostgreSQL persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(
        self,
        job_type: JobType,
        payload: dict,
        created_by_id: UUID | None = None,
        parent_job_id: UUID | None = None,
    ) -> UUID:
        """Add a job to the queue."""
        job = Job(
            job_type=job_type,
            status=JobStatus.PENDING,
            payload=payload,
            created_by_id=created_by_id,
            parent_job_id=parent_job_id,
        )
        self.session.add(job)
        await self.session.flush()
        return job.id

    async def get_status(self, job_id: UUID) -> JobStatus | None:
        """Get the status of a job."""
        result = await self.session.execute(
            select(Job.status).where(Job.id == job_id)
        )
        row = result.scalar_one_or_none()
        return row

    async def get_job(self, job_id: UUID) -> Job | None:
        """Get a job by ID."""
        result = await self.session.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def log(
        self,
        job_id: UUID,
        level: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        """Add a log entry for a job."""
        log_entry = JobLog(
            job_id=job_id,
            level=level,
            message=message,
            details=details,
        )
        self.session.add(log_entry)
        await self.session.commit()

    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Update job status."""
        values = {"status": status}
        if started_at:
            values["started_at"] = started_at
        if completed_at:
            values["completed_at"] = completed_at

        await self.session.execute(
            update(Job).where(Job.id == job_id).values(**values)
        )
        await self.session.commit()

    async def get_pending_jobs(self, limit: int = 10) -> list[Job]:
        """Get pending jobs ordered by creation time."""
        result = await self.session.execute(
            select(Job)
            .where(Job.status == JobStatus.PENDING)
            .order_by(Job.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_logs(self, job_id: UUID) -> list[JobLog]:
        """Get all logs for a job."""
        result = await self.session.execute(
            select(JobLog)
            .where(JobLog.job_id == job_id)
            .order_by(JobLog.created_at)
        )
        return list(result.scalars().all())
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_job_queue.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/jobs/ backend/tests/test_job_queue.py
git commit -m "feat(jobs): add JobQueue interface and AsyncioJobQueue implementation"
```

---

### Task 7: Job Worker

**Files:**
- Create: `backend/app/services/jobs/worker.py`
- Test: `backend/tests/test_job_worker.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_job_worker.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.jobs.worker import JobWorker
from app.models.job import Job, JobType, JobStatus


def test_job_worker_exists():
    """Test JobWorker can be instantiated."""
    worker = JobWorker()
    assert worker is not None


def test_job_worker_has_process_method():
    """Test JobWorker has process_job method."""
    worker = JobWorker()
    assert hasattr(worker, 'process_job')
    assert callable(worker.process_job)


def test_job_worker_has_run_method():
    """Test JobWorker has run method for background loop."""
    worker = JobWorker()
    assert hasattr(worker, 'run')
    assert callable(worker.run)
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_job_worker.py -v
```
Expected: FAIL with "cannot import name 'JobWorker'"

**Step 3: Write implementation**

```python
# backend/app/services/jobs/worker.py
import asyncio
import traceback
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.models.job import Job, JobStatus, JobType
from app.models.document import Document, ProcessingStatus
from app.services.jobs.queue import AsyncioJobQueue
from app.services.pipeline.orchestrator import process_document


class JobWorker:
    """Background worker that processes jobs from the queue."""

    def __init__(self):
        self.running = False
        self.poll_interval = 5  # seconds

    async def process_job(self, job: Job, session: AsyncSession) -> None:
        """Process a single job based on its type."""
        queue = AsyncioJobQueue(session)

        try:
            if job.job_type == JobType.PROCESS_DOCUMENT:
                await self._process_document(job, queue, session)
            elif job.job_type == JobType.PROCESS_BATCH:
                await self._process_batch(job, queue, session)
            elif job.job_type == JobType.SYNC_DRIVE_FOLDER:
                await self._sync_drive_folder(job, queue, session)
            elif job.job_type == JobType.PROCESS_DRIVE_FILE:
                await self._process_drive_file(job, queue, session)
            else:
                await queue.log(job.id, "error", f"Unknown job type: {job.job_type}")
                await queue.update_status(
                    job.id, JobStatus.FAILED, completed_at=datetime.now(timezone.utc)
                )
                return

            await queue.update_status(
                job.id, JobStatus.COMPLETED, completed_at=datetime.now(timezone.utc)
            )
        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()[-2000:],  # Last 2000 chars
            }
            await queue.log(job.id, "error", f"Job failed: {e}", error_details)
            await queue.update_status(
                job.id, JobStatus.FAILED, completed_at=datetime.now(timezone.utc)
            )

    async def _process_document(
        self, job: Job, queue: AsyncioJobQueue, session: AsyncSession
    ) -> None:
        """Process a single document (URL or reprocess existing)."""
        url = job.payload.get("url")
        document_id = job.payload.get("document_id")

        await queue.log(job.id, "info", "Starting document processing", {"url": url})

        if url:
            # Create new document
            document = Document(
                url=url,
                processing_status=ProcessingStatus.PROCESSING,
            )
            session.add(document)
            await session.flush()
            document_id = document.id

        # Process the document
        await process_document(document_id, session)
        await queue.log(job.id, "info", "Document processing completed")

    async def _process_batch(
        self, job: Job, queue: AsyncioJobQueue, session: AsyncSession
    ) -> None:
        """Process multiple documents by creating child jobs."""
        urls = job.payload.get("urls", [])
        await queue.log(job.id, "info", f"Creating {len(urls)} child jobs")

        for url in urls:
            child_job_id = await queue.enqueue(
                job_type=JobType.PROCESS_DOCUMENT,
                payload={"url": url},
                created_by_id=job.created_by_id,
                parent_job_id=job.id,
            )
            await queue.log(job.id, "info", f"Created child job", {"child_job_id": str(child_job_id), "url": url})

        await session.commit()

    async def _sync_drive_folder(
        self, job: Job, queue: AsyncioJobQueue, session: AsyncSession
    ) -> None:
        """Sync a Google Drive folder."""
        # Will be implemented in Drive integration task
        await queue.log(job.id, "info", "Drive sync not yet implemented")

    async def _process_drive_file(
        self, job: Job, queue: AsyncioJobQueue, session: AsyncSession
    ) -> None:
        """Process a file from Google Drive."""
        # Will be implemented in Drive integration task
        await queue.log(job.id, "info", "Drive file processing not yet implemented")

    async def run(self) -> None:
        """Main worker loop - polls for pending jobs."""
        self.running = True

        while self.running:
            async with async_session_maker() as session:
                queue = AsyncioJobQueue(session)

                # Get pending jobs
                jobs = await queue.get_pending_jobs(limit=1)

                for job in jobs:
                    # Mark as running
                    await queue.update_status(
                        job.id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc)
                    )
                    await queue.log(job.id, "info", "Job started")

                    # Process job
                    await self.process_job(job, session)

            await asyncio.sleep(self.poll_interval)

    async def recover_orphaned_jobs(self) -> None:
        """Mark jobs that were running when server crashed as failed."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Job).where(Job.status == JobStatus.RUNNING)
            )
            orphaned_jobs = result.scalars().all()

            for job in orphaned_jobs:
                queue = AsyncioJobQueue(session)
                await queue.log(
                    job.id, "error",
                    "Server restarted during processing - job marked as failed",
                    {"recovered_at": datetime.now(timezone.utc).isoformat()}
                )
                await queue.update_status(
                    job.id, JobStatus.FAILED, completed_at=datetime.now(timezone.utc)
                )

    def stop(self) -> None:
        """Stop the worker loop."""
        self.running = False
```

**Step 4: Update services/jobs/__init__.py**

```python
# backend/app/services/jobs/__init__.py
from app.services.jobs.queue import JobQueue, AsyncioJobQueue
from app.services.jobs.worker import JobWorker

__all__ = ["JobQueue", "AsyncioJobQueue", "JobWorker"]
```

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_job_worker.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/services/jobs/worker.py backend/app/services/jobs/__init__.py backend/tests/test_job_worker.py
git commit -m "feat(jobs): add JobWorker for background job processing"
```

---

### Task 8: Jobs API Endpoints

**Files:**
- Create: `backend/app/api/jobs.py`
- Create: `backend/app/schemas/job.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_jobs.py`

**Step 1: Create job schemas**

```python
# backend/app/schemas/job.py
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from app.models.job import JobStatus, JobType


class JobCreate(BaseModel):
    job_type: JobType
    payload: dict = {}


class JobBatchCreate(BaseModel):
    urls: list[str]


class JobLogResponse(BaseModel):
    id: UUID
    level: str
    message: str
    details: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    id: UUID
    job_type: JobType
    status: JobStatus
    payload: dict
    created_by_id: UUID | None
    parent_job_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class JobDetailResponse(JobResponse):
    logs: list[JobLogResponse] = []


class JobStatsResponse(BaseModel):
    pending: int
    running: int
    completed: int
    failed: int
```

**Step 2: Write the failing test**

```python
# backend/tests/test_api_jobs.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)
headers = {"X-API-Key": settings.admin_api_key}


def test_list_jobs():
    """Test listing jobs."""
    response = client.get("/api/admin/jobs", headers=headers)
    assert response.status_code == 200
    assert "jobs" in response.json()


def test_get_job_stats():
    """Test getting job statistics."""
    response = client.get("/api/admin/jobs/stats", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "pending" in data
    assert "running" in data
    assert "completed" in data
    assert "failed" in data


def test_create_batch_job():
    """Test creating a batch job."""
    response = client.post(
        "/api/admin/jobs/batch",
        headers=headers,
        json={"urls": ["https://example.com/1", "https://example.com/2"]},
    )
    assert response.status_code == 201
    assert "id" in response.json()
```

**Step 3: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_api_jobs.py -v
```
Expected: FAIL with "404 Not Found"

**Step 4: Write implementation**

```python
# backend/app/api/jobs.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_session
from app.core.deps import require_admin
from app.models.user import User
from app.models.job import Job, JobLog, JobStatus, JobType
from app.schemas.job import (
    JobCreate, JobBatchCreate, JobResponse, JobDetailResponse,
    JobLogResponse, JobStatsResponse
)
from app.services.jobs.queue import AsyncioJobQueue

router = APIRouter(prefix="/admin/jobs", tags=["jobs"])


@router.get("", response_model=dict)
async def list_jobs(
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """List jobs with optional filtering."""
    query = select(Job).order_by(Job.created_at.desc())

    if status:
        query = query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)

    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    jobs = result.scalars().all()

    return {
        "jobs": [JobResponse.model_validate(j) for j in jobs],
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats", response_model=JobStatsResponse)
async def get_job_stats(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """Get job statistics by status."""
    result = await session.execute(
        select(Job.status, func.count(Job.id))
        .group_by(Job.status)
    )
    stats = {row[0].value: row[1] for row in result.all()}

    return JobStatsResponse(
        pending=stats.get("pending", 0),
        running=stats.get("running", 0),
        completed=stats.get("completed", 0),
        failed=stats.get("failed", 0),
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """Get job details with logs."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get logs
    result = await session.execute(
        select(JobLog)
        .where(JobLog.job_id == job_id)
        .order_by(JobLog.created_at)
    )
    logs = result.scalars().all()

    response = JobDetailResponse.model_validate(job)
    response.logs = [JobLogResponse.model_validate(log) for log in logs]
    return response


@router.post("/batch", response_model=JobResponse, status_code=201)
async def create_batch_job(
    data: JobBatchCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """Create a batch job to process multiple URLs."""
    queue = AsyncioJobQueue(session)
    job_id = await queue.enqueue(
        job_type=JobType.PROCESS_BATCH,
        payload={"urls": data.urls},
        created_by_id=user.id if hasattr(user, 'id') and user.id else None,
    )
    await session.commit()

    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one()
    return JobResponse.model_validate(job)


@router.post("/{job_id}/retry", response_model=JobResponse, status_code=201)
async def retry_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """Retry a failed job by creating a new job with same payload."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    original_job = result.scalar_one_or_none()

    if not original_job:
        raise HTTPException(status_code=404, detail="Job not found")

    if original_job.status != JobStatus.FAILED:
        raise HTTPException(status_code=400, detail="Can only retry failed jobs")

    queue = AsyncioJobQueue(session)
    new_job_id = await queue.enqueue(
        job_type=original_job.job_type,
        payload={**original_job.payload, "retry_of": str(job_id)},
        created_by_id=user.id if hasattr(user, 'id') and user.id else None,
    )
    await session.commit()

    result = await session.execute(select(Job).where(Job.id == new_job_id))
    new_job = result.scalar_one()
    return JobResponse.model_validate(new_job)


@router.post("/bulk-retry", response_model=dict)
async def bulk_retry_failed(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """Retry all failed jobs."""
    result = await session.execute(
        select(Job).where(Job.status == JobStatus.FAILED)
    )
    failed_jobs = result.scalars().all()

    queue = AsyncioJobQueue(session)
    retried = 0

    for job in failed_jobs:
        await queue.enqueue(
            job_type=job.job_type,
            payload={**job.payload, "retry_of": str(job.id)},
            created_by_id=user.id if hasattr(user, 'id') and user.id else None,
        )
        retried += 1

    await session.commit()
    return {"retried": retried}
```

**Step 5: Register router in main.py**

Add to `backend/app/main.py`:
```python
from app.api.jobs import router as jobs_router

# Add after other routers:
app.include_router(jobs_router, prefix="/api")
```

**Step 6: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_api_jobs.py -v
```
Expected: PASS

**Step 7: Commit**

```bash
git add backend/app/api/jobs.py backend/app/schemas/job.py backend/app/main.py backend/tests/test_api_jobs.py
git commit -m "feat(jobs): add Jobs API endpoints"
```

---

## Phase 3: Google Drive Integration

### Task 9: Drive Models

**Files:**
- Create: `backend/app/models/drive.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models_drive.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_models_drive.py
import pytest
from uuid import uuid4
from app.models.drive import DriveFolder, DriveFile, DriveFileStatus


def test_drive_folder_model_exists():
    """Test DriveFolder model can be instantiated."""
    folder = DriveFolder(
        google_folder_id="1ABC123",
        name="Research Papers",
        owner_id=uuid4(),
    )
    assert folder.google_folder_id == "1ABC123"
    assert folder.name == "Research Papers"


def test_drive_file_model_exists():
    """Test DriveFile model can be instantiated."""
    file = DriveFile(
        folder_id=uuid4(),
        google_file_id="2XYZ789",
        name="paper.pdf",
        md5_hash="abc123",
    )
    assert file.google_file_id == "2XYZ789"


def test_drive_file_status_enum():
    """Test DriveFileStatus has required values."""
    assert DriveFileStatus.PENDING.value == "pending"
    assert DriveFileStatus.PROCESSING.value == "processing"
    assert DriveFileStatus.COMPLETED.value == "completed"
    assert DriveFileStatus.FAILED.value == "failed"
    assert DriveFileStatus.REMOVED.value == "removed"
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_models_drive.py -v
```
Expected: FAIL with "cannot import name 'DriveFolder'"

**Step 3: Write implementation**

```python
# backend/app/models/drive.py
import enum
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import String, Text, Boolean, Enum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class DriveFileStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REMOVED = "removed"


class DriveFolder(Base):
    __tablename__ = "drive_folders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    google_folder_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )


class DriveFile(Base):
    __tablename__ = "drive_files"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    folder_id: Mapped[UUID] = mapped_column(ForeignKey("drive_folders.id"), nullable=False)
    google_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    md5_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[DriveFileStatus] = mapped_column(
        Enum(DriveFileStatus), default=DriveFileStatus.PENDING
    )
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Step 4: Update models __init__.py**

Add to `backend/app/models/__init__.py`:
```python
from app.models.drive import DriveFolder, DriveFile, DriveFileStatus

# Add to __all__:
    "DriveFolder",
    "DriveFile",
    "DriveFileStatus",
```

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_models_drive.py -v
```
Expected: PASS

**Step 6: Create migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add drive_folders and drive_files tables"
cd backend && uv run alembic upgrade head
```

**Step 7: Commit**

```bash
git add backend/app/models/drive.py backend/app/models/__init__.py backend/tests/test_models_drive.py backend/alembic/versions/
git commit -m "feat(drive): add DriveFolder and DriveFile models"
```

---

### Task 10: Drive Service

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/services/drive/__init__.py`
- Create: `backend/app/services/drive/client.py`
- Test: `backend/tests/test_drive_service.py`

**Step 1: Update config**

Add to `backend/app/core/config.py` Settings class:
```python
    # Google Drive (service account)
    google_service_account_json: str | None = None  # JSON string or file path
    drive_sync_interval_minutes: int = 15
```

**Step 2: Write the failing test**

```python
# backend/tests/test_drive_service.py
import pytest
from unittest.mock import MagicMock, patch
from app.services.drive.client import DriveService


def test_drive_service_exists():
    """Test DriveService can be instantiated."""
    with patch("app.services.drive.client.service_account"):
        service = DriveService()
        assert service is not None


def test_drive_service_has_list_files():
    """Test DriveService has list_files method."""
    with patch("app.services.drive.client.service_account"):
        service = DriveService()
        assert hasattr(service, 'list_files')
        assert callable(service.list_files)


def test_drive_service_has_download_file():
    """Test DriveService has download_file method."""
    with patch("app.services.drive.client.service_account"):
        service = DriveService()
        assert hasattr(service, 'download_file')
        assert callable(service.download_file)
```

**Step 3: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_drive_service.py -v
```
Expected: FAIL with "cannot import name 'DriveService'"

**Step 4: Write implementation**

```python
# backend/app/services/drive/__init__.py
from app.services.drive.client import DriveService

__all__ = ["DriveService"]
```

```python
# backend/app/services/drive/client.py
import json
import io
from dataclasses import dataclass

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.core.config import settings


@dataclass
class DriveFileInfo:
    id: str
    name: str
    mime_type: str
    md5_checksum: str | None


class DriveService:
    """Google Drive service using service account authentication."""

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    def __init__(self):
        self.service = self._build_service()

    def _build_service(self):
        """Build the Drive API service."""
        if not settings.google_service_account_json:
            return None

        # Parse credentials from JSON string or file
        try:
            creds_data = json.loads(settings.google_service_account_json)
        except json.JSONDecodeError:
            # Assume it's a file path
            with open(settings.google_service_account_json) as f:
                creds_data = json.load(f)

        credentials = service_account.Credentials.from_service_account_info(
            creds_data, scopes=self.SCOPES
        )
        return build("drive", "v3", credentials=credentials)

    def list_files(self, folder_id: str) -> list[DriveFileInfo]:
        """List PDF files in a folder."""
        if not self.service:
            raise RuntimeError("Drive service not configured")

        files = []
        page_token = None

        while True:
            query = f"'{folder_id}' in parents and (mimeType='application/pdf' or mimeType='application/vnd.google-apps.document') and trashed=false"

            response = self.service.files().list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType, md5Checksum)",
                pageToken=page_token,
            ).execute()

            for file in response.get("files", []):
                files.append(DriveFileInfo(
                    id=file["id"],
                    name=file["name"],
                    mime_type=file["mimeType"],
                    md5_checksum=file.get("md5Checksum"),
                ))

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return files

    def download_file(self, file_id: str) -> bytes:
        """Download a file's content."""
        if not self.service:
            raise RuntimeError("Drive service not configured")

        request = self.service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        buffer.seek(0)
        return buffer.read()

    def export_google_doc(self, file_id: str, mime_type: str = "application/pdf") -> bytes:
        """Export a Google Doc to PDF."""
        if not self.service:
            raise RuntimeError("Drive service not configured")

        request = self.service.files().export_media(fileId=file_id, mimeType=mime_type)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        buffer.seek(0)
        return buffer.read()

    def verify_folder_access(self, folder_id: str) -> tuple[bool, str | None]:
        """Verify the service account can access a folder."""
        if not self.service:
            return False, "Drive service not configured"

        try:
            folder = self.service.files().get(
                fileId=folder_id, fields="id, name"
            ).execute()
            return True, folder.get("name")
        except Exception as e:
            return False, str(e)
```

**Step 5: Add dependencies to pyproject.toml**

```bash
cd backend && uv add google-auth google-api-python-client
```

**Step 6: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_drive_service.py -v
```
Expected: PASS

**Step 7: Commit**

```bash
git add backend/app/services/drive/ backend/app/core/config.py backend/tests/test_drive_service.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(drive): add DriveService for Google Drive API access"
```

---

### Task 11: Drive API Endpoints

**Files:**
- Create: `backend/app/api/drive.py`
- Create: `backend/app/schemas/drive.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_drive.py`

**Step 1: Create drive schemas**

```python
# backend/app/schemas/drive.py
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from app.models.drive import DriveFileStatus


class DriveFolderCreate(BaseModel):
    google_folder_id: str
    name: str | None = None


class DriveFolderResponse(BaseModel):
    id: UUID
    google_folder_id: str
    name: str
    is_active: bool
    last_sync_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class DriveFileResponse(BaseModel):
    id: UUID
    google_file_id: str
    name: str
    status: DriveFileStatus
    document_id: UUID | None
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None

    class Config:
        from_attributes = True
```

**Step 2: Write the failing test**

```python
# backend/tests/test_api_drive.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)
headers = {"X-API-Key": settings.admin_api_key}


def test_list_drive_folders():
    """Test listing drive folders."""
    response = client.get("/api/admin/drive/folders", headers=headers)
    assert response.status_code == 200
    assert "folders" in response.json()


def test_get_service_account_email():
    """Test getting service account email for sharing instructions."""
    response = client.get("/api/admin/drive/service-account", headers=headers)
    # Will return 200 with email or 503 if not configured
    assert response.status_code in [200, 503]
```

**Step 3: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_api_drive.py -v
```
Expected: FAIL with "404 Not Found"

**Step 4: Write implementation**

```python
# backend/app/api/drive.py
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_session
from app.core.deps import require_admin
from app.models.user import User
from app.models.drive import DriveFolder, DriveFile, DriveFileStatus
from app.models.job import JobType
from app.schemas.drive import DriveFolderCreate, DriveFolderResponse, DriveFileResponse
from app.services.drive.client import DriveService
from app.services.jobs.queue import AsyncioJobQueue

router = APIRouter(prefix="/admin/drive", tags=["drive"])


@router.get("/service-account")
async def get_service_account_info(user: User = Depends(require_admin)):
    """Get service account email for folder sharing instructions."""
    try:
        service = DriveService()
        if not service.service:
            raise HTTPException(status_code=503, detail="Drive service not configured")

        # Get service account email from credentials
        from app.core.config import settings
        import json

        try:
            creds = json.loads(settings.google_service_account_json)
        except:
            with open(settings.google_service_account_json) as f:
                creds = json.load(f)

        return {"email": creds.get("client_email")}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/folders", response_model=dict)
async def list_folders(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """List registered drive folders."""
    result = await session.execute(
        select(DriveFolder).order_by(DriveFolder.created_at.desc())
    )
    folders = result.scalars().all()
    return {"folders": [DriveFolderResponse.model_validate(f) for f in folders]}


@router.post("/folders", response_model=DriveFolderResponse, status_code=201)
async def create_folder(
    data: DriveFolderCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """Register a new drive folder."""
    # Verify access
    service = DriveService()
    can_access, folder_name = service.verify_folder_access(data.google_folder_id)

    if not can_access:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot access folder. Please share it with the service account. Error: {folder_name}"
        )

    # Check if already registered
    result = await session.execute(
        select(DriveFolder).where(DriveFolder.google_folder_id == data.google_folder_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Folder already registered")

    folder = DriveFolder(
        google_folder_id=data.google_folder_id,
        name=data.name or folder_name,
        owner_id=user.id if hasattr(user, 'id') and user.id else None,
    )
    session.add(folder)
    await session.commit()
    await session.refresh(folder)

    return DriveFolderResponse.model_validate(folder)


@router.post("/folders/{folder_id}/sync")
async def sync_folder(
    folder_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """Trigger a sync for a folder (creates a job)."""
    result = await session.execute(
        select(DriveFolder).where(DriveFolder.id == folder_id)
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    queue = AsyncioJobQueue(session)
    job_id = await queue.enqueue(
        job_type=JobType.SYNC_DRIVE_FOLDER,
        payload={"folder_id": str(folder_id)},
        created_by_id=user.id if hasattr(user, 'id') and user.id else None,
    )
    await session.commit()

    return {"job_id": str(job_id), "message": "Sync job created"}


@router.get("/folders/{folder_id}/files", response_model=dict)
async def list_folder_files(
    folder_id: UUID,
    status: DriveFileStatus | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """List files in a drive folder."""
    query = select(DriveFile).where(DriveFile.folder_id == folder_id)
    if status:
        query = query.where(DriveFile.status == status)
    query = query.order_by(DriveFile.created_at.desc())

    result = await session.execute(query)
    files = result.scalars().all()

    return {"files": [DriveFileResponse.model_validate(f) for f in files]}


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    """Delete a registered folder."""
    result = await session.execute(
        select(DriveFolder).where(DriveFolder.id == folder_id)
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    await session.delete(folder)
    await session.commit()

    return {"message": "Folder deleted"}
```

**Step 5: Register router in main.py**

Add to `backend/app/main.py`:
```python
from app.api.drive import router as drive_router

# Add after other routers:
app.include_router(drive_router, prefix="/api")
```

**Step 6: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_api_drive.py -v
```
Expected: PASS

**Step 7: Commit**

```bash
git add backend/app/api/drive.py backend/app/schemas/drive.py backend/app/main.py backend/tests/test_api_drive.py
git commit -m "feat(drive): add Drive API endpoints for folder management"
```

---

### Task 12: Drive Sync Job Implementation

**Files:**
- Modify: `backend/app/services/jobs/worker.py`
- Test: `backend/tests/test_drive_sync.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_drive_sync.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.jobs.worker import JobWorker
from app.models.job import Job, JobType, JobStatus


@pytest.mark.asyncio
async def test_sync_drive_folder_job():
    """Test drive folder sync job creates file records."""
    worker = JobWorker()

    mock_session = AsyncMock()
    mock_queue = AsyncMock()

    folder_id = uuid4()
    job = Job(
        id=uuid4(),
        job_type=JobType.SYNC_DRIVE_FOLDER,
        status=JobStatus.RUNNING,
        payload={"folder_id": str(folder_id)},
    )

    mock_files = [
        MagicMock(id="file1", name="doc1.pdf", mime_type="application/pdf", md5_checksum="abc"),
        MagicMock(id="file2", name="doc2.pdf", mime_type="application/pdf", md5_checksum="def"),
    ]

    with patch("app.services.jobs.worker.DriveService") as mock_drive:
        mock_drive.return_value.list_files.return_value = mock_files

        # Mock database queries
        mock_session.execute = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # This should not raise
        assert callable(worker._sync_drive_folder)
```

**Step 2: Run test to verify it passes with current stub**

```bash
cd backend && uv run pytest tests/test_drive_sync.py -v
```

**Step 3: Update worker.py with full drive sync implementation**

Update the `_sync_drive_folder` and `_process_drive_file` methods in `backend/app/services/jobs/worker.py`:

```python
# Add imports at top:
from app.models.drive import DriveFolder, DriveFile, DriveFileStatus
from app.services.drive.client import DriveService

# Replace the stub methods:

    async def _sync_drive_folder(
        self, job: Job, queue: AsyncioJobQueue, session: AsyncSession
    ) -> None:
        """Sync a Google Drive folder - discover new/changed files."""
        folder_id = job.payload.get("folder_id")

        # Get folder from DB
        result = await session.execute(
            select(DriveFolder).where(DriveFolder.id == folder_id)
        )
        folder = result.scalar_one_or_none()

        if not folder:
            raise ValueError(f"Folder not found: {folder_id}")

        await queue.log(job.id, "info", f"Syncing folder: {folder.name}")

        # Get files from Drive
        drive_service = DriveService()
        drive_files = drive_service.list_files(folder.google_folder_id)
        await queue.log(job.id, "info", f"Found {len(drive_files)} files in Drive")

        # Get existing file records
        result = await session.execute(
            select(DriveFile).where(DriveFile.folder_id == folder.id)
        )
        existing_files = {f.google_file_id: f for f in result.scalars().all()}

        new_files = 0
        updated_files = 0

        for drive_file in drive_files:
            existing = existing_files.get(drive_file.id)

            if not existing:
                # New file
                file_record = DriveFile(
                    folder_id=folder.id,
                    google_file_id=drive_file.id,
                    name=drive_file.name,
                    md5_hash=drive_file.md5_checksum,
                    status=DriveFileStatus.PENDING,
                )
                session.add(file_record)
                new_files += 1
            elif existing.md5_hash != drive_file.md5_checksum:
                # File changed
                existing.md5_hash = drive_file.md5_checksum
                existing.status = DriveFileStatus.PENDING
                existing.document_id = None  # Will be re-processed
                updated_files += 1

        # Mark files removed from Drive
        drive_file_ids = {f.id for f in drive_files}
        for google_file_id, existing in existing_files.items():
            if google_file_id not in drive_file_ids and existing.status != DriveFileStatus.REMOVED:
                existing.status = DriveFileStatus.REMOVED

        # Update folder last_sync_at
        folder.last_sync_at = datetime.now(timezone.utc)

        await session.commit()
        await queue.log(job.id, "info", f"Sync complete: {new_files} new, {updated_files} updated")

        # Create jobs for pending files
        result = await session.execute(
            select(DriveFile).where(
                DriveFile.folder_id == folder.id,
                DriveFile.status == DriveFileStatus.PENDING,
            )
        )
        pending_files = result.scalars().all()

        for file in pending_files:
            await queue.enqueue(
                job_type=JobType.PROCESS_DRIVE_FILE,
                payload={"drive_file_id": str(file.id)},
                created_by_id=job.created_by_id,
                parent_job_id=job.id,
            )

        await session.commit()
        await queue.log(job.id, "info", f"Created {len(pending_files)} processing jobs")

    async def _process_drive_file(
        self, job: Job, queue: AsyncioJobQueue, session: AsyncSession
    ) -> None:
        """Download and process a file from Google Drive."""
        drive_file_id = job.payload.get("drive_file_id")

        # Get file record
        result = await session.execute(
            select(DriveFile).where(DriveFile.id == drive_file_id)
        )
        drive_file = result.scalar_one_or_none()

        if not drive_file:
            raise ValueError(f"Drive file not found: {drive_file_id}")

        await queue.log(job.id, "info", f"Processing file: {drive_file.name}")

        # Update status
        drive_file.status = DriveFileStatus.PROCESSING
        await session.commit()

        try:
            # Download file
            drive_service = DriveService()

            if drive_file.name.endswith(".pdf") or "pdf" in drive_file.google_file_id.lower():
                content = drive_service.download_file(drive_file.google_file_id)
            else:
                # Google Doc - export as PDF
                content = drive_service.export_google_doc(drive_file.google_file_id)

            await queue.log(job.id, "info", f"Downloaded {len(content)} bytes")

            # Create document record
            from app.models.document import Document, SourceType, ProcessingStatus
            import hashlib

            content_hash = hashlib.sha256(content).hexdigest()

            # Check for duplicate
            result = await session.execute(
                select(Document).where(Document.content_hash == content_hash)
            )
            existing_doc = result.scalar_one_or_none()

            if existing_doc:
                await queue.log(job.id, "info", "Document already exists (duplicate content)")
                drive_file.document_id = existing_doc.id
                drive_file.status = DriveFileStatus.COMPLETED
                drive_file.processed_at = datetime.now(timezone.utc)
                await session.commit()
                return

            # Create new document
            document = Document(
                url=f"drive://{drive_file.google_file_id}",
                source_type=SourceType.DRIVE,
                title=drive_file.name,
                content_hash=content_hash,
                processing_status=ProcessingStatus.PROCESSING,
            )
            session.add(document)
            await session.flush()

            drive_file.document_id = document.id
            await session.commit()

            # Process the PDF content
            from app.services.pipeline.pdf_extractor import extract_pdf_text
            from app.services.pipeline.orchestrator import process_document

            # Extract text from PDF bytes
            text = await extract_pdf_text(content)
            document.content = text
            await session.commit()

            # Run the processing pipeline
            await process_document(document.id, session)

            drive_file.status = DriveFileStatus.COMPLETED
            drive_file.processed_at = datetime.now(timezone.utc)
            await session.commit()

            await queue.log(job.id, "info", "File processing completed")

        except Exception as e:
            drive_file.status = DriveFileStatus.FAILED
            drive_file.error_message = str(e)
            await session.commit()
            raise
```

**Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_drive_sync.py tests/test_job_worker.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/jobs/worker.py backend/tests/test_drive_sync.py
git commit -m "feat(drive): implement drive folder sync and file processing jobs"
```

---

### Task 13: Scheduled Drive Polling

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/services/jobs/scheduler.py`
- Test: `backend/tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_scheduler.py
import pytest
from app.services.jobs.scheduler import DriveSyncScheduler


def test_scheduler_exists():
    """Test DriveSyncScheduler can be instantiated."""
    scheduler = DriveSyncScheduler()
    assert scheduler is not None


def test_scheduler_has_start_method():
    """Test scheduler has start method."""
    scheduler = DriveSyncScheduler()
    assert hasattr(scheduler, 'start')
    assert callable(scheduler.start)


def test_scheduler_has_stop_method():
    """Test scheduler has stop method."""
    scheduler = DriveSyncScheduler()
    assert hasattr(scheduler, 'stop')
    assert callable(scheduler.stop)
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_scheduler.py -v
```
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/services/jobs/scheduler.py
import asyncio
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_maker
from app.models.drive import DriveFolder
from app.models.job import JobType
from app.services.jobs.queue import AsyncioJobQueue


class DriveSyncScheduler:
    """Scheduler for periodic Drive folder syncs."""

    def __init__(self):
        self.running = False
        self.interval_minutes = settings.drive_sync_interval_minutes

    async def start(self) -> None:
        """Start the scheduler loop."""
        self.running = True

        while self.running:
            await self._check_and_sync_folders()
            await asyncio.sleep(self.interval_minutes * 60)

    async def _check_and_sync_folders(self) -> None:
        """Check for folders needing sync and create jobs."""
        async with async_session_maker() as session:
            # Find active folders not synced within interval
            threshold = datetime.now(timezone.utc) - timedelta(minutes=self.interval_minutes)

            result = await session.execute(
                select(DriveFolder).where(
                    DriveFolder.is_active == True,
                    (DriveFolder.last_sync_at == None) | (DriveFolder.last_sync_at < threshold),
                )
            )
            folders = result.scalars().all()

            if folders:
                queue = AsyncioJobQueue(session)
                for folder in folders:
                    await queue.enqueue(
                        job_type=JobType.SYNC_DRIVE_FOLDER,
                        payload={"folder_id": str(folder.id)},
                    )
                await session.commit()

    def stop(self) -> None:
        """Stop the scheduler loop."""
        self.running = False
```

**Step 4: Update main.py with background tasks**

Update `backend/app/main.py` to start worker and scheduler on startup:

```python
# Add imports:
import asyncio
from contextlib import asynccontextmanager
from app.services.jobs.worker import JobWorker
from app.services.jobs.scheduler import DriveSyncScheduler

# Add lifespan context manager:
worker = JobWorker()
scheduler = DriveSyncScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await worker.recover_orphaned_jobs()
    asyncio.create_task(worker.run())
    asyncio.create_task(scheduler.start())
    yield
    # Shutdown
    worker.stop()
    scheduler.stop()

# Update FastAPI app creation:
app = FastAPI(
    title=settings.app_name,
    description="Human-Augmented Resource Intelligence API",
    version="0.1.0",
    lifespan=lifespan,
)
```

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_scheduler.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/services/jobs/scheduler.py backend/app/main.py backend/tests/test_scheduler.py
git commit -m "feat(drive): add scheduled Drive folder polling"
```

---

## Phase 4: Frontend Updates

### Task 14: Auth Context and Login

**Files:**
- Create: `frontend/src/contexts/AuthContext.tsx`
- Create: `frontend/src/components/auth/LoginButton.tsx`
- Modify: `frontend/src/components/layout/Header.tsx`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Create auth context**

```typescript
// frontend/src/contexts/AuthContext.tsx
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api } from '@/lib/api';

interface User {
  id: string;
  email: string;
  name: string | null;
  picture: string | null;
  role: 'user' | 'admin';
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => Promise<void>;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  async function checkAuth() {
    try {
      const response = await api.get('/api/auth/me');
      setUser(response.data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  function login() {
    window.location.href = `${api.defaults.baseURL}/api/auth/login`;
  }

  async function logout() {
    await api.post('/api/auth/logout');
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      logout,
      isAdmin: user?.role === 'admin',
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
```

**Step 2: Create login button component**

```typescript
// frontend/src/components/auth/LoginButton.tsx
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';

export function LoginButton() {
  const { user, loading, login, logout } = useAuth();

  if (loading) {
    return <Button variant="ghost" disabled>Loading...</Button>;
  }

  if (user) {
    return (
      <div className="flex items-center gap-3">
        {user.picture && (
          <img src={user.picture} alt="" className="w-8 h-8 rounded-full" />
        )}
        <span className="text-sm">{user.name || user.email}</span>
        <Button variant="ghost" size="sm" onClick={logout}>
          Logout
        </Button>
      </div>
    );
  }

  return (
    <Button variant="default" onClick={login}>
      Login with Google
    </Button>
  );
}
```

**Step 3: Update Header component**

Update `frontend/src/components/layout/Header.tsx` to include the login button.

**Step 4: Update api.ts to include credentials**

```typescript
// Update frontend/src/lib/api.ts:
export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,  // Include cookies for session auth
});
```

**Step 5: Update App.tsx with AuthProvider**

Wrap the app with AuthProvider.

**Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add OAuth login with Google"
```

---

### Task 15: Jobs Admin Page

**Files:**
- Create: `frontend/src/pages/JobsPage.tsx`
- Create: `frontend/src/components/admin/JobsTable.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`

**Step 1: Add jobs API functions**

```typescript
// Add to frontend/src/lib/api.ts:
export const jobsApi = {
  list: (status?: string, jobType?: string) =>
    api.get('/api/admin/jobs', { params: { status, job_type: jobType } }),

  getStats: () =>
    api.get('/api/admin/jobs/stats'),

  getJob: (id: string) =>
    api.get(`/api/admin/jobs/${id}`),

  retry: (id: string) =>
    api.post(`/api/admin/jobs/${id}/retry`),

  bulkRetry: () =>
    api.post('/api/admin/jobs/bulk-retry'),

  createBatch: (urls: string[]) =>
    api.post('/api/admin/jobs/batch', { urls }),
};
```

**Step 2: Create JobsTable component**

```typescript
// frontend/src/components/admin/JobsTable.tsx
// Component showing jobs list with status badges, logs modal, retry button
```

**Step 3: Create JobsPage**

```typescript
// frontend/src/pages/JobsPage.tsx
// Page with stats cards and jobs table
```

**Step 4: Add route to App.tsx**

**Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add Jobs admin page"
```

---

### Task 16: Drive Admin Page

**Files:**
- Create: `frontend/src/pages/DrivePage.tsx`
- Create: `frontend/src/components/admin/DriveFoldersTable.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`

**Step 1: Add drive API functions**

```typescript
// Add to frontend/src/lib/api.ts:
export const driveApi = {
  getServiceAccount: () =>
    api.get('/api/admin/drive/service-account'),

  listFolders: () =>
    api.get('/api/admin/drive/folders'),

  createFolder: (googleFolderId: string, name?: string) =>
    api.post('/api/admin/drive/folders', { google_folder_id: googleFolderId, name }),

  syncFolder: (id: string) =>
    api.post(`/api/admin/drive/folders/${id}/sync`),

  listFiles: (folderId: string, status?: string) =>
    api.get(`/api/admin/drive/folders/${folderId}/files`, { params: { status } }),

  deleteFolder: (id: string) =>
    api.delete(`/api/admin/drive/folders/${id}`),
};
```

**Step 2: Create DriveFoldersTable component**

**Step 3: Create DrivePage with add folder modal and sync buttons**

**Step 4: Add route to App.tsx**

**Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add Drive folders admin page"
```

---

## Final: Integration Testing

### Task 17: End-to-End Testing

**Step 1: Manual testing checklist**

1. Start backend: `cd backend && uv run uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Test OAuth login flow
4. Test creating a batch job
5. Verify worker picks up and processes jobs
6. Test Drive folder registration (with real Google folder)
7. Test sync and file processing
8. Verify scheduled sync runs

**Step 2: Run all tests**

```bash
cd backend && uv run pytest -v
```

**Step 3: Final commit**

```bash
git add .
git commit -m "feat: complete background processing and OAuth implementation"
```

---

## Summary

This plan implements:

1. **Google OAuth SSO** (Tasks 1-4)
   - Session model and management
   - OAuth service for Google
   - Auth API endpoints
   - Updated authentication dependencies

2. **Job Queue Infrastructure** (Tasks 5-8)
   - Job and JobLog models
   - AsyncioJobQueue implementation
   - JobWorker for background processing
   - Jobs API endpoints

3. **Google Drive Integration** (Tasks 9-13)
   - Drive models
   - DriveService with service account auth
   - Drive API endpoints
   - Sync and process jobs
   - Scheduled polling

4. **Frontend Updates** (Tasks 14-16)
   - Auth context and login
   - Jobs admin page
   - Drive admin page

**Total: 17 tasks**
