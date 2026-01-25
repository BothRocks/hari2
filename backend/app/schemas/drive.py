import re
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.drive import DriveFileStatus


class DriveFolderCreate(BaseModel):
    google_folder_id: str
    name: str | None = None

    @field_validator("google_folder_id", mode="before")
    @classmethod
    def extract_folder_id_from_url(cls, v: str) -> str:
        """Extract folder ID from Google Drive URL if full URL is provided."""
        if not v:
            return v

        v = v.strip()

        # If it looks like a URL, extract the folder ID
        # Formats: https://drive.google.com/drive/folders/ID
        #          https://drive.google.com/drive/u/0/folders/ID
        match = re.search(r"/folders/([a-zA-Z0-9_-]+)", v)
        if match:
            return match.group(1)

        # Otherwise assume it's already a folder ID
        return v


class DriveFolderResponse(BaseModel):
    id: UUID
    google_folder_id: str
    name: str
    is_active: bool
    last_sync_at: datetime | None
    created_at: datetime
    pending_count: int = 0  # Files waiting to be processed
    failed_count: int = 0   # Files that failed processing

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
