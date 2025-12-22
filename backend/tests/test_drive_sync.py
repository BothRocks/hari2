# backend/tests/test_drive_sync.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from app.services.jobs.worker import JobWorker
from app.models.job import Job, JobType, JobStatus
from app.models.drive import DriveFolder, DriveFile, DriveFileStatus
from app.models.document import Document, SourceType, ProcessingStatus
from app.services.drive.client import DriveFileInfo


@pytest.mark.asyncio
async def test_sync_drive_folder_creates_pending_files():
    """Test that sync creates DriveFile records with PENDING status for new files."""
    worker = JobWorker()

    # Create mock session and queue
    mock_session = AsyncMock()
    mock_queue = AsyncMock()

    # Setup test data
    folder_id = uuid4()
    job = Job(
        id=uuid4(),
        job_type=JobType.SYNC_DRIVE_FOLDER,
        status=JobStatus.RUNNING,
        payload={"folder_id": str(folder_id)},
    )

    # Mock folder from database
    mock_folder = MagicMock()
    mock_folder.id = folder_id
    mock_folder.google_folder_id = "google_folder_123"
    mock_folder.name = "Test Folder"

    # Mock database queries
    folder_result = MagicMock()
    folder_result.scalar_one_or_none.return_value = mock_folder

    existing_files_result = MagicMock()
    existing_files_result.scalars.return_value.all.return_value = []

    pending_files_result = MagicMock()
    pending_files_result.scalars.return_value.all.return_value = []

    # Configure session.execute to return appropriate results for each query
    call_count = 0
    def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # First call: get folder
            return folder_result
        elif call_count == 2:  # Second call: get existing files
            return existing_files_result
        else:  # Third call: get pending files
            return pending_files_result

    mock_session.execute.side_effect = mock_execute

    # Mock DriveService to return files
    mock_drive_files = [
        DriveFileInfo(
            id="file1",
            name="doc1.pdf",
            mime_type="application/pdf",
            md5_checksum="abc123"
        ),
        DriveFileInfo(
            id="file2",
            name="doc2.pdf",
            mime_type="application/pdf",
            md5_checksum="def456"
        ),
    ]

    with patch("app.services.jobs.worker.DriveService") as MockDriveService, \
         patch("app.services.jobs.worker.AsyncioJobQueue", return_value=mock_queue):
        mock_drive = MagicMock()
        mock_drive.list_files.return_value = mock_drive_files
        MockDriveService.return_value = mock_drive

        # Run the sync
        await worker._sync_drive_folder(job, mock_queue, mock_session)

        # Verify DriveService was called correctly
        MockDriveService.assert_called_once()
        mock_drive.list_files.assert_called_once_with("google_folder_123")

        # Verify new DriveFile records were added
        assert mock_session.add.call_count == 2

        # Get the added files
        added_files = [call[0][0] for call in mock_session.add.call_args_list]

        # Verify first file
        assert isinstance(added_files[0], DriveFile)
        assert added_files[0].google_file_id == "file1"
        assert added_files[0].name == "doc1.pdf"
        assert added_files[0].md5_hash == "abc123"
        assert added_files[0].status == DriveFileStatus.PENDING
        assert added_files[0].folder_id == folder_id

        # Verify second file
        assert isinstance(added_files[1], DriveFile)
        assert added_files[1].google_file_id == "file2"
        assert added_files[1].name == "doc2.pdf"
        assert added_files[1].md5_hash == "def456"
        assert added_files[1].status == DriveFileStatus.PENDING

        # Verify commits were made
        assert mock_session.commit.call_count == 2

        # Verify folder last_sync_at was updated
        assert mock_folder.last_sync_at is not None


