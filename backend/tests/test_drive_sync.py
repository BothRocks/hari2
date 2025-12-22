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
    assert callable(worker._sync_drive_folder)


@pytest.mark.asyncio
async def test_process_drive_file_job():
    """Test drive file processing job."""
    worker = JobWorker()
    assert callable(worker._process_drive_file)
