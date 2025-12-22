from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
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
    """List registered Drive folders."""
    result = await session.execute(
        select(DriveFolder).order_by(DriveFolder.created_at.desc())
    )
    folders = result.scalars().all()

    return {
        "folders": [DriveFolderResponse.model_validate(folder) for folder in folders]
    }


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
        payload={"folder_id": str(folder_id)},
        created_by_id=user.id,
    )

    await session.commit()

    return {
        "job_id": job_id,
        "message": f"Sync job created for folder: {folder.name}",
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
