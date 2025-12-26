from app.models.document import Document, SourceType, ProcessingStatus


def test_document_has_required_fields():
    assert hasattr(Document, "id")
    assert hasattr(Document, "url")
    assert hasattr(Document, "title")
    assert hasattr(Document, "content")
    assert hasattr(Document, "summary")
    assert hasattr(Document, "embedding")


def test_document_has_author_field():
    assert hasattr(Document, "author")


def test_document_has_review_fields():
    assert hasattr(Document, "needs_review")
    assert hasattr(Document, "review_reasons")
    assert hasattr(Document, "original_metadata")
    assert hasattr(Document, "reviewed_at")
    assert hasattr(Document, "reviewed_by_id")


def test_source_type_enum():
    assert SourceType.URL.value == "url"
    assert SourceType.PDF.value == "pdf"
    assert SourceType.DRIVE.value == "drive"


def test_processing_status_enum():
    assert ProcessingStatus.PENDING.value == "pending"
    assert ProcessingStatus.COMPLETED.value == "completed"
    assert ProcessingStatus.FAILED.value == "failed"
