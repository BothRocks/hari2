"""Job and JobLog models for background task processing."""
import enum
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import String, Text, Enum, ForeignKey, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class JobStatus(str, enum.Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, enum.Enum):
    """Job type enumeration."""
    PROCESS_DOCUMENT = "process_document"
    PROCESS_BATCH = "process_batch"
    SYNC_DRIVE_FOLDER = "sync_drive_folder"
    PROCESS_DRIVE_FILE = "process_drive_file"


class LogLevel(str, enum.Enum):
    """Log level enumeration."""
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class Job(Base, TimestampMixin):
    """Background job model."""
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_type: Mapped[JobType] = mapped_column(Enum(JobType), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    parent_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobLog(Base):
    """Job log entry model."""
    __tablename__ = "job_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    level: Mapped[LogLevel] = mapped_column(Enum(LogLevel), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
