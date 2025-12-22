from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.models.job import Job, JobLog, JobType, JobStatus, LogLevel


class JobQueue(ABC):
    """Abstract interface for job queue implementations."""

    @abstractmethod
    async def enqueue(
        self,
        job_type: JobType,
        payload: dict,
        created_by_id: UUID | None = None,
        parent_job_id: UUID | None = None,
    ) -> UUID:
        """Add a job to the queue."""
        pass

    @abstractmethod
    async def get_status(self, job_id: UUID) -> JobStatus | None:
        """Get the status of a job."""
        pass

    @abstractmethod
    async def get_job(self, job_id: UUID) -> Job | None:
        """Get a job by ID."""
        pass

    @abstractmethod
    async def log(
        self,
        job_id: UUID,
        level: LogLevel,
        message: str,
        details: dict | None = None,
    ) -> None:
        """Add a log entry for a job."""
        pass

    @abstractmethod
    async def cancel(self, job_id: UUID) -> bool:
        """Cancel a job if it's in PENDING status.

        Returns True if the job was cancelled, False otherwise.
        """
        pass


class AsyncioJobQueue(JobQueue):
    """Asyncio-based job queue with PostgreSQL persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(
        self,
        job_type: JobType,
        payload: dict,
        created_by_id: UUID | None = None,
        parent_job_id: UUID | None = None,
    ) -> UUID:
        """Add a job to the queue."""
        job = Job(
            job_type=job_type,
            status=JobStatus.PENDING,
            payload=payload,
            created_by_id=created_by_id,
            parent_job_id=parent_job_id,
        )
        self.session.add(job)
        await self.session.flush()
        return job.id

    async def get_status(self, job_id: UUID) -> JobStatus | None:
        """Get the status of a job."""
        result = await self.session.execute(
            select(Job.status).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_job(self, job_id: UUID) -> Job | None:
        """Get a job by ID."""
        result = await self.session.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def log(
        self,
        job_id: UUID,
        level: LogLevel,
        message: str,
        details: dict | None = None,
    ) -> None:
        """Add a log entry for a job."""
        log_entry = JobLog(
            job_id=job_id,
            level=level,
            message=message,
            details=details,
        )
        self.session.add(log_entry)

    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Update job status."""
        values = {"status": status}
        if started_at:
            values["started_at"] = started_at
        if completed_at:
            values["completed_at"] = completed_at

        await self.session.execute(
            update(Job).where(Job.id == job_id).values(**values)
        )

    async def get_pending_jobs(self, limit: int = 10) -> list[Job]:
        """Get pending jobs ordered by creation time."""
        result = await self.session.execute(
            select(Job)
            .where(Job.status == JobStatus.PENDING)
            .order_by(Job.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_logs(self, job_id: UUID) -> list[JobLog]:
        """Get all logs for a job."""
        result = await self.session.execute(
            select(JobLog)
            .where(JobLog.job_id == job_id)
            .order_by(JobLog.created_at)
        )
        return list(result.scalars().all())

    async def cancel(self, job_id: UUID) -> bool:
        """Cancel a job if it's in PENDING status.

        Returns True if the job was cancelled, False otherwise.
        """
        result = await self.session.execute(
            delete(Job).where(Job.id == job_id, Job.status == JobStatus.PENDING)
        )
        return result.rowcount > 0
