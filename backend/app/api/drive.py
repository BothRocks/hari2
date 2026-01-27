from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, update
import logging

from app.core.database import get_session
from app.core.deps import require_admin
from app.core.config import settings
from app.models.user import User
from app.models.drive import DriveFolder, DriveFile, DriveFileStatus
from app.models.job import JobType
from app.schemas.drive import (
    DriveFolderCreate,
    DriveFolderResponse,
    DriveFileResponse,
)
from app.services.drive.client import DriveService
from app.services.jobs.queue import AsyncioJobQueue

router = APIRouter(prefix="/admin/drive", tags=["admin"])
logger = logging.getLogger(__name__)


def get_drive_service() -> DriveService:
    """Get configured Drive service or raise exception."""
    return DriveService(settings.google_service_account_json)


@router.get("/service-account")
async def get_service_account_email(
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Get service account email for sharing instructions."""
    logger.info("Fetching service account email")

    try:
        drive_service = get_drive_service()

        if drive_service.service is None:
            logger.error("Google Drive service not configured")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google Drive service not configured. Please set GOOGLE_SERVICE_ACCOUNT_JSON environment variable.",
            )

        # Extract email from service account credentials using safe credential loading
        credentials_json = settings.google_service_account_json
        if not credentials_json:
            logger.error("No credentials JSON found in settings")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to extract service account email from credentials",
            )

        try:
            # Use the same safe credential loading logic as DriveService
            creds_info = drive_service._load_credentials(credentials_json)
            email = creds_info.get('client_email')

            if not email:
                logger.error("No client_email found in credentials")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service account credentials missing client_email field",
                )

            logger.info(f"Successfully retrieved service account email: {email}")
            return {
                "email": email,
                "instructions": f"Share your Google Drive folder with this email address: {email}",
            }

        except ValueError as e:
            logger.error(f"Invalid credentials format: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid credentials format: {str(e)}",
            )
        except KeyError as e:
            logger.error(f"Missing required credential field: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Service account credentials missing required field: {str(e)}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error retrieving service account email: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Google Drive service not configured: {str(e)}",
        )


@router.get("/folders")
async def list_drive_folders(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """List registered Drive folders with pending/failed/completed file counts."""
    # Get folders with file counts using subquery
    pending_count = (
        select(func.count(DriveFile.id))
        .where(DriveFile.folder_id == DriveFolder.id)
        .where(DriveFile.status == DriveFileStatus.PENDING)
        .correlate(DriveFolder)
        .scalar_subquery()
    )

    failed_count = (
        select(func.count(DriveFile.id))
        .where(DriveFile.folder_id == DriveFolder.id)
        .where(DriveFile.status == DriveFileStatus.FAILED)
        .correlate(DriveFolder)
        .scalar_subquery()
    )

    completed_count = (
        select(func.count(DriveFile.id))
        .where(DriveFile.folder_id == DriveFolder.id)
        .where(DriveFile.status == DriveFileStatus.COMPLETED)
        .correlate(DriveFolder)
        .scalar_subquery()
    )

    result = await session.execute(
        select(
            DriveFolder,
            pending_count.label("pending_count"),
            failed_count.label("failed_count"),
            completed_count.label("completed_count"),
        ).order_by(DriveFolder.created_at.desc())
    )
    rows = result.all()

    folders = []
    for row in rows:
        folder = row[0]
        folder_dict = {
            "id": folder.id,
            "google_folder_id": folder.google_folder_id,
            "name": folder.name,
            "is_active": folder.is_active,
            "last_sync_at": folder.last_sync_at,
            "created_at": folder.created_at,
            "pending_count": row[1] or 0,
            "failed_count": row[2] or 0,
            "completed_count": row[3] or 0,
        }
        folders.append(DriveFolderResponse.model_validate(folder_dict))

    return {"folders": folders}


@router.post("/folders", response_model=DriveFolderResponse, status_code=status.HTTP_201_CREATED)
async def register_drive_folder(
    folder_data: DriveFolderCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> DriveFolderResponse:
    """Register a new Drive folder (verify access first)."""
    try:
        drive_service = get_drive_service()

        if drive_service.service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google Drive service not configured",
            )

        # Verify folder access
        success, error_msg = drive_service.verify_folder_access(folder_data.google_folder_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot access folder: {error_msg}",
            )

        # Check if folder already registered
        result = await session.execute(
            select(DriveFolder).where(
                DriveFolder.google_folder_id == folder_data.google_folder_id
            )
        )
        existing_folder = result.scalar_one_or_none()

        if existing_folder:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Folder already registered",
            )

        # Get folder name if not provided
        folder_name = folder_data.name
        if not folder_name:
            # Get folder metadata to extract name
            try:
                folder_metadata = drive_service.service.files().get(
                    fileId=folder_data.google_folder_id,
                    fields='name'
                ).execute()
                folder_name = folder_metadata.get('name', 'Unnamed Folder')
            except Exception:
                folder_name = 'Unnamed Folder'

        # Create folder record
        folder = DriveFolder(
            google_folder_id=folder_data.google_folder_id,
            name=folder_name,
            owner_id=user.id,
            is_active=True,
        )
        session.add(folder)
        await session.commit()
        await session.refresh(folder)

        # Trigger immediate sync job for the new folder
        queue = AsyncioJobQueue(session)
        await queue.enqueue(
            job_type=JobType.SYNC_DRIVE_FOLDER,
            payload={"folder_id": str(folder.id), "process_files": True},
            created_by_id=user.id,
        )
        await session.commit()

        return DriveFolderResponse.model_validate(folder)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register folder: {str(e)}",
        )


@router.post("/folders/{folder_id}/sync")
async def sync_drive_folder(
    folder_id: UUID,
    process_files: bool = Query(default=True, description="Process files after syncing"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Trigger sync job for a Drive folder."""
    # Get folder
    result = await session.execute(
        select(DriveFolder).where(DriveFolder.id == folder_id)
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )

    if not folder.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder is not active",
        )

    # Create sync job
    queue = AsyncioJobQueue(session)
    job_id = await queue.enqueue(
        job_type=JobType.SYNC_DRIVE_FOLDER,
        payload={"folder_id": str(folder_id), "process_files": process_files},
        created_by_id=user.id,
    )

    await session.commit()

    action = "Sync and process" if process_files else "Sync only"
    return {
        "job_id": job_id,
        "message": f"{action} job created for folder: {folder.name}",
    }


