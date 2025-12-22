"""Scheduler for periodic Drive folder syncs."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.drive import DriveFolder
from app.models.job import JobType
from app.services.jobs.queue import AsyncioJobQueue

logger = logging.getLogger(__name__)


class DriveSyncScheduler:
    """Scheduler for periodic Drive folder syncs."""

    def __init__(self):
        self.running = False
        self.interval_minutes = settings.drive_sync_interval_minutes

    async def start(self) -> None:
        """Start the scheduler loop."""
        self.running = True
        logger.info(f"Drive sync scheduler started (interval: {self.interval_minutes} minutes)")

        while self.running:
            try:
                await self._check_and_sync_folders()
            except Exception as e:
                logger.exception(f"Error in scheduler loop: {e}")

            # Sleep in 1-second intervals for responsive shutdown
            sleep_seconds = self.interval_minutes * 60
            for _ in range(sleep_seconds):
                if not self.running:
                    break
                await asyncio.sleep(1)

    async def _check_and_sync_folders(self) -> None:
        """Check for folders needing sync and create jobs."""
        async with async_session_factory() as session:
            from app.models.job import Job, JobStatus

            # Find active folders not synced within interval
            threshold = datetime.now(timezone.utc) - timedelta(minutes=self.interval_minutes)

            result = await session.execute(
                select(DriveFolder).where(
                    DriveFolder.is_active == True,
                    (DriveFolder.last_sync_at == None) | (DriveFolder.last_sync_at < threshold),
                )
            )
            folders = result.scalars().all()

            if folders:
                logger.info(f"Found {len(folders)} folders due for sync")
                queue = AsyncioJobQueue(session)
                jobs_created = 0

                for folder in folders:
                    # Check for existing pending/running job for this folder
                    existing_job = await session.execute(
                        select(Job).where(
                            Job.job_type == JobType.SYNC_DRIVE_FOLDER,
                            Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
                        )
                    )
                    # Filter by payload (JSONB comparison)
                    existing = [j for j in existing_job.scalars().all()
                               if j.payload.get("folder_id") == str(folder.id)]

                    if existing:
                        logger.info(f"Skipping folder {folder.name} - sync job already pending/running")
                        continue

                    await queue.enqueue(
                        job_type=JobType.SYNC_DRIVE_FOLDER,
                        payload={"folder_id": str(folder.id)},
                    )
                    jobs_created += 1
                    logger.info(f"Created sync job for folder: {folder.name}")

                if jobs_created > 0:
                    await session.commit()
                    logger.info(f"Created {jobs_created} sync jobs")

    def stop(self) -> None:
        """Stop the scheduler loop."""
        self.running = False
        logger.info("Drive sync scheduler stopped")
