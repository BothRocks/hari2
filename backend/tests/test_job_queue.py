"""Tests for JobQueue interface and AsyncioJobQueue implementation."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobLog, JobStatus, JobType, LogLevel
from app.services.jobs.queue import JobQueue, AsyncioJobQueue


@pytest.mark.asyncio
async def test_asyncio_job_queue_enqueue():
    """Test enqueuing a job creates a Job with correct fields."""
    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.add = MagicMock()

    # Mock flush to simulate ID being set by the database
    async def mock_flush_side_effect():
        added_job = mock_session.add.call_args[0][0]
        if not hasattr(added_job, 'id') or added_job.id is None:
            added_job.id = uuid4()

    mock_session.flush = AsyncMock(side_effect=mock_flush_side_effect)

    queue = AsyncioJobQueue(mock_session)

    payload = {"document_id": "doc-123"}
    job_id = await queue.enqueue(
        job_type=JobType.PROCESS_DOCUMENT,
        payload=payload
    )

    assert job_id is not None
    assert mock_session.add.called

    # Verify the job object that was added
    added_job = mock_session.add.call_args[0][0]
    assert isinstance(added_job, Job)
    assert added_job.job_type == JobType.PROCESS_DOCUMENT
    assert added_job.status == JobStatus.PENDING
    assert added_job.payload == payload


@pytest.mark.asyncio
async def test_asyncio_job_queue_enqueue_with_user():
    """Test enqueuing a job with user reference."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    queue = AsyncioJobQueue(mock_session)
    user_id = uuid4()

    job_id = await queue.enqueue(
        job_type=JobType.PROCESS_BATCH,
        payload={"batch_id": "batch-456"},
        created_by_id=user_id
    )

    added_job = mock_session.add.call_args[0][0]
    assert added_job.created_by_id == user_id


@pytest.mark.asyncio
async def test_asyncio_job_queue_enqueue_with_parent():
    """Test enqueuing a job with parent job reference."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    queue = AsyncioJobQueue(mock_session)
    parent_id = uuid4()

    job_id = await queue.enqueue(
        job_type=JobType.PROCESS_DRIVE_FILE,
        payload={"file_id": "file-789"},
        parent_job_id=parent_id
    )

    added_job = mock_session.add.call_args[0][0]
    assert added_job.parent_job_id == parent_id


@pytest.mark.asyncio
async def test_asyncio_job_queue_get_status():
    """Test getting job status."""
    mock_session = MagicMock(spec=AsyncSession)

    # Mock query result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = JobStatus.RUNNING
    mock_session.execute = AsyncMock(return_value=mock_result)

    queue = AsyncioJobQueue(mock_session)
    job_id = uuid4()

    status = await queue.get_status(job_id)

    assert status == JobStatus.RUNNING
    assert mock_session.execute.called


@pytest.mark.asyncio
async def test_asyncio_job_queue_get_status_not_found():
    """Test getting status for non-existent job."""
    mock_session = MagicMock(spec=AsyncSession)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    queue = AsyncioJobQueue(mock_session)
    job_id = uuid4()

    status = await queue.get_status(job_id)

    assert status is None


@pytest.mark.asyncio
async def test_asyncio_job_queue_get_job():
    """Test getting a job by ID."""
    mock_session = MagicMock(spec=AsyncSession)

    # Create a mock job
    job_id = uuid4()
    mock_job = Job(
        id=job_id,
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.PENDING,
        payload={"test": "data"}
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_session.execute = AsyncMock(return_value=mock_result)

    queue = AsyncioJobQueue(mock_session)

    job = await queue.get_job(job_id)

    assert job == mock_job
    assert job.id == job_id


@pytest.mark.asyncio
async def test_asyncio_job_queue_get_job_not_found():
    """Test getting non-existent job returns None."""
    mock_session = MagicMock(spec=AsyncSession)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    queue = AsyncioJobQueue(mock_session)
    job_id = uuid4()

    job = await queue.get_job(job_id)

    assert job is None


@pytest.mark.asyncio
async def test_asyncio_job_queue_log():
    """Test logging a message for a job."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    queue = AsyncioJobQueue(mock_session)
    job_id = uuid4()

    await queue.log(
        job_id=job_id,
        level=LogLevel.INFO,
        message="Processing started"
    )

    assert mock_session.add.called
    assert mock_session.commit.called

    # Verify the log entry
    added_log = mock_session.add.call_args[0][0]
    assert isinstance(added_log, JobLog)
    assert added_log.job_id == job_id
    assert added_log.level == LogLevel.INFO
    assert added_log.message == "Processing started"
    assert added_log.details is None


