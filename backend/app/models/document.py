import enum
from uuid import UUID, uuid4
from sqlalchemy import String, Text, Enum, Float, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.models.base import Base, TimestampMixin


class SourceType(str, enum.Enum):
    URL = "url"
    PDF = "pdf"
    DRIVE = "drive"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Source info
    url: Mapped[str | None] = mapped_column(String(2048))
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), default=SourceType.URL)

    # Content
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), unique=True)

    # Processed output
    summary: Mapped[str | None] = mapped_column(Text)
    quick_summary: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list | None] = mapped_column(JSON)
    industries: Mapped[list | None] = mapped_column(JSON)
    language: Mapped[str | None] = mapped_column(String(10))

    # Embeddings (1536 dimensions for text-embedding-3-small)
    embedding: Mapped[list | None] = mapped_column(Vector(1536))

    # Quality & Status
    quality_score: Mapped[float | None] = mapped_column(Float)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus), default=ProcessingStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    # Metrics
    token_count: Mapped[int | None] = mapped_column(Integer)
    processing_cost_usd: Mapped[float | None] = mapped_column(Float)
