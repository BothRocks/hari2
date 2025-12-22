# backend/tests/test_semantic_search.py
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.search.semantic import SemanticSearch


def test_semantic_search_initialization_no_session():
    """Test SemanticSearch initialization without session."""
    search = SemanticSearch()
    assert search.session is None


def test_semantic_search_initialization_with_session():
    """Test SemanticSearch initialization with session."""
    mock_session = Mock()
    search = SemanticSearch(session=mock_session)
    assert search.session == mock_session


def test_semantic_search_has_search_method():
    """Test that SemanticSearch has search method."""
    search = SemanticSearch()
    assert hasattr(search, 'search')
    assert callable(search.search)


@pytest.mark.asyncio
async def test_search_raises_value_error_when_no_session_provided():
    """Test search raises ValueError when no session provided."""
    search = SemanticSearch()

    with pytest.raises(ValueError, match="Database session required"):
        await search.search("test query")


@pytest.mark.asyncio
async def test_search_raises_value_error_when_no_session_in_init_or_param():
    """Test search raises ValueError when no session in init or parameter."""
    search = SemanticSearch(session=None)

    with pytest.raises(ValueError, match="Database session required"):
        await search.search("test query", session=None)


@pytest.mark.asyncio
async def test_search_returns_empty_list_when_embedding_generation_fails():
    """Test search returns empty list when embedding generation fails."""
    mock_session = AsyncMock()
    search = SemanticSearch(session=mock_session)

    # Mock generate_embedding to return None
    with patch("app.services.search.semantic.generate_embedding", return_value=None):
        results = await search.search("test query")

        assert results == []
        # Verify database was not queried
        mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_search_executes_correct_sql_query():
    """Test search executes correct SQL query with proper parameters."""
    mock_session = AsyncMock()
    search = SemanticSearch(session=mock_session)

    mock_embedding = [0.1, 0.2, 0.3]
    test_query = "test search query"
    test_limit = 5
    test_threshold = 0.7

    # Mock generate_embedding
    with patch("app.services.search.semantic.generate_embedding", return_value=mock_embedding):
        # Mock database response (empty results for this test)
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await search.search(
            query=test_query,
            limit=test_limit,
            threshold=test_threshold
        )

        # Verify execute was called
        assert mock_session.execute.called
        call_args = mock_session.execute.call_args

        # Verify SQL text contains expected clauses
        sql_query = str(call_args[0][0])
        assert "SELECT" in sql_query
        assert "id" in sql_query
        assert "title" in sql_query
        assert "quick_summary" in sql_query
        assert "keywords" in sql_query
        assert "url" in sql_query
        assert "similarity" in sql_query
        assert "FROM documents" in sql_query
        assert "processing_status = 'completed'" in sql_query
        assert "embedding IS NOT NULL" in sql_query
        assert "ORDER BY" in sql_query
        assert "LIMIT" in sql_query
        assert "embedding <=> :query_embedding::vector" in sql_query

        # Verify parameters
        params = call_args[0][1]
        assert params["query_embedding"] == str(mock_embedding)
        assert params["threshold"] == test_threshold
        assert params["limit"] == test_limit


