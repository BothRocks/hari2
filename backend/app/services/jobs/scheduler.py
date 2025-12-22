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

            await asyncio.sleep(self.interval_minutes * 60)

    async def _check_and_sync_folders(self) -> None:
        """Check for folders needing sync and create jobs."""
        async with async_session_factory() as session:
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
                for folder in folders:
                    await queue.enqueue(
                        job_type=JobType.SYNC_DRIVE_FOLDER,
                        payload={"folder_id": str(folder.id)},
                    )
                    logger.info(f"Created sync job for folder: {folder.name}")
                await session.commit()

    def stop(self) -> None:
        """Stop the scheduler loop."""
        self.running = False
        logger.info("Drive sync scheduler stopped")
