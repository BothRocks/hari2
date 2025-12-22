from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.drive import DriveFileStatus


class DriveFolderCreate(BaseModel):
    google_folder_id: str
    name: str | None = None


class DriveFolderResponse(BaseModel):
    id: UUID
    google_folder_id: str
    name: str
    is_active: bool
    last_sync_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DriveFileResponse(BaseModel):
    id: UUID
    google_file_id: str
    name: str
    status: DriveFileStatus
    document_id: UUID | None
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