@pytest.mark.asyncio
async def test_asyncio_job_queue_log_with_details():
    """Test logging with details."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    queue = AsyncioJobQueue(mock_session)
    job_id = uuid4()
    details = {"error_code": "E001", "stack": "..."}

    await queue.log(
        job_id=job_id,
        level=LogLevel.ERROR,
        message="Processing failed",
        details=details
    )

    added_log = mock_session.add.call_args[0][0]
    assert added_log.details == details


@pytest.mark.asyncio
async def test_asyncio_job_queue_log_all_levels():
    """Test logging supports all log levels."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    queue = AsyncioJobQueue(mock_session)
    job_id = uuid4()

    # Test INFO level
    await queue.log(job_id, LogLevel.INFO, "Info message")
    assert mock_session.add.call_args[0][0].level == LogLevel.INFO

    # Test WARN level
    await queue.log(job_id, LogLevel.WARN, "Warning message")
    assert mock_session.add.call_args[0][0].level == LogLevel.WARN

    # Test ERROR level
    await queue.log(job_id, LogLevel.ERROR, "Error message")
    assert mock_session.add.call_args[0][0].level == LogLevel.ERROR


@pytest.mark.asyncio
async def test_asyncio_job_queue_update_status():
    """Test updating job status."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    queue = AsyncioJobQueue(mock_session)
    job_id = uuid4()

    await queue.update_status(job_id, JobStatus.RUNNING)

    assert mock_session.execute.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_asyncio_job_queue_update_status_with_timestamps():
    """Test updating status with timestamps."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    queue = AsyncioJobQueue(mock_session)
    job_id = uuid4()
    now = datetime.now(timezone.utc)

    await queue.update_status(
        job_id,
        JobStatus.COMPLETED,
        started_at=now,
        completed_at=now
    )

    assert mock_session.execute.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_asyncio_job_queue_get_pending_jobs():
    """Test getting pending jobs."""
    mock_session = MagicMock(spec=AsyncSession)

    # Create mock jobs
    job1 = Job(id=uuid4(), job_type=JobType.PROCESS_DOCUMENT, status=JobStatus.PENDING, payload={})
    job2 = Job(id=uuid4(), job_type=JobType.PROCESS_BATCH, status=JobStatus.PENDING, payload={})

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [job1, job2]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    queue = AsyncioJobQueue(mock_session)

    jobs = await queue.get_pending_jobs()

    assert len(jobs) == 2
    assert jobs[0] == job1
    assert jobs[1] == job2


@pytest.mark.asyncio
async def test_asyncio_job_queue_get_pending_jobs_with_limit():
    """Test getting pending jobs respects limit."""
    mock_session = MagicMock(spec=AsyncSession)

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    queue = AsyncioJobQueue(mock_session)

    await queue.get_pending_jobs(limit=5)

    assert mock_session.execute.called


@pytest.mark.asyncio
async def test_asyncio_job_queue_get_logs():
    """Test getting logs for a job."""
    mock_session = MagicMock(spec=AsyncSession)

    job_id = uuid4()
    log1 = JobLog(id=uuid4(), job_id=job_id, level=LogLevel.INFO, message="Log 1")
    log2 = JobLog(id=uuid4(), job_id=job_id, level=LogLevel.ERROR, message="Log 2")

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [log1, log2]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    queue = AsyncioJobQueue(mock_session)

    logs = await queue.get_logs(job_id)

    assert len(logs) == 2
    assert logs[0] == log1
    assert logs[1] == log2


@pytest.mark.asyncio
async def test_job_queue_is_abstract():
    """Test that JobQueue is an abstract base class."""
    from abc import ABC

    assert issubclass(JobQueue, ABC)


@pytest.mark.asyncio
async def test_asyncio_job_queue_implements_interface():
    """Test that AsyncioJobQueue implements all JobQueue methods."""
    assert hasattr(AsyncioJobQueue, 'enqueue')
    assert hasattr(AsyncioJobQueue, 'get_status')
    assert hasattr(AsyncioJobQueue, 'get_job')
    assert hasattr(AsyncioJobQueue, 'log')
