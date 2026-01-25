from pydantic import BaseModel, ConfigDict, field_serializer
from uuid import UUID
from datetime import datetime, timezone


def serialize_datetime(dt: datetime | None) -> str | None:
    """Serialize datetime to ISO format with UTC timezone."""
    if dt is None:
        return None
    # Ensure datetime has UTC timezone for proper frontend interpretation
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class DocumentCreate(BaseModel):
    url: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    author: str | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str | None
    source_type: str
    title: str | None
    author: str | None
    quick_summary: str | None
    keywords: list[str] | None
    industries: list[str] | None
    quality_score: float | None
    processing_status: str
    needs_review: bool
    created_at: datetime

    @field_serializer('created_at')
    def serialize_created_at(self, dt: datetime) -> str:
        return serialize_datetime(dt) or ""


class DocumentDetail(DocumentResponse):
    summary: str | None
    content: str | None
    language: str | None
    error_message: str | None
    token_count: int | None
    processing_cost_usd: float | None
    review_reasons: list[str] | None
    original_metadata: dict | None
    reviewed_at: datetime | None
    reviewed_by_email: str | None = None
    updated_at: datetime

    @field_serializer('reviewed_at', 'updated_at')
    def serialize_datetimes(self, dt: datetime | None) -> str | None:
        return serialize_datetime(dt)


class DocumentList(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class ReprocessResponse(BaseModel):
    job_id: UUID
    message: str
