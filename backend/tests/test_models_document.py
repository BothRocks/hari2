import pytest
from uuid import UUID
from app.models.document import Document, SourceType, ProcessingStatus


def test_document_has_required_fields():
    assert hasattr(Document, "id")
    assert hasattr(Document, "url")
    assert hasattr(Document, "title")
    assert hasattr(Document, "content")
    assert hasattr(Document, "summary")
    assert hasattr(Document, "embedding")


def test_source_type_enum():
    assert SourceType.URL.value == "url"
    assert SourceType.PDF.value == "pdf"
    assert SourceType.DRIVE.value == "drive"


def test_processing_status_enum():
    assert ProcessingStatus.PENDING.value == "pending"
    assert ProcessingStatus.COMPLETED.value == "completed"
    assert ProcessingStatus.FAILED.value == "failed"