@pytest.mark.asyncio
async def test_sync_drive_folder_updates_changed_files():
    """Test that files with changed MD5 hash get status=PENDING."""
    worker = JobWorker()

    # Create mock session and queue
    mock_session = AsyncMock()
    mock_queue = AsyncMock()

    # Setup test data
    folder_id = uuid4()
    job = Job(
        id=uuid4(),
        job_type=JobType.SYNC_DRIVE_FOLDER,
        status=JobStatus.RUNNING,
        payload={"folder_id": str(folder_id)},
    )

    # Mock folder from database
    mock_folder = MagicMock()
    mock_folder.id = folder_id
    mock_folder.google_folder_id = "google_folder_123"

    # Create existing file with old MD5 hash
    existing_file = MagicMock(spec=DriveFile)
    existing_file.google_file_id = "file1"
    existing_file.name = "old_name.pdf"
    existing_file.md5_hash = "old_hash_123"
    existing_file.status = DriveFileStatus.COMPLETED
    existing_file.error_message = "old error"

    # Mock database queries
    folder_result = MagicMock()
    folder_result.scalar_one_or_none.return_value = mock_folder

    existing_files_result = MagicMock()
    existing_files_result.scalars.return_value.all.return_value = [existing_file]

    pending_files_result = MagicMock()
    pending_files_result.scalars.return_value.all.return_value = []

    # Configure session.execute
    call_count = 0
    def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return folder_result
        elif call_count == 2:
            return existing_files_result
        else:
            return pending_files_result

    mock_session.execute.side_effect = mock_execute

    # Mock DriveService to return file with new MD5 hash
    mock_drive_files = [
        DriveFileInfo(
            id="file1",
            name="new_name.pdf",
            mime_type="application/pdf",
            md5_checksum="new_hash_456"
        ),
    ]

    with patch("app.services.jobs.worker.DriveService") as MockDriveService, \
         patch("app.services.jobs.worker.AsyncioJobQueue", return_value=mock_queue):
        mock_drive = MagicMock()
        mock_drive.list_files.return_value = mock_drive_files
        MockDriveService.return_value = mock_drive

        # Run the sync
        await worker._sync_drive_folder(job, mock_queue, mock_session)

        # Verify file was updated
        assert existing_file.md5_hash == "new_hash_456"
        assert existing_file.name == "new_name.pdf"
        assert existing_file.status == DriveFileStatus.PENDING
        assert existing_file.error_message is None

        # Verify no new files were added
        assert mock_session.add.call_count == 0


@pytest.mark.asyncio
async def test_sync_drive_folder_marks_removed_files():
    """Test that files not in Drive anymore get status=REMOVED."""
    worker = JobWorker()

    # Create mock session and queue
    mock_session = AsyncMock()
    mock_queue = AsyncMock()

    # Setup test data
    folder_id = uuid4()
    job = Job(
        id=uuid4(),
        job_type=JobType.SYNC_DRIVE_FOLDER,
        status=JobStatus.RUNNING,
        payload={"folder_id": str(folder_id)},
    )

    # Mock folder
    mock_folder = MagicMock()
    mock_folder.id = folder_id
    mock_folder.google_folder_id = "google_folder_123"

    # Create existing files - one that still exists in Drive, one that was removed
    existing_file_1 = MagicMock(spec=DriveFile)
    existing_file_1.google_file_id = "file1"
    existing_file_1.name = "doc1.pdf"
    existing_file_1.md5_hash = "abc123"  # Same MD5 as in Drive
    existing_file_1.status = DriveFileStatus.COMPLETED

    existing_file_2 = MagicMock(spec=DriveFile)
    existing_file_2.google_file_id = "file2"
    existing_file_2.status = DriveFileStatus.COMPLETED

    # Mock database queries
    folder_result = MagicMock()
    folder_result.scalar_one_or_none.return_value = mock_folder

    existing_files_result = MagicMock()
    existing_files_result.scalars.return_value.all.return_value = [existing_file_1, existing_file_2]

    pending_files_result = MagicMock()
    pending_files_result.scalars.return_value.all.return_value = []

    # Configure session.execute
    call_count = 0
    def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return folder_result
        elif call_count == 2:
            return existing_files_result
        else:
            return pending_files_result

    mock_session.execute.side_effect = mock_execute

    # Mock DriveService to return only one file (file1 still exists, file2 was removed)
    mock_drive_files = [
        DriveFileInfo(
            id="file1",
            name="doc1.pdf",
            mime_type="application/pdf",
            md5_checksum="abc123"
        ),
    ]

    with patch("app.services.jobs.worker.DriveService") as MockDriveService, \
         patch("app.services.jobs.worker.AsyncioJobQueue", return_value=mock_queue):
        mock_drive = MagicMock()
        mock_drive.list_files.return_value = mock_drive_files
        MockDriveService.return_value = mock_drive

        # Run the sync
        await worker._sync_drive_folder(job, mock_queue, mock_session)

        # Verify file1 still has COMPLETED status (no change because MD5 didn't change)
        assert existing_file_1.status == DriveFileStatus.COMPLETED

        # Verify file2 was marked as REMOVED
        assert existing_file_2.status == DriveFileStatus.REMOVED


