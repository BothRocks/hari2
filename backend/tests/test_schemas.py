import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentDetail,
    DocumentList,
)
from app.schemas.query import (
    QueryRequest,
    QueryResponse,
    SourceReference,
    SearchRequest,
    SearchResult,
)


class TestDocumentCreate:
    """Test DocumentCreate schema."""

    def test_document_create_with_url(self):
        """Test DocumentCreate schema with URL."""
        doc = DocumentCreate(url="https://example.com/doc.pdf")
        assert doc.url == "https://example.com/doc.pdf"

    def test_document_create_with_none_url(self):
        """Test DocumentCreate schema with None URL."""
        doc = DocumentCreate(url=None)
        assert doc.url is None

    def test_document_create_without_url(self):
        """Test DocumentCreate schema without providing URL (defaults to None)."""
        doc = DocumentCreate()
        assert doc.url is None


class TestDocumentResponse:
    """Test DocumentResponse schema."""

    def test_document_response_with_all_fields(self):
        """Test DocumentResponse schema with all fields."""
        doc_id = uuid4()
        created = datetime.now()

        doc = DocumentResponse(
            id=doc_id,
            url="https://example.com/doc.pdf",
            title="Test Document",
            quick_summary="A quick summary",
            keywords=["test", "document"],
            industries=["tech", "finance"],
            quality_score=0.85,
            processing_status="completed",
            created_at=created,
        )

        assert doc.id == doc_id
        assert doc.url == "https://example.com/doc.pdf"
        assert doc.title == "Test Document"
        assert doc.quick_summary == "A quick summary"
        assert doc.keywords == ["test", "document"]
        assert doc.industries == ["tech", "finance"]
        assert doc.quality_score == 0.85
        assert doc.processing_status == "completed"
        assert doc.created_at == created

    def test_document_response_with_none_fields(self):
        """Test DocumentResponse schema with None optional fields."""
        doc_id = uuid4()
        created = datetime.now()

        doc = DocumentResponse(
            id=doc_id,
            url=None,
            title=None,
            quick_summary=None,
            keywords=None,
            industries=None,
            quality_score=None,
            processing_status="pending",
            created_at=created,
        )

        assert doc.id == doc_id
        assert doc.url is None
        assert doc.title is None
        assert doc.quick_summary is None
        assert doc.keywords is None
        assert doc.industries is None
        assert doc.quality_score is None
        assert doc.processing_status == "pending"
        assert doc.created_at == created

    def test_document_response_from_attributes_config(self):
        """Test from_attributes config works."""
        # Simulate an ORM model with attributes
        class MockORMModel:
            def __init__(self):
                self.id = uuid4()
                self.url = "https://example.com/doc.pdf"
                self.title = "Test Document"
                self.quick_summary = "A quick summary"
                self.keywords = ["test", "document"]
                self.industries = ["tech"]
                self.quality_score = 0.85
                self.processing_status = "completed"
                self.created_at = datetime.now()

        orm_obj = MockORMModel()
        doc = DocumentResponse.model_validate(orm_obj)

        assert doc.id == orm_obj.id
        assert doc.url == orm_obj.url
        assert doc.title == orm_obj.title
        assert doc.quality_score == orm_obj.quality_score


class TestDocumentDetail:
    """Test DocumentDetail schema."""

    def test_document_detail_inherits_from_document_response(self):
        """Test DocumentDetail inherits from DocumentResponse."""
        assert issubclass(DocumentDetail, DocumentResponse)

    def test_document_detail_with_all_fields(self):
        """Test DocumentDetail schema with all fields including inherited ones."""
        doc_id = uuid4()
        created = datetime.now()

        doc = DocumentDetail(
            id=doc_id,
            url="https://example.com/doc.pdf",
            title="Test Document",
            quick_summary="A quick summary",
            keywords=["test", "document"],
            industries=["tech"],
            quality_score=0.85,
            processing_status="completed",
            created_at=created,
            summary="A detailed summary of the document content.",
            content="Full document content here.",
            language="en",
            error_message=None,
        )

        # Check inherited fields
        assert doc.id == doc_id
        assert doc.url == "https://example.com/doc.pdf"
        assert doc.processing_status == "completed"

        # Check additional fields
        assert doc.summary == "A detailed summary of the document content."
        assert doc.content == "Full document content here."
        assert doc.language == "en"
        assert doc.error_message is None

    def test_document_detail_with_error_message(self):
        """Test DocumentDetail schema with error message."""
        doc_id = uuid4()
        created = datetime.now()

        doc = DocumentDetail(
            id=doc_id,
            url="https://example.com/doc.pdf",
            title=None,
            quick_summary=None,
            keywords=None,
            industries=None,
            quality_score=None,
            processing_status="failed",
            created_at=created,
            summary=None,
            content=None,
            language=None,
            error_message="Failed to extract content from PDF",
        )

        assert doc.processing_status == "failed"
        assert doc.error_message == "Failed to extract content from PDF"


