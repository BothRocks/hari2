from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_session
from app.core.deps import require_admin
from app.models.job import Job, JobLog, JobType, JobStatus, LogLevel
from app.models.user import User
from app.schemas.job import (
    JobCreate,
    JobBatchCreate,
    JobLogResponse,
    JobResponse,
    JobDetailResponse,
    JobStatsResponse,
)
from app.services.jobs.queue import AsyncioJobQueue

router = APIRouter(prefix="/admin/jobs", tags=["admin"])


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> list[JobResponse]:
    """List jobs with optional filtering and pagination."""
    query = select(Job)

    # Apply filters
    if status:
        query = query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)

    # Apply pagination and ordering
    query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)

    result = await session.execute(query)
    jobs = result.scalars().all()

    return [JobResponse.model_validate(job) for job in jobs]


@router.get("/stats", response_model=JobStatsResponse)
async def get_job_stats(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> JobStatsResponse:
    """Get job statistics by status."""
    # Count jobs by status
    pending_result = await session.execute(
        select(func.count(Job.id)).where(Job.status == JobStatus.PENDING)
    )
    pending = pending_result.scalar_one()

    running_result = await session.execute(
        select(func.count(Job.id)).where(Job.status == JobStatus.RUNNING)
    )
    running = running_result.scalar_one()

    completed_result = await session.execute(
        select(func.count(Job.id)).where(Job.status == JobStatus.COMPLETED)
    )
    completed = completed_result.scalar_one()

    failed_result = await session.execute(
        select(func.count(Job.id)).where(Job.status == JobStatus.FAILED)
    )
    failed = failed_result.scalar_one()

    return JobStatsResponse(
        pending=pending,
        running=running,
        completed=completed,
        failed=failed,
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job_detail(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> JobDetailResponse:
    """Get job details with logs."""
    # Get job
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Get logs
    logs_result = await session.execute(
        select(JobLog)
        .where(JobLog.job_id == job_id)
        .order_by(JobLog.created_at)
    )
    logs = logs_result.scalars().all()

    # Convert to response models
    job_response = JobResponse.model_validate(job)
    log_responses = [JobLogResponse.model_validate(log) for log in logs]

    return JobDetailResponse(
        **job_response.model_dump(),
        logs=log_responses,
    )


@router.post("/batch", response_model=JobResponse)
async def create_batch_job(
    batch_data: JobBatchCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> JobResponse:
    """Create a batch job from URLs."""
    if not batch_data.urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URLs list cannot be empty",
        )

    queue = AsyncioJobQueue(session)

    # Create batch job
    job_id = await queue.enqueue(
        job_type=JobType.PROCESS_BATCH,
        payload={"urls": batch_data.urls},
        created_by_id=user.id,
    )

    await session.commit()

    # Fetch and return the created job
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one()

    return JobResponse.model_validate(job)


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> JobResponse:
    """Retry a failed job."""
    # Get job
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed jobs can be retried. Job is not in failed state.",
        )

    queue = AsyncioJobQueue(session)

    # Create new job with same payload
    new_job_id = await queue.enqueue(
        job_type=job.job_type,
        payload=job.payload,
        created_by_id=user.id,
        parent_job_id=job.parent_job_id,
    )

    await session.commit()

    # Fetch and return the new job
    result = await session.execute(select(Job).where(Job.id == new_job_id))
    new_job = result.scalar_one()

    return JobResponse.model_validate(new_job)


@router.post("/bulk-retry")
async def bulk_retry_jobs(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Retry all failed jobs."""
    # Get all failed jobs
    result = await session.execute(
        select(Job).where(Job.status == JobStatus.FAILED)
    )
    failed_jobs = result.scalars().all()

    queue = AsyncioJobQueue(session)
    retried_count = 0

    for job in failed_jobs:
        await queue.enqueue(
            job_type=job.job_type,
            payload=job.payload,
            created_by_id=user.id,
            parent_job_id=job.parent_job_id,
        )
        retried_count += 1

    await session.commit()

    return {
        "retried_count": retried_count,
        "message": f"Retried {retried_count} failed jobs",
    }
