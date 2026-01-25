from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

from app.models.job import JobType, JobStatus, LogLevel


class JobCreate(BaseModel):
    """Schema for creating a job."""
    job_type: JobType
    payload: dict


class JobBatchCreate(BaseModel):
    """Schema for creating a batch job from URLs."""
    urls: list[str]


class JobLogResponse(BaseModel):
    """Schema for job log response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    level: LogLevel
    message: str
    details: dict | None
    created_at: datetime


class JobResponse(BaseModel):
    """Schema for job response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: JobType
    status: JobStatus
    payload: dict
    created_by_id: UUID | None
    parent_job_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class JobDetailResponse(JobResponse):
    """Schema for detailed job response with logs."""
    logs: list[JobLogResponse]


class JobStatsResponse(BaseModel):
    """Schema for job statistics response."""
    pending: int
    running: int
    completed: int
    failed: int


class JobListResponse(BaseModel):
    """Schema for paginated job list response."""
    items: list[JobResponse]
    total: int
    page: int
    page_size: int
