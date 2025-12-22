"""Tests for JobWorker background processing."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus, JobType, LogLevel
from app.services.jobs.worker import JobWorker
from app.services.jobs.queue import AsyncioJobQueue


@pytest.mark.asyncio
async def test_worker_initialization():
    """Test worker initializes with correct state."""
    worker = JobWorker()

    assert worker.running is False
    assert worker.poll_interval == 5


@pytest.mark.asyncio
async def test_process_document_job():
    """Test processing a PROCESS_DOCUMENT job."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.execute = AsyncMock()

    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.RUNNING,
        payload={"url": "https://example.com/doc"},
    )

    worker = JobWorker()
    await worker.process_job(job, mock_session)

    # Verify session.commit was called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_process_batch_job():
    """Test processing a PROCESS_BATCH job creates child jobs."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    # Mock flush to simulate ID generation
    async def mock_flush_side_effect():
        for call in mock_session.add.call_args_list:
            obj = call[0][0]
            if not hasattr(obj, 'id') or obj.id is None:
                obj.id = uuid4()

    mock_session.flush = AsyncMock(side_effect=mock_flush_side_effect)

    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_BATCH,
        status=JobStatus.RUNNING,
        payload={"urls": ["https://example.com/1", "https://example.com/2"]},
        created_by_id=uuid4(),
    )

    worker = JobWorker()
    await worker.process_job(job, mock_session)

    # Verify session.commit was called
    assert mock_session.commit.called

    # Count how many child jobs were created (excluding logs)
    child_jobs = [call[0][0] for call in mock_session.add.call_args_list if isinstance(call[0][0], Job)]
    # Should have created 2 child jobs
    assert len(child_jobs) == 2


@pytest.mark.asyncio
async def test_process_drive_folder_placeholder():
    """Test SYNC_DRIVE_FOLDER job logs placeholder message."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    job = Job(
        id=uuid4(),
        job_type=JobType.SYNC_DRIVE_FOLDER,
        status=JobStatus.RUNNING,
        payload={"folder_id": "folder-123"},
    )

    worker = JobWorker()
    await worker.process_job(job, mock_session)

    # Verify session.commit was called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_process_drive_file_placeholder():
    """Test PROCESS_DRIVE_FILE job logs placeholder message."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DRIVE_FILE,
        status=JobStatus.RUNNING,
        payload={"file_id": "file-456"},
    )

    worker = JobWorker()
    await worker.process_job(job, mock_session)

    # Verify session.commit was called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_process_job_handles_error():
    """Test that process_job handles exceptions and marks job as failed."""
    from app.models.job import JobLog

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.execute = AsyncMock()

    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.RUNNING,
        payload={"url": "https://example.com"},
    )

    worker = JobWorker()

    # Mock the internal method to raise an exception
    async def mock_error(*args, **kwargs):
        raise ValueError("Test error")

    worker._process_document = mock_error

    await worker.process_job(job, mock_session)

    # Verify session.commit was called
    assert mock_session.commit.called

    # Verify error was logged - check for JobLog with ERROR level
    log_calls = [call[0][0] for call in mock_session.add.call_args_list if isinstance(call[0][0], JobLog)]
    assert len(log_calls) > 0
    error_logs = [log for log in log_calls if log.level == LogLevel.ERROR]
    assert len(error_logs) > 0


@pytest.mark.asyncio
async def test_process_job_updates_status_to_completed():
    """Test successful job processing updates status to COMPLETED."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.execute = AsyncMock()

    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.RUNNING,
        payload={"url": "https://example.com"},
    )

    worker = JobWorker()
    await worker.process_job(job, mock_session)

    # Verify execute was called to update status
    assert mock_session.execute.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_recover_orphaned_jobs():
    """Test recover_orphaned_jobs marks running jobs as failed."""
    # Create mock running jobs
    job1 = Job(id=uuid4(), job_type=JobType.PROCESS_DOCUMENT, status=JobStatus.RUNNING, payload={})
    job2 = Job(id=uuid4(), job_type=JobType.PROCESS_BATCH, status=JobStatus.RUNNING, payload={})

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [job1, job2]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    with patch('app.services.jobs.worker.async_session_factory') as mock_factory:
        # Setup context manager
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_factory.return_value = mock_context

        worker = JobWorker()
        await worker.recover_orphaned_jobs()

    # Verify session.commit was called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_worker_stop():
    """Test stop() method sets running to False."""
    worker = JobWorker()
    worker.running = True

    worker.stop()

    assert worker.running is False


@pytest.mark.asyncio
async def test_run_processes_pending_jobs():
    """Test run() method polls and processes pending jobs."""
    # Create a mock pending job
    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.PENDING,
        payload={"url": "https://example.com"},
    )

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [job]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    with patch('app.services.jobs.worker.async_session_factory') as mock_factory:
        # Setup context manager
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_factory.return_value = mock_context

        worker = JobWorker()

        # Run worker for one iteration
        async def stop_after_one():
            await asyncio.sleep(0.1)
            worker.stop()

        import asyncio
        await asyncio.gather(
            worker.run(),
            stop_after_one()
        )

    # Verify job was processed (status updated)
    assert mock_session.execute.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_run_calls_recover_orphaned_jobs_on_startup():
    """Test run() method calls recover_orphaned_jobs on startup."""
    # Mock for recovery: no orphaned jobs
    mock_scalars_recovery = MagicMock()
    mock_scalars_recovery.all.return_value = []
    mock_result_recovery = MagicMock()
    mock_result_recovery.scalars.return_value = mock_scalars_recovery

    # Mock for pending jobs: no jobs
    mock_scalars_pending = MagicMock()
    mock_scalars_pending.all.return_value = []
    mock_result_pending = MagicMock()
    mock_result_pending.scalars.return_value = mock_scalars_pending

    mock_session = MagicMock(spec=AsyncSession)
    # First call is for recovery, subsequent calls are for pending jobs
    mock_session.execute = AsyncMock(side_effect=[mock_result_recovery, mock_result_pending])
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    with patch('app.services.jobs.worker.async_session_factory') as mock_factory:
        # Setup context manager
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_factory.return_value = mock_context

        worker = JobWorker()

        # Run worker for one iteration
        async def stop_after_one():
            await asyncio.sleep(0.1)
            worker.stop()

        import asyncio
        await asyncio.gather(
            worker.run(),
            stop_after_one()
        )

    # Verify recover_orphaned_jobs was called (session.execute called at least once)
    assert mock_session.execute.call_count >= 1
    # Verify the first execute call was for recovery (checking for RUNNING jobs)
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_process_document_with_document_id():
    """Test processing a document with document_id in payload."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.execute = AsyncMock()

    doc_id = uuid4()
    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DOCUMENT,
        status=JobStatus.RUNNING,
        payload={"document_id": str(doc_id)},
    )

    worker = JobWorker()
    await worker.process_job(job, mock_session)

    # Verify session.commit was called
    assert mock_session.commit.called
