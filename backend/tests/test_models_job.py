"""Tests for Job and JobLog models."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone

from app.models.job import Job, JobLog, JobStatus, JobType, LogLevel


def test_job_status_enum():
    """Test JobStatus enum values."""
    assert JobStatus.PENDING == "pending"
    assert JobStatus.RUNNING == "running"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"


def test_job_type_enum():
    """Test JobType enum values."""
    assert JobType.PROCESS_DOCUMENT == "process_document"
    assert JobType.PROCESS_BATCH == "process_batch"
    assert JobType.SYNC_DRIVE_FOLDER == "sync_drive_folder"
    assert JobType.PROCESS_DRIVE_FILE == "process_drive_file"


def test_log_level_enum():
    """Test LogLevel enum values."""
    assert LogLevel.INFO == "info"
    assert LogLevel.WARN == "warn"
    assert LogLevel.ERROR == "error"


def test_job_has_required_fields():
    """Test Job model has all required fields."""
    assert hasattr(Job, 'id')
    assert hasattr(Job, 'job_type')
    assert hasattr(Job, 'status')
    assert hasattr(Job, 'payload')
    assert hasattr(Job, 'created_by_id')
    assert hasattr(Job, 'parent_job_id')
    assert hasattr(Job, 'started_at')
    assert hasattr(Job, 'completed_at')
    assert hasattr(Job, 'created_at')
    assert hasattr(Job, 'updated_at')


def test_job_model_can_be_instantiated():
    """Test Job model can be instantiated with minimal fields."""
    job = Job(
        job_type=JobType.PROCESS_DOCUMENT,
        payload={"document_id": "test-123"}
    )
    assert job.job_type == JobType.PROCESS_DOCUMENT
    assert job.payload == {"document_id": "test-123"}


def test_job_with_user_reference():
    """Test Job model can have a user reference."""
    user_id = uuid4()
    job = Job(
        job_type=JobType.PROCESS_BATCH,
        payload={"batch_id": "batch-456"},
        created_by_id=user_id
    )
    assert job.created_by_id == user_id


def test_job_with_parent_reference():
    """Test Job model can have a parent job reference."""
    parent_id = uuid4()
    job = Job(
        job_type=JobType.PROCESS_DRIVE_FILE,
        payload={"file_id": "file-101"},
        parent_job_id=parent_id
    )
    assert job.parent_job_id == parent_id


def test_job_status_can_be_set():
    """Test Job status can be set to different values."""
    job = Job(
        job_type=JobType.PROCESS_DOCUMENT,
        payload={"document_id": "test-123"}
    )

    job.status = JobStatus.RUNNING
    assert job.status == JobStatus.RUNNING

    job.status = JobStatus.COMPLETED
    assert job.status == JobStatus.COMPLETED

    job.status = JobStatus.FAILED
    assert job.status == JobStatus.FAILED


def test_job_timestamps_can_be_set():
    """Test Job timestamps can be set."""
    job = Job(
        job_type=JobType.PROCESS_DOCUMENT,
        payload={"document_id": "test-123"}
    )

    now = datetime.now(timezone.utc)
    job.started_at = now
    assert job.started_at == now

    job.completed_at = now
    assert job.completed_at == now


def test_job_log_has_required_fields():
    """Test JobLog model has all required fields."""
    assert hasattr(JobLog, 'id')
    assert hasattr(JobLog, 'job_id')
    assert hasattr(JobLog, 'level')
    assert hasattr(JobLog, 'message')
    assert hasattr(JobLog, 'details')
    assert hasattr(JobLog, 'created_at')


def test_job_log_model_can_be_instantiated():
    """Test JobLog model can be instantiated."""
    job_id = uuid4()
    log = JobLog(
        job_id=job_id,
        level=LogLevel.INFO,
        message="Processing started"
    )
    assert log.job_id == job_id
    assert log.level == LogLevel.INFO
    assert log.message == "Processing started"


def test_job_log_with_details():
    """Test JobLog model can have details."""
    job_id = uuid4()
    details = {"error_code": "E001", "stack_trace": "..."}
    log = JobLog(
        job_id=job_id,
        level=LogLevel.ERROR,
        message="Processing failed",
        details=details
    )
    assert log.details == details


def test_job_log_level_values():
    """Test JobLog supports different log levels."""
    job_id = uuid4()

    info_log = JobLog(job_id=job_id, level=LogLevel.INFO, message="Info message")
    assert info_log.level == LogLevel.INFO

    warn_log = JobLog(job_id=job_id, level=LogLevel.WARN, message="Warning message")
    assert warn_log.level == LogLevel.WARN

    error_log = JobLog(job_id=job_id, level=LogLevel.ERROR, message="Error message")
    assert error_log.level == LogLevel.ERROR
