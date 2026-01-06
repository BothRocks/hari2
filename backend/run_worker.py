#!/usr/bin/env python3
"""Standalone worker script for systemd service."""
import asyncio
from app.services.jobs.worker import JobWorker


async def main():
    worker = JobWorker()
    await worker.recover_orphaned_jobs()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
