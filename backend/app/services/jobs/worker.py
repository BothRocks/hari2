"""Background worker for processing jobs."""
import asyncio
import traceback
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.document import Document, SourceType, ProcessingStatus
from app.models.drive import DriveFolder, DriveFile, DriveFileStatus
from app.models.job import Job, JobStatus, JobType, LogLevel
from app.services.drive.client import DriveService
from app.services.jobs.queue import AsyncioJobQueue
from app.services.pipeline.orchestrator import DocumentPipeline


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
        url = job.payload.get("url")
        document_id = job.payload.get("document_id")
        is_reprocess = job.payload.get("reprocess", False)

        if not url and not document_id:
            raise ValueError("Payload must contain either 'url' or 'document_id'")

        await queue.log(
            job.id,
            LogLevel.INFO,
            "Starting document processing",
            {"url": url, "document_id": str(document_id) if document_id else None, "reprocess": is_reprocess}
        )

        if document_id:
            # Get existing document
            result = await session.execute(
                select(Document).where(Document.id == UUID(document_id))
            )
            document = result.scalar_one_or_none()
            if not document:
                raise ValueError(f"Document {document_id} not found")

            # Reset status
            document.processing_status = ProcessingStatus.PROCESSING
            await session.commit()

            # Process based on source type
            pipeline = DocumentPipeline()

            if document.source_type == SourceType.URL and document.url:
                # URL document - use URL pipeline (handles both HTML and PDF URLs)
                pipeline_result = await pipeline.process_url(document.url)

            elif document.source_type == SourceType.DRIVE and document.drive_file_id:
                # Drive document - download from Drive and process as PDF
                await queue.log(job.id, LogLevel.INFO, f"Downloading from Drive: {document.drive_file_id}")
                drive_service = DriveService(settings.google_service_account_json)
                file_content = drive_service.download_file(document.drive_file_id)

                if file_content is None:
                    pipeline_result = {"status": "failed", "error": "Failed to download file from Drive"}
                else:
                    pipeline_result = await pipeline.process_pdf(file_content, filename=document.title or "")

            elif document.source_type == SourceType.PDF:
                # PDF document without Drive - can't reprocess without original content
                pipeline_result = {"status": "failed", "error": "Cannot process PDF document without file content"}

            else:
                pipeline_result = {"status": "failed", "error": f"Cannot process document with source_type {document.source_type}"}

            if pipeline_result.get("status") == "failed":
                document.processing_status = ProcessingStatus.FAILED
                document.error_message = pipeline_result.get("error")
            else:
                document.processing_status = ProcessingStatus.COMPLETED
                document.content = pipeline_result.get("content")
                document.content_hash = pipeline_result.get("content_hash")
                document.title = pipeline_result.get("title") or document.title
                document.author = pipeline_result.get("author")
                document.summary = pipeline_result.get("summary")
                document.quick_summary = pipeline_result.get("quick_summary")
                document.keywords = pipeline_result.get("keywords")
                document.industries = pipeline_result.get("industries")
                document.language = pipeline_result.get("language")
                document.embedding = pipeline_result.get("embedding")
                document.quality_score = pipeline_result.get("quality_score")
                document.token_count = pipeline_result.get("token_count")
                document.needs_review = pipeline_result.get("needs_review", False)
                document.review_reasons = pipeline_result.get("review_reasons")
                document.original_metadata = pipeline_result.get("original_metadata")
                # Calculate processing cost if available
                llm_metadata = pipeline_result.get("llm_metadata", {})
                if llm_metadata.get("total_cost_usd"):
                    document.processing_cost_usd = llm_metadata["total_cost_usd"]
                # Clear previous review if reprocessing
                if is_reprocess:
                    document.reviewed_at = None
                    document.reviewed_by_id = None
                document.error_message = None

            await session.commit()
            await queue.log(job.id, LogLevel.INFO, "Document processing completed")
        else:
            # Legacy: URL provided directly in payload (not via document record)
            await queue.log(job.id, LogLevel.INFO, "Legacy URL processing - no document_id provided")

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
        """Sync a Google Drive folder."""
        # Validate payload
        folder_id = job.payload.get("folder_id")
        if not folder_id:
            raise ValueError("Payload must contain 'folder_id'")

        await queue.log(job.id, LogLevel.INFO, f"Starting sync for folder {folder_id}")

        # Get folder from database
        result = await session.execute(
            select(DriveFolder).where(DriveFolder.id == UUID(folder_id))
        )
        folder = result.scalar_one_or_none()
        if not folder:
            raise ValueError(f"Folder {folder_id} not found")

        # Initialize Drive service
        drive_service = DriveService(settings.google_service_account_json)

        # List files from Google Drive
        await queue.log(job.id, LogLevel.INFO, f"Listing files from Drive folder {folder.google_folder_id}")
        drive_files = drive_service.list_files(folder.google_folder_id)
        await queue.log(job.id, LogLevel.INFO, f"Found {len(drive_files)} files in Drive")

        # Get existing DriveFile records
        result = await session.execute(
            select(DriveFile).where(DriveFile.folder_id == folder.id)
        )
        existing_files = {f.google_file_id: f for f in result.scalars().all()}

        # Track which files are still in Drive
        current_file_ids = set()

        # Process each file from Drive
        files_created = 0
        files_updated = 0

        for drive_file in drive_files:
            current_file_ids.add(drive_file.id)
            existing_file = existing_files.get(drive_file.id)

            if existing_file is None:
                # New file - create record with unique constraint check
                new_file = DriveFile(
                    folder_id=folder.id,
                    google_file_id=drive_file.id,
                    name=drive_file.name,
                    md5_hash=drive_file.md5_checksum,
                    status=DriveFileStatus.PENDING,
                )
                session.add(new_file)
                try:
                    await session.flush()  # Trigger constraint check
                    files_created += 1
                except IntegrityError:
                    # File already exists (concurrent sync) - rollback and skip
                    await session.rollback()
                    # Re-query to get the existing file
                    result = await session.execute(
                        select(DriveFile).where(
                            DriveFile.folder_id == folder.id,
                            DriveFile.google_file_id == drive_file.id
                        )
                    )
                    existing_file = result.scalar_one_or_none()
                    if existing_file:
                        existing_files[drive_file.id] = existing_file

            # Check if file has changed (only if we have an existing_file)
            if existing_file and drive_file.md5_checksum and existing_file.md5_hash != drive_file.md5_checksum:
                # File modified - update and mark for reprocessing
                existing_file.md5_hash = drive_file.md5_checksum
                existing_file.name = drive_file.name
                existing_file.status = DriveFileStatus.PENDING
                existing_file.error_message = None
                files_updated += 1

        # Mark removed files
        files_removed = 0
        for file_id, existing_file in existing_files.items():
            if file_id not in current_file_ids and existing_file.status != DriveFileStatus.REMOVED:
                existing_file.status = DriveFileStatus.REMOVED
                files_removed += 1

        # Update folder last_sync_at
        folder.last_sync_at = datetime.now(timezone.utc)
        await session.commit()

        await queue.log(
            job.id,
            LogLevel.INFO,
            f"Sync complete: {files_created} created, {files_updated} updated, {files_removed} removed"
        )

        # Check if we should process files (defaults to True for backward compatibility)
        process_files = job.payload.get("process_files", True)

        if process_files:
            # Create PROCESS_DRIVE_FILE jobs for all pending files
            result = await session.execute(
                select(DriveFile).where(
                    DriveFile.folder_id == folder.id,
                    DriveFile.status == DriveFileStatus.PENDING
                )
            )
            pending_files = result.scalars().all()

            jobs_created = 0
            for drive_file in pending_files:
                await queue.enqueue(
                    job_type=JobType.PROCESS_DRIVE_FILE,
                    payload={"drive_file_id": str(drive_file.id)},
                    created_by_id=job.created_by_id,
                    parent_job_id=job.id,
                )
                jobs_created += 1

            await session.commit()
            await queue.log(job.id, LogLevel.INFO, f"Created {jobs_created} processing jobs for pending files")
        else:
            await queue.log(job.id, LogLevel.INFO, "Skipping file processing (sync only mode)")

    async def _process_drive_file(self, job: Job, queue: AsyncioJobQueue, session: AsyncSession) -> None:
        """Process a file from Google Drive."""
        # Validate payload
        drive_file_id = job.payload.get("drive_file_id")
        if not drive_file_id:
            raise ValueError("Payload must contain 'drive_file_id'")

        await queue.log(job.id, LogLevel.INFO, f"Starting processing for Drive file {drive_file_id}")

        # Get DriveFile record
        result = await session.execute(
            select(DriveFile).where(DriveFile.id == UUID(drive_file_id))
        )
        drive_file = result.scalar_one_or_none()
        if not drive_file:
            raise ValueError(f"DriveFile {drive_file_id} not found")

        # Update status to PROCESSING
        drive_file.status = DriveFileStatus.PROCESSING
        await session.commit()

        try:
            # Initialize Drive service
            drive_service = DriveService(settings.google_service_account_json)

            # Download file content
            await queue.log(job.id, LogLevel.INFO, f"Downloading file from Drive: {drive_file.name}")

            # Check if it's a Google Doc (need to export) or regular file (download)
            # We can infer from the presence of md5_hash - Google Docs don't have it
            if drive_file.md5_hash is None:
                # Google Doc - export as PDF
                file_content = drive_service.export_google_doc(drive_file.google_file_id, mime_type='application/pdf')
            else:
                # Regular file (PDF) - download directly
                file_content = drive_service.download_file(drive_file.google_file_id)

            if file_content is None:
                raise ValueError("Failed to download file content")

            # Create Document record with Drive view URL
            drive_view_url = f"https://drive.google.com/file/d/{drive_file.google_file_id}/view"
            document = Document(
                source_type=SourceType.DRIVE,
                url=drive_view_url,
                title=drive_file.name,
                processing_status=ProcessingStatus.PROCESSING,
            )
            session.add(document)
            await session.commit()  # Commit to get document.id

            await queue.log(job.id, LogLevel.INFO, f"Created document {document.id}, starting pipeline")

            # Run processing pipeline
            pipeline = DocumentPipeline()
            pipeline_result = await pipeline.process_pdf(file_content, filename=drive_file.name)

            if pipeline_result.get("status") == "failed":
                raise ValueError(f"Pipeline failed: {pipeline_result.get('error')}")

            # Update document with pipeline results
            document.content = pipeline_result.get("content")
            document.content_hash = pipeline_result.get("content_hash")
            document.title = pipeline_result.get("title") or drive_file.name
            document.summary = pipeline_result.get("summary")
            document.quick_summary = pipeline_result.get("quick_summary")
            document.keywords = pipeline_result.get("keywords")
            document.industries = pipeline_result.get("industries")
            document.language = pipeline_result.get("language")
            document.embedding = pipeline_result.get("embedding")
            document.quality_score = pipeline_result.get("quality_score")
            document.token_count = pipeline_result.get("token_count")
            document.processing_status = ProcessingStatus.COMPLETED

            # Calculate processing cost if available
            llm_metadata = pipeline_result.get("llm_metadata", {})
            if llm_metadata.get("total_cost_usd"):
                document.processing_cost_usd = llm_metadata["total_cost_usd"]

            # Check for duplicate AFTER pipeline processing (using content_hash from cleaned text)
            content_hash = pipeline_result.get("content_hash")
            if content_hash:
                result = await session.execute(
                    select(Document).where(
                        Document.content_hash == content_hash,
                        Document.id != document.id  # Exclude the just-created document
                    )
                )
                existing_doc = result.scalar_one_or_none()

                if existing_doc:
                    await queue.log(
                        job.id,
                        LogLevel.INFO,
                        f"Duplicate detected - content matches document {existing_doc.id}, linking and removing duplicate"
                    )
                    # Link to existing document
                    drive_file.document_id = existing_doc.id
                    drive_file.status = DriveFileStatus.COMPLETED
                    drive_file.processed_at = datetime.now(timezone.utc)

                    # Delete the duplicate document we just created
                    await session.delete(document)
                    await session.commit()
                    return

            # No duplicate - update DriveFile to link to new document
            drive_file.document_id = document.id
            drive_file.status = DriveFileStatus.COMPLETED
            drive_file.processed_at = datetime.now(timezone.utc)

            await session.commit()
            await queue.log(job.id, LogLevel.INFO, f"Processing complete - document {document.id}")

        except Exception as e:
            # Mark as failed and store error (truncate to avoid database errors)
            drive_file.status = DriveFileStatus.FAILED
            drive_file.error_message = str(e)[:2000]
            await session.commit()
            raise  # Re-raise to be caught by process_job error handler

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
