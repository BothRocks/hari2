from pydantic import BaseModel, ConfigDict, HttpUrl
from uuid import UUID
from datetime import datetime


class DocumentCreate(BaseModel):
    url: str | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str | None
    title: str | None
    quick_summary: str | None
    keywords: list[str] | None
    industries: list[str] | None
    quality_score: float | None
    processing_status: str
    created_at: datetime


class DocumentDetail(DocumentResponse):
    summary: str | None
    content: str | None
    language: str | None
    error_message: str | None


class DocumentList(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