@router.get("/folders/{folder_id}/files")
async def list_drive_files(
    folder_id: UUID,
    status_filter: DriveFileStatus | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """List files in a Drive folder."""
    # Verify folder exists
    result = await session.execute(
        select(DriveFolder).where(DriveFolder.id == folder_id)
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )

    # Build query
    query = select(DriveFile).where(DriveFile.folder_id == folder_id)

    if status_filter:
        query = query.where(DriveFile.status == status_filter)

    # Apply pagination and ordering
    query = query.order_by(DriveFile.created_at.desc()).limit(limit).offset(offset)

    result = await session.execute(query)
    files = result.scalars().all()

    return {
        "files": [DriveFileResponse.model_validate(file) for file in files]
    }


@router.delete("/folders/{folder_id}")
async def delete_drive_folder(
    folder_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Delete a Drive folder registration."""
    # Get folder
    result = await session.execute(
        select(DriveFolder).where(DriveFolder.id == folder_id)
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )

    folder_name = folder.name

    # Delete folder (cascade will delete associated files)
    await session.execute(
        delete(DriveFolder).where(DriveFolder.id == folder_id)
    )
    await session.commit()

    return {
        "message": f"Deleted folder: {folder_name}",
    }


@router.post("/folders/{folder_id}/retry-failed")
async def retry_failed_files(
    folder_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Reset failed files to pending and trigger processing."""
    result = await session.execute(
        select(DriveFolder).where(DriveFolder.id == folder_id)
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    # Reset failed files to pending
    update_result = await session.execute(
        update(DriveFile)
        .where(DriveFile.folder_id == folder_id)
        .where(DriveFile.status == DriveFileStatus.FAILED)
        .values(status=DriveFileStatus.PENDING, error_message=None)
    )
    reset_count = update_result.rowcount

    if reset_count > 0:
        # Trigger processing job
        queue = AsyncioJobQueue(session)
        await queue.enqueue(
            job_type=JobType.SYNC_DRIVE_FOLDER,
            payload={"folder_id": str(folder_id), "process_files": True},
            created_by_id=user.id,
        )

    await session.commit()

    return {
        "reset_count": reset_count,
        "message": f"Reset {reset_count} failed files to pending for folder: {folder.name}",
    }


@router.get("/uploads-folder")
async def get_uploads_folder(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Get the uploads folder (configured via DRIVE_UPLOADS_FOLDER_ID) with file counts."""
    folder_id = settings.drive_uploads_folder_id
    if not folder_id:
        return {"configured": False}

    # Look up the folder in drive_folders table (it may or may not be registered)
    result = await session.execute(
        select(DriveFolder).where(DriveFolder.google_folder_id == folder_id)
    )
    folder = result.scalar_one_or_none()

    if not folder:
        # Folder exists in config but not registered in DB - return basic info
        return {
            "configured": True,
            "google_folder_id": folder_id,
            "name": "Carpeta de uploads",
            "folder_db_id": None,
            "pending_count": 0,
            "failed_count": 0,
            "completed_count": 0,
        }

    # Get file counts
    counts_result = await session.execute(
        select(
            func.count(DriveFile.id).filter(DriveFile.status == DriveFileStatus.PENDING).label("pending_count"),
            func.count(DriveFile.id).filter(DriveFile.status == DriveFileStatus.FAILED).label("failed_count"),
            func.count(DriveFile.id).filter(DriveFile.status == DriveFileStatus.COMPLETED).label("completed_count"),
        ).where(DriveFile.folder_id == folder.id)
    )
    counts = counts_result.one()

    return {
        "configured": True,
        "google_folder_id": folder_id,
        "name": folder.name,
        "folder_db_id": str(folder.id),
        "pending_count": counts.pending_count or 0,
        "failed_count": counts.failed_count or 0,
        "completed_count": counts.completed_count or 0,
    }
