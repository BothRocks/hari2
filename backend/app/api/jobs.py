from typing import Any, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, or_, desc, asc, update

from app.core.database import get_session
from app.core.deps import require_admin
from app.models.job import Job, JobLog, JobType, JobStatus
from app.models.user import User
from app.schemas.job import (
    JobBatchCreate,
    JobLogResponse,
    JobResponse,
    JobDetailResponse,
    JobStatsResponse,
    JobListResponse,
)
from app.services.jobs.queue import AsyncioJobQueue

router = APIRouter(prefix="/admin/jobs", tags=["admin"])


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    status_filter: JobStatus | None = Query(None, alias="status"),
    job_type: JobType | None = None,
    search: str | None = Query(None, description="Search in filename and error message"),
    sort_by: Literal["created_at", "status", "job_type"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> JobListResponse:
    """List jobs with search, filtering, sorting, and pagination."""
    query = select(Job).where(Job.archived == False)  # noqa: E712

    # Apply filters
    if status_filter:
        query = query.where(Job.status == status_filter)
    if job_type:
        query = query.where(Job.job_type == job_type)

    # Apply search (search in payload->document_id filename, or error_message)
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(Job.payload["url"].astext).like(search_pattern),
                func.lower(Job.payload["document_id"].astext).like(search_pattern),
                func.lower(Job.error_message).like(search_pattern),
            )
        )

    # Get total count before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_column = getattr(Job, sort_by, Job.created_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.limit(page_size).offset(offset)

    result = await session.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(
        items=[JobResponse.model_validate(job) for job in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=JobStatsResponse)
async def get_job_stats(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> JobStatsResponse:
    """Get job statistics by status."""
    # Count non-archived jobs by status using a single query with conditional aggregation
    result = await session.execute(
        select(
            func.count(case((Job.status == JobStatus.PENDING, 1))).label('pending'),
            func.count(case((Job.status == JobStatus.RUNNING, 1))).label('running'),
            func.count(case((Job.status == JobStatus.COMPLETED, 1))).label('completed'),
            func.count(case((Job.status == JobStatus.FAILED, 1))).label('failed'),
        ).where(Job.archived == False)  # noqa: E712
    )
    row = result.one()

    return JobStatsResponse(
        pending=row.pending,
        running=row.running,
        completed=row.completed,
        failed=row.failed,
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

    if len(batch_data.urls) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size exceeds maximum limit of 1000 URLs",
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


@router.post("/archive")
async def archive_jobs(
    filter: Literal["all", "failed", "completed"] = Query(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Archive jobs by filter."""
    stmt = update(Job).where(Job.archived == False).values(archived=True)  # noqa: E712

    if filter == "failed":
        stmt = stmt.where(Job.status == JobStatus.FAILED)
    elif filter == "completed":
        stmt = stmt.where(Job.status == JobStatus.COMPLETED)
    # "all" archives everything non-archived

    result = await session.execute(stmt)
    await session.commit()

    return {"archived_count": result.rowcount}
