# backend/tests/test_api_documents.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.documents import router, create_document_from_url, upload_pdf, list_documents, get_document, delete_document, update_document, reprocess_document, mark_document_reviewed
from app.models.document import Document, ProcessingStatus, SourceType
from app.models.user import User, UserRole
from app.schemas.document import DocumentCreate, DocumentUpdate, DocumentDetail, DocumentList, ReprocessResponse
from app.models.job import Job, JobType, JobStatus


def test_router_exists():
    """Test that the documents router exists and has correct config."""
    assert router is not None
    assert router.prefix == "/documents"
    assert "documents" in router.tags


@pytest.mark.asyncio
async def test_create_document_from_url_success():
    """Test creating a document from URL successfully."""
    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock select result - no existing document
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    # Mock refresh to set required fields on document
    def mock_refresh_side_effect(doc):
        if not hasattr(doc, 'id') or doc.id is None:
            doc.id = uuid4()
        if not hasattr(doc, 'created_at') or doc.created_at is None:
            doc.created_at = datetime.now()
            doc.updated_at = datetime.now()

    mock_session.refresh = AsyncMock(side_effect=mock_refresh_side_effect)

    # Mock user
    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    # Mock pipeline
    with patch("app.api.documents.DocumentPipeline") as MockPipeline:
        mock_pipeline = MockPipeline.return_value
        mock_pipeline.process_url = AsyncMock(return_value={
            "status": "completed",
            "content": "Test content",
            "content_hash": "abc123",
            "title": "Test Title",
            "summary": "Test summary",
            "quick_summary": "Quick summary",
            "keywords": ["test", "keyword"],
            "industries": ["tech"],
            "language": "en",
            "embedding": [0.1] * 1536,
            "quality_score": 0.85,
            "token_count": 100,
            "llm_metadata": {"cost_usd": 0.001}
        })

        document_data = DocumentCreate(url="https://example.com")
        result = await create_document_from_url(
            document_data=document_data,
            session=mock_session,
            user=mock_user
        )

        assert result is not None
        assert mock_session.add.called
        assert mock_session.commit.called
        mock_pipeline.process_url.assert_called_once_with("https://example.com")


