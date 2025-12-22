"""DriveFolder and DriveFile models for Google Drive integration."""
import enum
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import String, Text, Enum, ForeignKey, Boolean, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class DriveFileStatus(str, enum.Enum):
    """Drive file status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REMOVED = "removed"


class DriveFolder(Base, TimestampMixin):
    """Google Drive folder model."""
    __tablename__ = "drive_folders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    google_folder_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DriveFile(Base, TimestampMixin):
    """Google Drive file model."""
    __tablename__ = "drive_files"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    folder_id: Mapped[UUID] = mapped_column(ForeignKey("drive_folders.id"), nullable=False, index=True)
    google_file_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    md5_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[DriveFileStatus] = mapped_column(Enum(DriveFileStatus), default=DriveFileStatus.PENDING, index=True)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Add indexes for frequently queried columns
    __table_args__ = (
        Index('ix_drive_files_folder_status', 'folder_id', 'status'),
    )
