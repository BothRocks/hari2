#!/usr/bin/env python3
"""Standalone worker script for systemd service."""
import asyncio
import signal
from app.services.jobs.worker import JobWorker
from app.services.jobs.scheduler import DriveSyncScheduler


async def main():
    worker = JobWorker()
    scheduler = DriveSyncScheduler()

    # Handle graceful shutdown
    def shutdown_handler(sig, frame):
        worker.stop()
        scheduler.stop()

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Recover orphaned jobs and start both worker and scheduler
    await worker.recover_orphaned_jobs()

    # Run worker and scheduler concurrently
    await asyncio.gather(
        worker.run(),
        scheduler.start(),
    )


if __name__ == "__main__":
    asyncio.run(main())