@pytest.mark.asyncio
async def test_process_drive_file_success():
    """Test successful file processing creates Document and sets COMPLETED status."""
    worker = JobWorker()

    # Create mock session and queue
    mock_session = AsyncMock()
    mock_queue = AsyncMock()

    # Setup test data
    drive_file_id = uuid4()
    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DRIVE_FILE,
        status=JobStatus.RUNNING,
        payload={"drive_file_id": str(drive_file_id)},
    )

    # Mock DriveFile from database
    mock_drive_file = MagicMock(spec=DriveFile)
    mock_drive_file.id = drive_file_id
    mock_drive_file.google_file_id = "google_file_123"
    mock_drive_file.name = "test.pdf"
    mock_drive_file.md5_hash = "abc123"

    # Mock database queries
    drive_file_result = MagicMock()
    drive_file_result.scalar_one_or_none.return_value = mock_drive_file

    duplicate_check_result = MagicMock()
    duplicate_check_result.scalar_one_or_none.return_value = None  # No duplicate

    # Configure session.execute
    call_count = 0
    def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return drive_file_result
        else:
            return duplicate_check_result

    mock_session.execute.side_effect = mock_execute

    # Mock file content
    mock_file_content = b"PDF file content"

    # Mock pipeline result
    mock_pipeline_result = {
        "status": "completed",
        "content": "Extracted text content",
        "content_hash": "sha256_hash_123",
        "title": "Test Document",
        "summary": "Test summary",
        "quick_summary": "Quick summary",
        "keywords": ["keyword1", "keyword2"],
        "industries": ["tech"],
        "language": "en",
        "embedding": [0.1] * 1536,
        "quality_score": 0.85,
        "token_count": 1000,
        "llm_metadata": {"total_cost_usd": 0.05}
    }

    with patch("app.services.jobs.worker.DriveService") as MockDriveService, \
         patch("app.services.jobs.worker.AsyncioJobQueue", return_value=mock_queue), \
         patch("app.services.jobs.worker.DocumentPipeline") as MockPipeline:

        # Mock DriveService
        mock_drive = MagicMock()
        mock_drive.download_file.return_value = mock_file_content
        MockDriveService.return_value = mock_drive

        # Mock DocumentPipeline
        mock_pipeline = MagicMock()
        mock_pipeline.process_pdf = AsyncMock(return_value=mock_pipeline_result)
        MockPipeline.return_value = mock_pipeline

        # Run the processing
        await worker._process_drive_file(job, mock_queue, mock_session)

        # Verify DriveService was called
        mock_drive.download_file.assert_called_once_with("google_file_123")

        # Verify pipeline was called
        mock_pipeline.process_pdf.assert_called_once_with(mock_file_content, filename="test.pdf")

        # Verify Document was created
        assert mock_session.add.call_count == 1
        created_document = mock_session.add.call_args[0][0]
        assert isinstance(created_document, Document)
        assert created_document.source_type == SourceType.DRIVE
        # Title gets updated from pipeline result, not initial file name
        assert created_document.title == "Test Document"
        assert created_document.processing_status == ProcessingStatus.COMPLETED

        # Verify DriveFile status was updated to PROCESSING then COMPLETED
        assert mock_drive_file.status == DriveFileStatus.COMPLETED
        assert mock_drive_file.processed_at is not None
        assert mock_drive_file.document_id == created_document.id

        # Verify commits were made
        assert mock_session.commit.call_count >= 2


