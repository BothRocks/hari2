import asyncio
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
from app.services.jobs.worker import JobWorker
from app.services.jobs.scheduler import DriveSyncScheduler

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


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.environment,
    }
