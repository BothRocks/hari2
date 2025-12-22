"""Background worker for processing jobs."""
import asyncio
import traceback
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.job import Job, JobStatus, JobType, LogLevel
from app.services.jobs.queue import AsyncioJobQueue


class JobWorker:
    """Background worker that processes jobs from the queue."""

    def __init__(self, poll_interval: int = 5):
        """Initialize the job worker.

        Args:
            poll_interval: Seconds to wait between polling for jobs (default: 5)
        """
        self.running = False
        self.poll_interval = poll_interval

    async def process_job(self, job: Job, session: AsyncSession) -> None:
        """Process a single job based on its type."""
        queue = AsyncioJobQueue(session)

        try:
            if job.job_type == JobType.PROCESS_DOCUMENT:
                await self._process_document(job, queue, session)
            elif job.job_type == JobType.PROCESS_BATCH:
                await self._process_batch(job, queue, session)
            elif job.job_type == JobType.SYNC_DRIVE_FOLDER:
                await self._sync_drive_folder(job, queue, session)
            elif job.job_type == JobType.PROCESS_DRIVE_FILE:
                await self._process_drive_file(job, queue, session)
            else:
                await queue.log(job.id, LogLevel.ERROR, f"Unknown job type: {job.job_type}")
                await queue.update_status(job.id, JobStatus.FAILED, completed_at=datetime.now(timezone.utc))
                await session.commit()
                return

            await queue.update_status(job.id, JobStatus.COMPLETED, completed_at=datetime.now(timezone.utc))
            await session.commit()

        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()[-2000:],
            }
            await queue.log(job.id, LogLevel.ERROR, f"Job failed: {e}", error_details)
            await queue.update_status(job.id, JobStatus.FAILED, completed_at=datetime.now(timezone.utc))
            await session.commit()

    async def _process_document(self, job: Job, queue: AsyncioJobQueue, session: AsyncSession) -> None:
        """Process a single document."""
        # Validate payload
        url = job.payload.get("url")
        document_id = job.payload.get("document_id")

        if not url and not document_id:
            raise ValueError("Payload must contain either 'url' or 'document_id'")

        await queue.log(
            job.id,
            LogLevel.INFO,
            "Starting document processing",
            {"url": url, "document_id": str(document_id) if document_id else None}
        )
        # Placeholder - actual processing will use pipeline.orchestrator
        await queue.log(job.id, LogLevel.INFO, "Document processing completed")

    async def _process_batch(self, job: Job, queue: AsyncioJobQueue, session: AsyncSession) -> None:
        """Process multiple documents by creating child jobs."""
        # Validate payload
        urls = job.payload.get("urls")

        if not urls:
            raise ValueError("Payload must contain 'urls' field")

        if not isinstance(urls, list):
            raise ValueError("'urls' field must be a list")

        if len(urls) == 0:
            raise ValueError("'urls' list cannot be empty")

        await queue.log(job.id, LogLevel.INFO, f"Creating {len(urls)} child jobs")

        for url in urls:
            child_job_id = await queue.enqueue(
                job_type=JobType.PROCESS_DOCUMENT,
                payload={"url": url},
                created_by_id=job.created_by_id,
                parent_job_id=job.id,
            )
            await queue.log(
                job.id,
                LogLevel.INFO,
                "Created child job",
                {"child_job_id": str(child_job_id), "url": url}
            )

    async def _sync_drive_folder(self, job: Job, queue: AsyncioJobQueue, session: AsyncSession) -> None:
        """Sync a Google Drive folder - placeholder."""
        await queue.log(job.id, LogLevel.INFO, "Drive sync not yet implemented")

    async def _process_drive_file(self, job: Job, queue: AsyncioJobQueue, session: AsyncSession) -> None:
        """Process a file from Google Drive - placeholder."""
        await queue.log(job.id, LogLevel.INFO, "Drive file processing not yet implemented")

    async def run(self) -> None:
        """Main worker loop - polls for pending jobs."""
        self.running = True

        # Crash recovery on startup
        await self.recover_orphaned_jobs()

        while self.running:
            async with async_session_factory() as session:
                queue = AsyncioJobQueue(session)
                jobs = await queue.get_pending_jobs(limit=1)

                for job in jobs:
                    # Claim the job atomically
                    await queue.update_status(job.id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
                    await queue.log(job.id, LogLevel.INFO, "Job started")
                    await session.commit()

                    # Process in separate try block so status updates are preserved
                    try:
                        await self.process_job(job, session)
                    except Exception:
                        # process_job handles its own errors and commits
                        pass

            await asyncio.sleep(self.poll_interval)

    async def recover_orphaned_jobs(self) -> None:
        """Mark jobs that were running when server crashed as failed."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(Job).where(Job.status == JobStatus.RUNNING)
            )
            orphaned_jobs = result.scalars().all()

            for job in orphaned_jobs:
                queue = AsyncioJobQueue(session)
                await queue.log(job.id, LogLevel.ERROR, "Server restarted during processing - job marked as failed")
                await queue.update_status(job.id, JobStatus.FAILED, completed_at=datetime.now(timezone.utc))

            await session.commit()

    def stop(self) -> None:
        """Stop the worker loop."""
        self.running = False
