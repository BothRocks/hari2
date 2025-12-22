import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID
from datetime import datetime

from app.models.drive import DriveFolder, DriveFile, DriveFileStatus
from app.models.user import User, UserRole


def test_drive_router_exists():
    """Test that the drive router exists and has correct config."""
    from app.api.drive import router
    assert router is not None
    assert router.prefix == "/admin/drive"
    assert "admin" in router.tags


@pytest.mark.asyncio
async def test_list_drive_folders():
    """Test listing drive folders."""
    from app.api.drive import list_drive_folders
    from sqlalchemy.ext.asyncio import AsyncSession

    # Create mock folders
    folder1 = DriveFolder(
        id=uuid4(),
        google_folder_id="folder123",
        name="Test Folder 1",
        owner_id=uuid4(),
        is_active=True,
        last_sync_at=None,
        created_at=datetime.now(),
    )
    folder2 = DriveFolder(
        id=uuid4(),
        google_folder_id="folder456",
        name="Test Folder 2",
        owner_id=uuid4(),
        is_active=True,
        last_sync_at=datetime.now(),
        created_at=datetime.now(),
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [folder1, folder2]
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await list_drive_folders(session=mock_session, user=mock_admin)

    assert "folders" in result
    assert len(result["folders"]) == 2
    assert result["folders"][0].name == "Test Folder 1"
    assert result["folders"][1].name == "Test Folder 2"


@pytest.mark.asyncio
async def test_list_drive_files():
    """Test listing files in a drive folder."""
    from app.api.drive import list_drive_files
    from sqlalchemy.ext.asyncio import AsyncSession

    folder_id = uuid4()

    # Create mock folder
    folder = DriveFolder(
        id=folder_id,
        google_folder_id="folder123",
        name="Test Folder",
        owner_id=uuid4(),
        is_active=True,
        last_sync_at=None,
        created_at=datetime.now(),
    )

    # Create mock files
    file1 = DriveFile(
        id=uuid4(),
        folder_id=folder_id,
        google_file_id="file123",
        name="document1.pdf",
        md5_hash="abc123",
        status=DriveFileStatus.COMPLETED,
        document_id=uuid4(),
        error_message=None,
        created_at=datetime.now(),
        processed_at=datetime.now(),
    )
    file2 = DriveFile(
        id=uuid4(),
        folder_id=folder_id,
        google_file_id="file456",
        name="document2.pdf",
        md5_hash="def456",
        status=DriveFileStatus.PENDING,
        document_id=None,
        error_message=None,
        created_at=datetime.now(),
        processed_at=None,
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock folder query
    mock_folder_result = MagicMock()
    mock_folder_result.scalar_one_or_none.return_value = folder

    # Mock files query
    mock_files_result = MagicMock()
    mock_files_result.scalars.return_value.all.return_value = [file1, file2]

    mock_session.execute = AsyncMock(side_effect=[mock_folder_result, mock_files_result])

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await list_drive_files(
        folder_id=folder_id,
        status_filter=None,
        limit=100,
        offset=0,
        session=mock_session,
        user=mock_admin,
    )

    assert "files" in result
    assert len(result["files"]) == 2
    assert result["files"][0].name == "document1.pdf"
    assert result["files"][1].name == "document2.pdf"


@pytest.mark.asyncio
async def test_list_drive_files_with_status_filter():
    """Test listing files with status filter."""
    from app.api.drive import list_drive_files
    from sqlalchemy.ext.asyncio import AsyncSession

    folder_id = uuid4()

    # Create mock folder
    folder = DriveFolder(
        id=folder_id,
        google_folder_id="folder123",
        name="Test Folder",
        owner_id=uuid4(),
        is_active=True,
        last_sync_at=None,
        created_at=datetime.now(),
    )

    # Create mock file
    file1 = DriveFile(
        id=uuid4(),
        folder_id=folder_id,
        google_file_id="file123",
        name="document1.pdf",
        md5_hash="abc123",
        status=DriveFileStatus.COMPLETED,
        document_id=uuid4(),
        error_message=None,
        created_at=datetime.now(),
        processed_at=datetime.now(),
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock folder query
    mock_folder_result = MagicMock()
    mock_folder_result.scalar_one_or_none.return_value = folder

    # Mock files query
    mock_files_result = MagicMock()
    mock_files_result.scalars.return_value.all.return_value = [file1]

    mock_session.execute = AsyncMock(side_effect=[mock_folder_result, mock_files_result])

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    result = await list_drive_files(
        folder_id=folder_id,
        status_filter=DriveFileStatus.COMPLETED,
        limit=100,
        offset=0,
        session=mock_session,
        user=mock_admin,
    )

    assert "files" in result
    assert len(result["files"]) == 1
    assert result["files"][0].status == DriveFileStatus.COMPLETED


@pytest.mark.asyncio
async def test_list_drive_files_folder_not_found():
    """Test listing files for non-existent folder."""
    from app.api.drive import list_drive_files
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import HTTPException

    folder_id = uuid4()

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Mock admin user
    mock_admin = User(id=uuid4(), email="admin@example.com", role=UserRole.ADMIN, is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await list_drive_files(
            folder_id=folder_id,
            status_filter=None,
            limit=100,
            offset=0,
            session=mock_session,
            user=mock_admin,
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()
