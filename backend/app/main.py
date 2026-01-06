import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.query import router as query_router
from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.api.drive import router as drive_router
from app.integrations.telegram.webhook import router as telegram_router
from app.integrations.slack.events import router as slack_router
from app.services.jobs.worker import JobWorker
from app.services.jobs.scheduler import DriveSyncScheduler

logger = logging.getLogger(__name__)


def validate_production_secrets(settings_obj=None) -> None:
    """Validate that production is not using default secrets."""
    s = settings_obj or settings

    if s.environment == "development":
        return

    if s.secret_key == "dev-secret-key-change-in-production":
        raise RuntimeError(
            "SECRET_KEY must be set in production. "
            'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )

    if s.admin_api_key == "dev-admin-key":
        raise RuntimeError(
            "ADMIN_API_KEY must be set in production. "
            'Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )


worker = JobWorker()
scheduler = DriveSyncScheduler()
_worker_task = None
_scheduler_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task, _scheduler_task
    # Validate secrets before starting
    validate_production_secrets()
    # Startup
    await worker.recover_orphaned_jobs()
    _worker_task = asyncio.create_task(worker.run())
    _scheduler_task = asyncio.create_task(scheduler.start())
    yield
    # Shutdown - stop and wait
    worker.stop()
    scheduler.stop()
    # Wait for tasks with timeout
    if _worker_task:
        try:
            await asyncio.wait_for(_worker_task, timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Worker task did not complete in time")
    if _scheduler_task:
        try:
            await asyncio.wait_for(_scheduler_task, timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Scheduler task did not complete in time")


app = FastAPI(
    title=settings.app_name,
    description="Human-Augmented Resource Intelligence API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(query_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(drive_router, prefix="/api")
app.include_router(telegram_router, prefix="/api")
app.include_router(slack_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.environment,
        "commit": settings.git_commit,
    }
