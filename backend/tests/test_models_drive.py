"""Tests for DriveFolder and DriveFile models."""
from uuid import uuid4
from datetime import datetime, timezone

from app.models.drive import DriveFolder, DriveFile, DriveFileStatus


def test_drive_file_status_enum():
    """Test DriveFileStatus enum values."""
    assert DriveFileStatus.PENDING == "pending"
    assert DriveFileStatus.PROCESSING == "processing"
    assert DriveFileStatus.COMPLETED == "completed"
    assert DriveFileStatus.FAILED == "failed"
    assert DriveFileStatus.REMOVED == "removed"


def test_drive_folder_has_required_fields():
    """Test DriveFolder model has all required fields."""
    assert hasattr(DriveFolder, 'id')
    assert hasattr(DriveFolder, 'google_folder_id')
    assert hasattr(DriveFolder, 'name')
    assert hasattr(DriveFolder, 'owner_id')
    assert hasattr(DriveFolder, 'is_active')
    assert hasattr(DriveFolder, 'last_sync_at')
    assert hasattr(DriveFolder, 'created_at')
    assert hasattr(DriveFolder, 'updated_at')


def test_drive_folder_model_can_be_instantiated():
    """Test DriveFolder model can be instantiated with minimal fields."""
    owner_id = uuid4()
    folder = DriveFolder(
        google_folder_id="1234567890abcdef",
        name="My Documents",
        owner_id=owner_id
    )
    assert folder.google_folder_id == "1234567890abcdef"
    assert folder.name == "My Documents"
    assert folder.owner_id == owner_id


def test_drive_folder_is_active_can_be_true():
    """Test DriveFolder is_active can be set to True."""
    owner_id = uuid4()
    folder = DriveFolder(
        google_folder_id="1234567890abcdef",
        name="My Documents",
        owner_id=owner_id,
        is_active=True
    )
    assert folder.is_active is True


def test_drive_folder_can_be_deactivated():
    """Test DriveFolder can be deactivated."""
    owner_id = uuid4()
    folder = DriveFolder(
        google_folder_id="1234567890abcdef",
        name="My Documents",
        owner_id=owner_id,
        is_active=False
    )
    assert folder.is_active is False


def test_drive_folder_last_sync_at_can_be_set():
    """Test DriveFolder last_sync_at can be set."""
    owner_id = uuid4()
    folder = DriveFolder(
        google_folder_id="1234567890abcdef",
        name="My Documents",
        owner_id=owner_id
    )
    now = datetime.now(timezone.utc)
    folder.last_sync_at = now
    assert folder.last_sync_at == now


def test_drive_file_has_required_fields():
    """Test DriveFile model has all required fields."""
    assert hasattr(DriveFile, 'id')
    assert hasattr(DriveFile, 'folder_id')
    assert hasattr(DriveFile, 'google_file_id')
    assert hasattr(DriveFile, 'name')
    assert hasattr(DriveFile, 'md5_hash')
    assert hasattr(DriveFile, 'status')
    assert hasattr(DriveFile, 'document_id')
    assert hasattr(DriveFile, 'error_message')
    assert hasattr(DriveFile, 'created_at')
    assert hasattr(DriveFile, 'updated_at')
    assert hasattr(DriveFile, 'processed_at')


def test_drive_file_model_can_be_instantiated():
    """Test DriveFile model can be instantiated with minimal fields."""
    folder_id = uuid4()
    file = DriveFile(
        folder_id=folder_id,
        google_file_id="file123abc",
        name="document.pdf",
        status=DriveFileStatus.PENDING
    )
    assert file.folder_id == folder_id
    assert file.google_file_id == "file123abc"
    assert file.name == "document.pdf"
    assert file.status == DriveFileStatus.PENDING


def test_drive_file_with_md5_hash():
    """Test DriveFile model can have md5_hash."""
    folder_id = uuid4()
    file = DriveFile(
        folder_id=folder_id,
        google_file_id="file123abc",
        name="document.pdf",
        status=DriveFileStatus.PENDING,
        md5_hash="5d41402abc4b2a76b9719d911017c592"
    )
    assert file.md5_hash == "5d41402abc4b2a76b9719d911017c592"


def test_drive_file_with_document_reference():
    """Test DriveFile model can have a document reference."""
    folder_id = uuid4()
    document_id = uuid4()
    file = DriveFile(
        folder_id=folder_id,
        google_file_id="file123abc",
        name="document.pdf",
        status=DriveFileStatus.COMPLETED,
        document_id=document_id
    )
    assert file.document_id == document_id


def test_drive_file_status_can_be_set():
    """Test DriveFile status can be set to different values."""
    folder_id = uuid4()
    file = DriveFile(
        folder_id=folder_id,
        google_file_id="file123abc",
        name="document.pdf",
        status=DriveFileStatus.PENDING
    )

    file.status = DriveFileStatus.PROCESSING
    assert file.status == DriveFileStatus.PROCESSING

    file.status = DriveFileStatus.COMPLETED
    assert file.status == DriveFileStatus.COMPLETED

    file.status = DriveFileStatus.FAILED
    assert file.status == DriveFileStatus.FAILED

    file.status = DriveFileStatus.REMOVED
    assert file.status == DriveFileStatus.REMOVED


def test_drive_file_with_error_message():
    """Test DriveFile model can have error_message."""
    folder_id = uuid4()
    file = DriveFile(
        folder_id=folder_id,
        google_file_id="file123abc",
        name="document.pdf",
        status=DriveFileStatus.FAILED,
        error_message="Failed to download file from Drive"
    )
    assert file.error_message == "Failed to download file from Drive"


def test_drive_file_processed_at_can_be_set():
    """Test DriveFile processed_at can be set."""
    folder_id = uuid4()
    file = DriveFile(
        folder_id=folder_id,
        google_file_id="file123abc",
        name="document.pdf",
        status=DriveFileStatus.COMPLETED
    )
    now = datetime.now(timezone.utc)
    file.processed_at = now
    assert file.processed_at == now