@pytest.mark.asyncio
async def test_create_document_url_required():
    """Test that URL is required when creating document."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    document_data = DocumentCreate(url=None)

    with pytest.raises(HTTPException) as exc_info:
        await create_document_from_url(
            document_data=document_data,
            session=mock_session,
            user=mock_user
        )

    assert exc_info.value.status_code == 400
    assert "URL is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_document_duplicate_url():
    """Test that duplicate URL is rejected."""
    # Mock existing document
    existing_doc = Document(
        id=uuid4(),
        url="https://example.com",
        source_type=SourceType.URL,
        processing_status=ProcessingStatus.COMPLETED,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_doc
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    document_data = DocumentCreate(url="https://example.com")

    with pytest.raises(HTTPException) as exc_info:
        await create_document_from_url(
            document_data=document_data,
            session=mock_session,
            user=mock_user
        )

    assert exc_info.value.status_code == 409
    assert "already exists" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_document_pipeline_failure():
    """Test handling of pipeline failure."""
    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock select result - no existing document
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    # Mock refresh to set required fields on document
    def mock_refresh_side_effect(doc):
        if not hasattr(doc, 'id') or doc.id is None:
            doc.id = uuid4()
        if not hasattr(doc, 'created_at') or doc.created_at is None:
            doc.created_at = datetime.now()
            doc.updated_at = datetime.now()
        if not hasattr(doc, 'needs_review') or doc.needs_review is None:
            doc.needs_review = False

    mock_session.refresh = AsyncMock(side_effect=mock_refresh_side_effect)

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    # Mock pipeline with failure
    with patch("app.api.documents.DocumentPipeline") as MockPipeline:
        mock_pipeline = MockPipeline.return_value
        mock_pipeline.process_url = AsyncMock(return_value={
            "status": "failed",
            "error": "Failed to fetch URL"
        })

        document_data = DocumentCreate(url="https://example.com")
        result = await create_document_from_url(
            document_data=document_data,
            session=mock_session,
            user=mock_user
        )

        assert result is not None
        # Document should be created but with FAILED status
        assert mock_session.add.called


@pytest.mark.asyncio
async def test_upload_pdf_success():
    """Test uploading a PDF successfully."""
    # Mock file
    mock_file = MagicMock()
    mock_file.content_type = "application/pdf"
    mock_file.filename = "test.pdf"
    mock_file.size = None  # No size header
    mock_file.read = AsyncMock(return_value=b"PDF content")

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    # Mock refresh to set required fields on document
    def mock_refresh_side_effect(doc):
        if not hasattr(doc, 'id') or doc.id is None:
            doc.id = uuid4()
        if not hasattr(doc, 'created_at') or doc.created_at is None:
            doc.created_at = datetime.now()
            doc.updated_at = datetime.now()

    mock_session.refresh = AsyncMock(side_effect=mock_refresh_side_effect)

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    # Mock pipeline and settings for size check
    with patch("app.api.documents.DocumentPipeline") as MockPipeline, \
         patch("app.api.documents.settings") as mock_settings:
        mock_settings.max_upload_size_mb = 350

        mock_pipeline = MockPipeline.return_value
        mock_pipeline.process_pdf = AsyncMock(return_value={
            "status": "completed",
            "content": "PDF text content",
            "content_hash": "def456",
            "title": "PDF Title",
            "summary": "PDF summary",
            "quick_summary": "Quick PDF summary",
            "keywords": ["pdf", "test"],
            "industries": ["education"],
            "language": "en",
            "embedding": [0.2] * 1536,
            "quality_score": 0.9,
            "token_count": 150,
            "llm_metadata": {"cost_usd": 0.002}
        })

        result = await upload_pdf(
            file=mock_file,
            session=mock_session,
            user=mock_user
        )

        assert result is not None
        assert mock_session.add.called
        assert mock_session.commit.called
        mock_pipeline.process_pdf.assert_called_once_with(b"PDF content", "test.pdf")


@pytest.mark.asyncio
async def test_upload_pdf_validation_not_pdf():
    """Test that non-PDF files are rejected."""
    # Mock file with wrong content type
    mock_file = MagicMock()
    mock_file.content_type = "text/plain"
    mock_file.filename = "test.txt"

    mock_session = MagicMock(spec=AsyncSession)
    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await upload_pdf(
            file=mock_file,
            session=mock_session,
            user=mock_user
        )

    assert exc_info.value.status_code == 400
    assert "PDF" in exc_info.value.detail


@pytest.mark.asyncio
async def test_list_documents_default_pagination():
    """Test listing documents with default pagination."""
    # Mock documents
    doc1 = Document(
        id=uuid4(),
        url="https://example1.com",
        source_type=SourceType.URL,
        processing_status=ProcessingStatus.COMPLETED,
        needs_review=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    doc2 = Document(
        id=uuid4(),
        url="https://example2.com",
        source_type=SourceType.URL,
        processing_status=ProcessingStatus.COMPLETED,
        needs_review=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock count query (uses .scalar() not .scalar_one())
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 2

    # Mock documents query
    mock_docs_result = MagicMock()
    mock_docs_result.scalars.return_value.all.return_value = [doc1, doc2]

    # Setup execute to return different results based on call order
    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_docs_result])

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    result = await list_documents(
        page=1,
        page_size=20,
        status=None,
        needs_review=None,
        search=None,
        sort_by="created_at",
        sort_order="desc",
        session=mock_session,
        user=mock_user
    )

    assert isinstance(result, DocumentList)
    assert result.total == 2
    assert result.page == 1
    assert result.page_size == 20
    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_list_documents_with_status_filter():
    """Test listing documents with status filter."""
    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock count query (uses .scalar() not .scalar_one())
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    # Mock documents query
    mock_docs_result = MagicMock()
    mock_docs_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_docs_result])

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    result = await list_documents(
        page=1,
        page_size=20,
        status=ProcessingStatus.COMPLETED,
        needs_review=None,
        search=None,
        sort_by="created_at",
        sort_order="desc",
        session=mock_session,
        user=mock_user
    )

    assert isinstance(result, DocumentList)
    assert result.total == 1


@pytest.mark.asyncio
async def test_list_documents_custom_pagination():
    """Test listing documents with custom pagination."""
    # Mock session
    mock_session = MagicMock(spec=AsyncSession)

    # Mock count query (uses .scalar() not .scalar_one())
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 100

    # Mock documents query
    mock_docs_result = MagicMock()
    mock_docs_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_docs_result])

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    result = await list_documents(
        page=2,
        page_size=10,
        status=None,
        needs_review=None,
        search=None,
        sort_by="created_at",
        sort_order="desc",
        session=mock_session,
        user=mock_user
    )

    assert result.page == 2
    assert result.page_size == 10
    assert result.total == 100


@pytest.mark.asyncio
async def test_get_document_success():
    """Test getting a document by ID."""
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        url="https://example.com",
        title="Test Document",
        source_type=SourceType.URL,
        processing_status=ProcessingStatus.COMPLETED,
        summary="Full summary",
        content="Full content",
        needs_review=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    result = await get_document(
        document_id=doc_id,
        session=mock_session,
        user=mock_user
    )

    assert isinstance(result, DocumentDetail)


@pytest.mark.asyncio
async def test_get_document_not_found():
    """Test getting a non-existent document returns 404."""
    doc_id = uuid4()

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await get_document(
            document_id=doc_id,
            session=mock_session,
            user=mock_user
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_delete_document_success():
    """Test deleting a document successfully."""
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        url="https://example.com",
        source_type=SourceType.URL,
        processing_status=ProcessingStatus.COMPLETED,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    result = await delete_document(
        document_id=doc_id,
        session=mock_session,
        user=mock_user
    )

    assert result is None
    mock_session.delete.assert_called_once_with(doc)
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_document_not_found():
    """Test deleting a non-existent document returns 404."""
    doc_id = uuid4()

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await delete_document(
            document_id=doc_id,
            session=mock_session,
            user=mock_user
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_update_document_success():
    """Test updating a document's editable fields."""
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        url="https://example.com",
        title="Original Title",
        author="Original Author",
        source_type=SourceType.URL,
        processing_status=ProcessingStatus.COMPLETED,
        needs_review=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    update_data = DocumentUpdate(title="New Title", author="New Author")
    result = await update_document(
        document_id=doc_id,
        update_data=update_data,
        session=mock_session,
        user=mock_user
    )

    assert result is not None
    assert doc.title == "New Title"
    assert doc.author == "New Author"
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_document_not_found():
    """Test updating a non-existent document returns 404."""
    doc_id = uuid4()

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    update_data = DocumentUpdate(title="New Title")

    with pytest.raises(HTTPException) as exc_info:
        await update_document(
            document_id=doc_id,
            update_data=update_data,
            session=mock_session,
            user=mock_user
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_reprocess_document_success():
    """Test triggering document reprocessing."""
    doc_id = uuid4()
    job_id = uuid4()
    doc = Document(
        id=doc_id,
        url="https://example.com",
        source_type=SourceType.URL,
        processing_status=ProcessingStatus.COMPLETED,
        needs_review=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    # Capture the job that gets added
    added_jobs = []
    def capture_add(obj):
        if isinstance(obj, Job):
            obj.id = job_id  # Set ID since it's generated on commit
        added_jobs.append(obj)
    mock_session.add = MagicMock(side_effect=capture_add)

    result = await reprocess_document(
        document_id=doc_id,
        session=mock_session,
        user=mock_user
    )

    assert result is not None
    assert result.job_id == job_id
    assert str(doc_id) in result.message
    mock_session.commit.assert_called_once()
    assert len(added_jobs) == 1
    assert added_jobs[0].job_type == JobType.PROCESS_DOCUMENT
    assert added_jobs[0].payload["document_id"] == str(doc_id)
    assert added_jobs[0].payload["reprocess"] is True


@pytest.mark.asyncio
async def test_reprocess_document_not_found():
    """Test reprocessing a non-existent document returns 404."""
    doc_id = uuid4()

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await reprocess_document(
            document_id=doc_id,
            session=mock_session,
            user=mock_user
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_mark_document_reviewed_success():
    """Test marking a document as reviewed."""
    doc_id = uuid4()
    user_id = uuid4()
    doc = Document(
        id=doc_id,
        url="https://example.com",
        source_type=SourceType.URL,
        processing_status=ProcessingStatus.COMPLETED,
        needs_review=True,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_user = User(id=user_id, email="test@example.com", role=UserRole.USER, is_active=True)

    result = await mark_document_reviewed(
        document_id=doc_id,
        session=mock_session,
        user=mock_user
    )

    assert result is not None
    assert doc.needs_review is False
    assert doc.reviewed_by_id == user_id
    assert doc.reviewed_at is not None
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_mark_document_reviewed_not_found():
    """Test marking a non-existent document as reviewed returns 404."""
    doc_id = uuid4()

    # Mock session
    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_user = User(id=uuid4(), email="test@example.com", role=UserRole.USER, is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        await mark_document_reviewed(
            document_id=doc_id,
            session=mock_session,
            user=mock_user
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()