class TestDocumentList:
    """Test DocumentList schema."""

    def test_document_list(self):
        """Test DocumentList schema."""
        doc_id = uuid4()
        created = datetime.now()

        doc = DocumentResponse(
            id=doc_id,
            url="https://example.com/doc.pdf",
            title="Test Document",
            quick_summary="A quick summary",
            keywords=["test"],
            industries=["tech"],
            quality_score=0.85,
            processing_status="completed",
            created_at=created,
        )

        doc_list = DocumentList(
            items=[doc],
            total=1,
            page=1,
            page_size=10,
        )

        assert len(doc_list.items) == 1
        assert doc_list.items[0].id == doc_id
        assert doc_list.total == 1
        assert doc_list.page == 1
        assert doc_list.page_size == 10

    def test_document_list_empty(self):
        """Test DocumentList schema with empty items."""
        doc_list = DocumentList(
            items=[],
            total=0,
            page=1,
            page_size=10,
        )

        assert len(doc_list.items) == 0
        assert doc_list.total == 0


class TestQueryRequest:
    """Test QueryRequest schema."""

    def test_query_request_with_defaults(self):
        """Test QueryRequest schema with defaults."""
        query = QueryRequest(query="What is this about?")
        assert query.query == "What is this about?"
        assert query.limit == 5

    def test_query_request_with_custom_limit(self):
        """Test QueryRequest schema with custom limit."""
        query = QueryRequest(query="What is this about?", limit=10)
        assert query.query == "What is this about?"
        assert query.limit == 10

    def test_query_request_validation(self):
        """Test QueryRequest schema validation."""
        with pytest.raises(ValidationError):
            QueryRequest()  # Missing required 'query' field


class TestSourceReference:
    """Test SourceReference schema."""

    def test_source_reference(self):
        """Test SourceReference schema."""
        source = SourceReference(
            id="123",
            title="Test Document",
            url="https://example.com/doc.pdf",
        )
        assert source.id == "123"
        assert source.title == "Test Document"
        assert source.url == "https://example.com/doc.pdf"

    def test_source_reference_with_none_fields(self):
        """Test SourceReference schema with None fields."""
        source = SourceReference(id=None, title=None, url=None)
        assert source.id is None
        assert source.title is None
        assert source.url is None


class TestQueryResponse:
    """Test QueryResponse schema."""

    def test_query_response(self):
        """Test QueryResponse schema."""
        source1 = SourceReference(
            id="123",
            title="Test Document 1",
            url="https://example.com/doc1.pdf",
        )
        source2 = SourceReference(
            id="456",
            title="Test Document 2",
            url="https://example.com/doc2.pdf",
        )

        response = QueryResponse(
            answer="This is the answer to your question.",
            sources=[source1, source2],
        )

        assert response.answer == "This is the answer to your question."
        assert len(response.sources) == 2
        assert response.sources[0].id == "123"
        assert response.sources[1].id == "456"

    def test_query_response_empty_sources(self):
        """Test QueryResponse schema with empty sources."""
        response = QueryResponse(
            answer="This is the answer with no sources.",
            sources=[],
        )

        assert response.answer == "This is the answer with no sources."
        assert len(response.sources) == 0


class TestSearchRequest:
    """Test SearchRequest schema."""

    def test_search_request_with_defaults(self):
        """Test SearchRequest schema with defaults."""
        search = SearchRequest(query="machine learning")
        assert search.query == "machine learning"
        assert search.limit == 10
        assert search.threshold == 0.5

    def test_search_request_with_custom_values(self):
        """Test SearchRequest schema with custom values."""
        search = SearchRequest(
            query="machine learning",
            limit=20,
            threshold=0.7,
        )
        assert search.query == "machine learning"
        assert search.limit == 20
        assert search.threshold == 0.7

    def test_search_request_validation(self):
        """Test SearchRequest schema validation."""
        with pytest.raises(ValidationError):
            SearchRequest()  # Missing required 'query' field


class TestSearchResult:
    """Test SearchResult schema."""

    def test_search_result(self):
        """Test SearchResult schema."""
        result = SearchResult(
            id="123",
            title="Test Document",
            quick_summary="A quick summary",
            url="https://example.com/doc.pdf",
            score=0.85,
        )

        assert result.id == "123"
        assert result.title == "Test Document"
        assert result.quick_summary == "A quick summary"
        assert result.url == "https://example.com/doc.pdf"
        assert result.score == 0.85

    def test_search_result_with_none_fields(self):
        """Test SearchResult schema with None optional fields."""
        result = SearchResult(
            id="123",
            title=None,
            quick_summary=None,
            url=None,
            score=0.85,
        )

        assert result.id == "123"
        assert result.title is None
        assert result.quick_summary is None
        assert result.url is None
        assert result.score == 0.85