@pytest.mark.asyncio
async def test_process_drive_file_duplicate_detection():
    """Test that duplicate content hash links to existing document."""
    worker = JobWorker()

    # Create mock session and queue
    mock_session = AsyncMock()
    mock_queue = AsyncMock()

    # Setup test data
    drive_file_id = uuid4()
    existing_doc_id = uuid4()
    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DRIVE_FILE,
        status=JobStatus.RUNNING,
        payload={"drive_file_id": str(drive_file_id)},
    )

    # Mock DriveFile
    mock_drive_file = MagicMock(spec=DriveFile)
    mock_drive_file.id = drive_file_id
    mock_drive_file.google_file_id = "google_file_123"
    mock_drive_file.name = "duplicate.pdf"
    mock_drive_file.md5_hash = "abc123"

    # Mock existing document (duplicate)
    mock_existing_doc = MagicMock(spec=Document)
    mock_existing_doc.id = existing_doc_id
    mock_existing_doc.content_hash = "duplicate_hash_123"

    # Mock database queries
    drive_file_result = MagicMock()
    drive_file_result.scalar_one_or_none.return_value = mock_drive_file

    duplicate_check_result = MagicMock()
    duplicate_check_result.scalar_one_or_none.return_value = mock_existing_doc

    # Configure session.execute
    call_count = 0
    def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return drive_file_result
        else:
            return duplicate_check_result

    mock_session.execute.side_effect = mock_execute

    # Mock file content
    mock_file_content = b"Duplicate PDF file content"

    with patch("app.services.jobs.worker.DriveService") as MockDriveService, \
         patch("app.services.jobs.worker.AsyncioJobQueue", return_value=mock_queue):

        # Mock DriveService
        mock_drive = MagicMock()
        mock_drive.download_file.return_value = mock_file_content
        MockDriveService.return_value = mock_drive

        # Run the processing
        await worker._process_drive_file(job, mock_queue, mock_session)

        # Verify file was downloaded
        mock_drive.download_file.assert_called_once_with("google_file_123")

        # Verify no new Document was created
        assert mock_session.add.call_count == 0

        # Verify DriveFile was linked to existing document
        assert mock_drive_file.document_id == existing_doc_id
        assert mock_drive_file.status == DriveFileStatus.COMPLETED
        assert mock_drive_file.processed_at is not None

        # Verify log message about duplicate
        log_calls = [call for call in mock_queue.log.call_args_list if "Duplicate detected" in str(call)]
        assert len(log_calls) > 0


@pytest.mark.asyncio
async def test_process_drive_file_google_doc_export():
    """Test that Google Docs (no MD5) are exported as PDF."""
    worker = JobWorker()

    # Create mock session and queue
    mock_session = AsyncMock()
    mock_queue = AsyncMock()

    # Setup test data
    drive_file_id = uuid4()
    job = Job(
        id=uuid4(),
        job_type=JobType.PROCESS_DRIVE_FILE,
        status=JobStatus.RUNNING,
        payload={"drive_file_id": str(drive_file_id)},
    )

    # Mock DriveFile (Google Doc has no md5_hash)
    mock_drive_file = MagicMock(spec=DriveFile)
    mock_drive_file.id = drive_file_id
    mock_drive_file.google_file_id = "google_doc_123"
    mock_drive_file.name = "test.gdoc"
    mock_drive_file.md5_hash = None  # Google Docs don't have MD5

    # Mock database queries
    drive_file_result = MagicMock()
    drive_file_result.scalar_one_or_none.return_value = mock_drive_file

    duplicate_check_result = MagicMock()
    duplicate_check_result.scalar_one_or_none.return_value = None

    # Configure session.execute
    call_count = 0
    def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return drive_file_result
        else:
            return duplicate_check_result

    mock_session.execute.side_effect = mock_execute

    # Mock exported content
    mock_exported_content = b"Exported PDF content"

    # Mock pipeline result
    mock_pipeline_result = {
        "status": "completed",
        "content": "Extracted content",
        "content_hash": "hash123",
        "title": "Test Google Doc",
    }

    with patch("app.services.jobs.worker.DriveService") as MockDriveService, \
         patch("app.services.jobs.worker.AsyncioJobQueue", return_value=mock_queue), \
         patch("app.services.jobs.worker.DocumentPipeline") as MockPipeline:

        # Mock DriveService
        mock_drive = MagicMock()
        mock_drive.export_google_doc.return_value = mock_exported_content
        MockDriveService.return_value = mock_drive

        # Mock DocumentPipeline
        mock_pipeline = MagicMock()
        mock_pipeline.process_pdf = AsyncMock(return_value=mock_pipeline_result)
        MockPipeline.return_value = mock_pipeline

        # Run the processing
        await worker._process_drive_file(job, mock_queue, mock_session)

        # Verify export_google_doc was called (not download_file)
        mock_drive.export_google_doc.assert_called_once_with("google_doc_123", mime_type='application/pdf')
        mock_drive.download_file.assert_not_called()

        # Verify pipeline processed the exported content
        mock_pipeline.process_pdf.assert_called_once_with(mock_exported_content, filename="test.gdoc")
