from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


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


class DocumentList(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class ReprocessResponse(BaseModel):
    job_id: UUID
    message: str
