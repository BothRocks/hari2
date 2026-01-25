# backend/tests/test_api_jobs.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime

from app.models.job import Job, JobLog, JobType, JobStatus, LogLevel
from app.models.user import User, UserRole


def test_jobs_router_exists():
    """Test that the jobs router exists and has correct config."""
    from app.api.jobs import router
    assert router is not None
    assert router.prefix == "/admin/jobs"
    assert "admin" in router.tags


@pytest.mark.asyncio
async def test_list_jobs_default():
    """Test listing jobs with default parameters."""
    from app.api.jobs import list_jobs
    from sqlalchemy.ext.asyncio import AsyncSession

    # Create mock jobs
    job1 = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.PENDING,
        payload={"url": "https://example.com"},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=None,
        completed_at=None,
    )
    job2 = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_BATCH,
        status=JobStatus.RUNNING,
        payload={"urls": ["https://example1.com", "https://example2.com"]},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=datetime.now(),
        completed_at=None,
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock count query result
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 2

    # Mock jobs query result
    mock_jobs_result = MagicMock()
    mock_jobs_result.scalars.return_value.all.return_value = [job1, job2]

    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_jobs_result])

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await list_jobs(
        status_filter=None,
        job_type=None,
        search=None,
        sort_by="created_at",
        sort_order="desc",
        page=1,
        page_size=20,
        session=mock_session,
        user=mock_admin,
    )

    assert result.total == 2
    assert len(result.items) == 2
    assert result.items[0].job_type == JobType.PROCESS_DOCUMENT
    assert result.items[1].job_type == JobType.PROCESS_BATCH


@pytest.mark.asyncio
async def test_list_jobs_with_status_filter():
    """Test listing jobs filtered by status."""
    from app.api.jobs import list_jobs
    from sqlalchemy.ext.asyncio import AsyncSession

    # Create mock job
    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.COMPLETED,
        payload={"url": "https://example.com"},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock count query result
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    # Mock jobs query result
    mock_jobs_result = MagicMock()
    mock_jobs_result.scalars.return_value.all.return_value = [job]

    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_jobs_result])

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await list_jobs(
        status_filter=JobStatus.COMPLETED,
        job_type=None,
        search=None,
        sort_by="created_at",
        sort_order="desc",
        page=1,
        page_size=20,
        session=mock_session,
        user=mock_admin,
    )

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].status == JobStatus.COMPLETED


@pytest.mark.asyncio
async def test_list_jobs_with_job_type_filter():
    """Test listing jobs filtered by job type."""
    from app.api.jobs import list_jobs
    from sqlalchemy.ext.asyncio import AsyncSession

    # Create mock job
    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_BATCH,
        status=JobStatus.PENDING,
        payload={"urls": []},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=None,
        completed_at=None,
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock count query result
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    # Mock jobs query result
    mock_jobs_result = MagicMock()
    mock_jobs_result.scalars.return_value.all.return_value = [job]

    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_jobs_result])

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await list_jobs(
        status_filter=None,
        job_type=JobType.PROCESS_BATCH,
        search=None,
        sort_by="created_at",
        sort_order="desc",
        page=1,
        page_size=20,
        session=mock_session,
        user=mock_admin,
    )

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].job_type == JobType.PROCESS_BATCH


@pytest.mark.asyncio
async def test_list_jobs_pagination():
    """Test listing jobs with pagination."""
    from app.api.jobs import list_jobs
    from app.schemas.job import JobListResponse
    from sqlalchemy.ext.asyncio import AsyncSession

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock count query result
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 50

    # Mock jobs query result
    mock_jobs_result = MagicMock()
    mock_jobs_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_jobs_result])

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await list_jobs(
        status_filter=None,
        job_type=None,
        search=None,
        sort_by="created_at",
        sort_order="desc",
        page=3,
        page_size=10,
        session=mock_session,
        user=mock_admin,
    )

    assert isinstance(result, JobListResponse)
    assert result.page == 3
    assert result.page_size == 10
    assert result.total == 50


@pytest.mark.asyncio
async def test_get_job_stats():
    """Test getting job statistics."""
    from app.api.jobs import get_job_stats
    from sqlalchemy.ext.asyncio import AsyncSession

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock result with named tuple-like row (optimized single query)
    mock_row = MagicMock()
    mock_row.pending = 5
    mock_row.running = 2
    mock_row.completed = 10
    mock_row.failed = 1

    mock_result = MagicMock()
    mock_result.one.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await get_job_stats(session=mock_session, user=mock_admin)

    assert result.pending == 5
    assert result.running == 2
    assert result.completed == 10
    assert result.failed == 1