@pytest.mark.asyncio
async def test_search_returns_properly_formatted_results():
    """Test search returns properly formatted results."""
    mock_session = AsyncMock()
    search = SemanticSearch(session=mock_session)

    mock_embedding = [0.1] * 1536
    test_uuid_1 = uuid4()
    test_uuid_2 = uuid4()

    # Mock database rows
    mock_row_1 = Mock()
    mock_row_1.id = test_uuid_1
    mock_row_1.title = "Test Document 1"
    mock_row_1.quick_summary = "This is a test summary 1"
    mock_row_1.keywords = ["test", "document"]
    mock_row_1.url = "https://example.com/doc1"
    mock_row_1.similarity = 0.95

    mock_row_2 = Mock()
    mock_row_2.id = test_uuid_2
    mock_row_2.title = "Test Document 2"
    mock_row_2.quick_summary = "This is a test summary 2"
    mock_row_2.keywords = ["another", "test"]
    mock_row_2.url = "https://example.com/doc2"
    mock_row_2.similarity = 0.85

    with patch("app.services.search.semantic.generate_embedding", return_value=mock_embedding):
        mock_result = Mock()
        mock_result.fetchall.return_value = [mock_row_1, mock_row_2]
        mock_session.execute.return_value = mock_result

        results = await search.search("test query")

        assert len(results) == 2

        # Verify first result
        assert results[0]["id"] == str(test_uuid_1)
        assert results[0]["title"] == "Test Document 1"
        assert results[0]["quick_summary"] == "This is a test summary 1"
        assert results[0]["keywords"] == ["test", "document"]
        assert results[0]["url"] == "https://example.com/doc1"
        assert results[0]["similarity"] == 0.95

        # Verify second result
        assert results[1]["id"] == str(test_uuid_2)
        assert results[1]["title"] == "Test Document 2"
        assert results[1]["quick_summary"] == "This is a test summary 2"
        assert results[1]["keywords"] == ["another", "test"]
        assert results[1]["url"] == "https://example.com/doc2"
        assert results[1]["similarity"] == 0.85


@pytest.mark.asyncio
async def test_search_uses_session_parameter_over_init_session():
    """Test that session parameter takes precedence over init session."""
    init_session = AsyncMock()
    param_session = AsyncMock()

    search = SemanticSearch(session=init_session)

    mock_embedding = [0.1] * 1536

    with patch("app.services.search.semantic.generate_embedding", return_value=mock_embedding):
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        param_session.execute.return_value = mock_result

        await search.search("test query", session=param_session)

        # Verify param_session was used, not init_session
        param_session.execute.assert_called_once()
        init_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_search_with_default_parameters():
    """Test search with default limit and threshold parameters."""
    mock_session = AsyncMock()
    search = SemanticSearch(session=mock_session)

    mock_embedding = [0.1] * 1536

    with patch("app.services.search.semantic.generate_embedding", return_value=mock_embedding):
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await search.search("test query")

        # Verify default parameters
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 10  # default limit
        assert params["threshold"] == 0.5  # default threshold


@pytest.mark.asyncio
async def test_search_handles_null_fields_in_results():
    """Test search handles null fields in database results."""
    mock_session = AsyncMock()
    search = SemanticSearch(session=mock_session)

    mock_embedding = [0.1] * 1536
    test_uuid = uuid4()

    # Mock row with some null fields
    mock_row = Mock()
    mock_row.id = test_uuid
    mock_row.title = None
    mock_row.quick_summary = None
    mock_row.keywords = None
    mock_row.url = None
    mock_row.similarity = 0.75

    with patch("app.services.search.semantic.generate_embedding", return_value=mock_embedding):
        mock_result = Mock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await search.search("test query")

        assert len(results) == 1
        assert results[0]["id"] == str(test_uuid)
        assert results[0]["title"] is None
        assert results[0]["quick_summary"] is None
        assert results[0]["keywords"] is None
        assert results[0]["url"] is None
        assert results[0]["similarity"] == 0.75


@pytest.mark.asyncio
async def test_search_returns_empty_list_when_no_matches():
    """Test search returns empty list when no documents match."""
    mock_session = AsyncMock()
    search = SemanticSearch(session=mock_session)

    mock_embedding = [0.1] * 1536

    with patch("app.services.search.semantic.generate_embedding", return_value=mock_embedding):
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        results = await search.search("test query")

        assert results == []


@pytest.mark.asyncio
async def test_search_similarity_score_is_float():
    """Test that similarity scores are converted to float."""
    mock_session = AsyncMock()
    search = SemanticSearch(session=mock_session)

    mock_embedding = [0.1] * 1536
    test_uuid = uuid4()

    mock_row = Mock()
    mock_row.id = test_uuid
    mock_row.title = "Test"
    mock_row.quick_summary = "Summary"
    mock_row.keywords = []
    mock_row.url = "https://test.com"
    mock_row.similarity = 0.8888888888  # High precision

    with patch("app.services.search.semantic.generate_embedding", return_value=mock_embedding):
        mock_result = Mock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await search.search("test query")

        assert isinstance(results[0]["similarity"], float)
        assert results[0]["similarity"] == 0.8888888888
