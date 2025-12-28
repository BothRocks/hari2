# backend/app/integrations/bot_base.py
"""Abstract base class for chat platform bots."""
import logging
from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document, SourceType
from app.models.job import Job, JobStatus, JobType
from app.services.drive.client import DriveService
from app.services.jobs.queue import AsyncioJobQueue
from app.core.config import settings
from app.integrations.user_state import set_last_upload, get_last_upload

logger = logging.getLogger(__name__)


class BotBase(ABC):
    """Abstract base for chat platform integrations.

    Handles document uploads (PDF/URL) and status checks.
    Subclasses implement platform-specific webhook handling.
    """

    platform: str = "unknown"  # Override in subclass: "telegram" or "slack"

    def __init__(self, db: AsyncSession, drive_service: DriveService | None = None):
        self.db = db
        self.drive_service = drive_service

    async def handle_file(self, user_id: str, file_bytes: bytes, filename: str) -> str:
        """Handle uploaded file (PDF).

        Flow: Upload to Drive (archive) → Create HARI document → Return status.
        """
        # Check if Drive is configured for uploads
        if not settings.drive_uploads_folder_id:
            return "PDF uploads are not configured. Please contact an administrator."

        if not self.drive_service:
            return "Drive service is not available. Please contact an administrator."

        try:
            # Upload to Drive for archival
            drive_file_id = self.drive_service.upload_file(
                file_content=file_bytes,
                filename=filename,
                folder_id=settings.drive_uploads_folder_id,
            )

            if not drive_file_id:
                return "Failed to upload file to Drive. Please try again."

            # Create document record
            document = Document(
                source_type=SourceType.DRIVE,
                drive_file_id=drive_file_id,
                title=filename,
            )
            self.db.add(document)
            await self.db.flush()

            # Create processing job
            job_queue = AsyncioJobQueue(self.db)
            job_id = await job_queue.enqueue(
                job_type=JobType.PROCESS_DOCUMENT,
                payload={"document_id": str(document.id)},
            )

            # Track for status checks
            set_last_upload(self.platform, user_id, job_id, filename)

            await self.db.commit()

            return (
                f"Document uploaded!\n"
                f"File: {filename}\n"
                f"Job ID: {job_id}\n"
                f"Status: PROCESSING\n\n"
                f"Reply 'status' to check progress."
            )

        except Exception as e:
            logger.exception(f"Error handling file upload from {self.platform}:{user_id}")
            await self.db.rollback()
            return f"Error uploading file: {str(e)}"

    async def handle_url(self, user_id: str, url: str) -> str:
        """Handle URL submission.

        Flow: Create HARI document directly → Return status.
        """
        try:
            # Create document record
            document = Document(
                url=url,
                source_type=SourceType.URL,
            )
            self.db.add(document)
            await self.db.flush()

            # Create processing job
            job_queue = AsyncioJobQueue(self.db)
            job_id = await job_queue.enqueue(
                job_type=JobType.PROCESS_DOCUMENT,
                payload={"document_id": str(document.id)},
            )

            # Track for status checks
            set_last_upload(self.platform, user_id, job_id, url)

            await self.db.commit()

            return (
                f"URL submitted!\n"
                f"URL: {url}\n"
                f"Job ID: {job_id}\n"
                f"Status: PROCESSING\n\n"
                f"Reply 'status' to check progress."
            )

        except Exception as e:
            logger.exception(f"Error handling URL from {self.platform}:{user_id}")
            await self.db.rollback()
            return f"Error processing URL: {str(e)}"

    async def handle_status(self, user_id: str) -> str:
        """Handle status request for last upload."""
        last_upload = get_last_upload(self.platform, user_id)

        if not last_upload:
            return "No recent uploads found. Send me a PDF or URL first!"

        try:
            # Fetch job status
            result = await self.db.execute(
                select(Job).where(Job.id == last_upload.job_id)
            )
            job = result.scalar_one_or_none()

            if not job:
                return f"Could not find job {last_upload.job_id}"

            status_emoji = {
                JobStatus.PENDING: "⏳",
                JobStatus.RUNNING: "🔄",
                JobStatus.COMPLETED: "✅",
                JobStatus.FAILED: "❌",
            }.get(job.status, "❓")

            response = (
                f"{status_emoji} {last_upload.filename}\n"
                f"Status: {job.status.value}"
            )

            # Add quality score if completed
            if job.status == JobStatus.COMPLETED and job.payload:
                doc_id = job.payload.get("document_id")
                if doc_id:
                    doc_result = await self.db.execute(
                        select(Document).where(Document.id == UUID(doc_id))
                    )
                    doc = doc_result.scalar_one_or_none()
                    if doc and doc.quality_score is not None:
                        response += f"\nQuality Score: {doc.quality_score:.0f}"

            # Add error if failed
            if job.status == JobStatus.FAILED and job.error_message:
                response += f"\nError: {job.error_message}"

            return response

        except Exception as e:
            logger.exception(f"Error checking status for {self.platform}:{user_id}")
            return f"Error checking status: {str(e)}"

    def handle_help(self) -> str:
        """Return help message."""
        return (
            "I can help you add documents to the knowledge base.\n\n"
            "Send me:\n"
            "• A PDF file to upload\n"
            "• A URL to a webpage or document\n"
            "• 'status' to check your last upload\n"
        )

    def is_url(self, text: str) -> bool:
        """Check if text looks like a URL."""
        text = text.strip().lower()
        return text.startswith("http://") or text.startswith("https://")

    def is_status_request(self, text: str) -> bool:
        """Check if text is a status request."""
        text = text.strip().lower()
        return text in ("status", "/status")