@pytest.mark.asyncio
async def test_get_job_detail_success():
    """Test getting job details with logs."""
    from app.api.jobs import get_job_detail
    from sqlalchemy.ext.asyncio import AsyncSession

    job_id = uuid4()
    job = Job(
        id=job_id,
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.COMPLETED,
        payload={"url": "https://example.com"},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )

    log1 = JobLog(
        id=uuid4(),
        job_id=job_id,
        level=LogLevel.INFO,
        message="Job started",
        details=None,
        created_at=datetime.now(),
    )
    log2 = JobLog(
        id=uuid4(),
        job_id=job_id,
        level=LogLevel.INFO,
        message="Job completed",
        details={"result": "success"},
        created_at=datetime.now(),
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock job query
    mock_job_result = MagicMock()
    mock_job_result.scalar_one_or_none.return_value = job

    # Mock logs query
    mock_logs_result = MagicMock()
    mock_logs_result.scalars.return_value.all.return_value = [log1, log2]

    mock_session.execute = AsyncMock(side_effect=[mock_job_result, mock_logs_result])

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await get_job_detail(job_id=job_id, session=mock_session, user=mock_admin)

    assert result.id == job_id
    assert result.status == JobStatus.COMPLETED
    assert len(result.logs) == 2
    assert result.logs[0].message == "Job started"
    assert result.logs[1].message == "Job completed"


@pytest.mark.asyncio
async def test_get_job_detail_not_found():
    """Test getting job details for non-existent job."""
    from app.api.jobs import get_job_detail
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import HTTPException

    job_id = uuid4()

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await get_job_detail(job_id=job_id, session=mock_session, user=mock_admin)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_create_batch_job():
    """Test creating a batch job from URLs."""
    from app.api.jobs import create_batch_job
    from app.schemas.job import JobBatchCreate
    from sqlalchemy.ext.asyncio import AsyncSession

    # Create mock job
    created_job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_BATCH,
        status=JobStatus.PENDING,
        payload={"urls": ["https://example1.com", "https://example2.com"]},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=None,
        completed_at=None,
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()

    # Mock execute to return the created job
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = created_job
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    batch_data = JobBatchCreate(urls=["https://example1.com", "https://example2.com"])

    result = await create_batch_job(batch_data=batch_data, session=mock_session, user=mock_admin)

    assert result is not None
    assert result.job_type == JobType.PROCESS_BATCH
    assert mock_session.add.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_retry_job_success():
    """Test retrying a failed job."""
    from app.api.jobs import retry_job
    from sqlalchemy.ext.asyncio import AsyncSession

    job_id = uuid4()
    job = Job(
        id=job_id,
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.FAILED,
        payload={"url": "https://example.com"},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )

    # Create new job for retry
    new_job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.PENDING,
        payload={"url": "https://example.com"},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=None,
        completed_at=None,
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock first execute (get original job)
    mock_result1 = MagicMock()
    mock_result1.scalar_one_or_none.return_value = job

    # Mock second execute (get new job)
    mock_result2 = MagicMock()
    mock_result2.scalar_one.return_value = new_job

    mock_session.execute = AsyncMock(side_effect=[mock_result1, mock_result2])
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await retry_job(job_id=job_id, session=mock_session, user=mock_admin)

    assert result is not None
    assert result.status == JobStatus.PENDING
    assert mock_session.add.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_retry_job_not_found():
    """Test retrying a non-existent job."""
    from app.api.jobs import retry_job
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import HTTPException

    job_id = uuid4()

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await retry_job(job_id=job_id, session=mock_session, user=mock_admin)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_retry_job_not_failed():
    """Test retrying a job that is not in failed state."""
    from app.api.jobs import retry_job
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import HTTPException

    job_id = uuid4()
    job = Job(
        id=job_id,
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.COMPLETED,  # Not failed
        payload={"url": "https://example.com"},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = job
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await retry_job(job_id=job_id, session=mock_session, user=mock_admin)

    assert exc_info.value.status_code == 400
    assert "failed state" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_bulk_retry_jobs():
    """Test retrying all failed jobs."""
    from app.api.jobs import bulk_retry_jobs
    from sqlalchemy.ext.asyncio import AsyncSession

    # Create mock failed jobs
    job1 = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.FAILED,
        payload={"url": "https://example1.com"},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )
    job2 = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.FAILED,
        payload={"url": "https://example2.com"},
        created_by_id=uuid4(),
        parent_job_id=None,
        created_at=datetime.now(),
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [job1, job2]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await bulk_retry_jobs(session=mock_session, user=mock_admin)

    assert result["retried_count"] == 2


@pytest.mark.asyncio
async def test_create_batch_job_exceeds_max_urls():
    """Test creating a batch job with more than 1000 URLs."""
    from app.api.jobs import create_batch_job
    from app.schemas.job import JobBatchCreate
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import HTTPException

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    # Create batch data with more than 1000 URLs
    batch_data = JobBatchCreate(urls=[f"https://example{i}.com" for i in range(1001)])

    with pytest.raises(HTTPException) as exc_info:
        await create_batch_job(batch_data=batch_data, session=mock_session, user=mock_admin)

    assert exc_info.value.status_code == 400
    assert "exceeds maximum limit" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_create_batch_job_empty_urls():
    """Test creating a batch job with empty URLs list."""
    from app.api.jobs import create_batch_job
    from app.schemas.job import JobBatchCreate
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import HTTPException

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    batch_data = JobBatchCreate(urls=[])

    with pytest.raises(HTTPException) as exc_info:
        await create_batch_job(batch_data=batch_data, session=mock_session, user=mock_admin)

    assert exc_info.value.status_code == 400
    assert "cannot be empty" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_job_stats_optimized():
    """Test that get_job_stats uses optimized single query."""
    from app.api.jobs import get_job_stats
    from sqlalchemy.ext.asyncio import AsyncSession

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock result with named tuple-like row
    mock_row = MagicMock()
    mock_row.pending = 5
    mock_row.running = 2
    mock_row.completed = 10
    mock_row.failed = 1

    mock_result = MagicMock()
    mock_result.one.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await get_job_stats(session=mock_session, user=mock_admin)

    # Verify it was called only once (optimized query)
    assert mock_session.execute.call_count == 1
    assert result.pending == 5
    assert result.running == 2
    assert result.completed == 10
    assert result.failed == 1
