# backend/tests/test_keyword_search.py
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from app.services.search.keyword import KeywordSearch


def test_keyword_search_initialization_no_session():
    """Test KeywordSearch initialization without session."""
    search = KeywordSearch()
    assert search.session is None


def test_keyword_search_initialization_with_session():
    """Test KeywordSearch initialization with session."""
    mock_session = Mock()
    search = KeywordSearch(session=mock_session)
    assert search.session == mock_session


def test_keyword_search_has_search_method():
    """Test that KeywordSearch has search method."""
    search = KeywordSearch()
    assert hasattr(search, 'search')
    assert callable(search.search)


@pytest.mark.asyncio
async def test_search_raises_value_error_when_no_session_provided():
    """Test search raises ValueError when no session provided."""
    search = KeywordSearch()

    with pytest.raises(ValueError, match="Database session required"):
        await search.search("test query")


@pytest.mark.asyncio
async def test_search_raises_value_error_when_no_session_in_init_or_param():
    """Test search raises ValueError when no session in init or parameter."""
    search = KeywordSearch(session=None)

    with pytest.raises(ValueError, match="Database session required"):
        await search.search("test query", session=None)


@pytest.mark.asyncio
async def test_search_with_empty_query():
    """Test search with empty query returns empty results gracefully."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    # Empty query should return empty list without querying database
    results = await search.search("")

    assert results == []
    # Verify execute was NOT called (early return for empty query)
    assert not mock_session.execute.called

    # Also test whitespace-only query
    results = await search.search("   ")
    assert results == []


@pytest.mark.asyncio
async def test_search_executes_correct_sql_query():
    """Test search executes correct SQL query with proper parameters."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    test_query = "machine learning"
    test_limit = 5

    # Mock database response
    mock_result = Mock()
    mock_result.fetchall.return_value = []
    mock_session.execute.return_value = mock_result

    await search.search(query=test_query, limit=test_limit)

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
    assert "ts_rank" in sql_query
    assert "FROM documents" in sql_query
    assert "processing_status = 'completed'" in sql_query
    assert "to_tsvector('english'" in sql_query
    assert "to_tsquery('english'" in sql_query
    assert "@@" in sql_query
    assert "ORDER BY rank DESC" in sql_query
    assert "LIMIT" in sql_query

    # Verify parameters
    params = call_args[0][1]
    assert params["tsquery"] == "machine & learning"  # Words joined with &
    assert params["limit"] == test_limit


@pytest.mark.asyncio
async def test_tsquery_conversion_single_word():
    """Test tsquery conversion with single word."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    mock_result = Mock()
    mock_result.fetchall.return_value = []
    mock_session.execute.return_value = mock_result

    await search.search("python")

    call_args = mock_session.execute.call_args
    params = call_args[0][1]
    assert params["tsquery"] == "python"


@pytest.mark.asyncio
async def test_tsquery_conversion_multiple_words():
    """Test tsquery conversion with multiple words (AND operation)."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    mock_result = Mock()
    mock_result.fetchall.return_value = []
    mock_session.execute.return_value = mock_result

    await search.search("machine learning algorithms")

    call_args = mock_session.execute.call_args
    params = call_args[0][1]
    assert params["tsquery"] == "machine & learning & algorithms"


@pytest.mark.asyncio
async def test_tsquery_conversion_strips_extra_spaces():
    """Test tsquery conversion strips extra whitespace."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    mock_result = Mock()
    mock_result.fetchall.return_value = []
    mock_session.execute.return_value = mock_result

    await search.search("  machine   learning  ")

    call_args = mock_session.execute.call_args
    params = call_args[0][1]
    assert params["tsquery"] == "machine & learning"


@pytest.mark.asyncio
async def test_search_returns_properly_formatted_results():
    """Test search returns properly formatted results with rank."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    test_uuid_1 = uuid4()
    test_uuid_2 = uuid4()

    # Mock database rows
    mock_row_1 = Mock()
    mock_row_1.id = test_uuid_1
    mock_row_1.title = "Machine Learning Basics"
    mock_row_1.quick_summary = "Introduction to ML concepts"
    mock_row_1.keywords = ["machine", "learning", "AI"]
    mock_row_1.url = "https://example.com/ml-basics"
    mock_row_1.rank = 0.95

    mock_row_2 = Mock()
    mock_row_2.id = test_uuid_2
    mock_row_2.title = "Deep Learning Guide"
    mock_row_2.quick_summary = "Advanced neural networks"
    mock_row_2.keywords = ["deep", "learning", "neural"]
    mock_row_2.url = "https://example.com/deep-learning"
    mock_row_2.rank = 0.82

    mock_result = Mock()
    mock_result.fetchall.return_value = [mock_row_1, mock_row_2]
    mock_session.execute.return_value = mock_result

    results = await search.search("machine learning")

    assert len(results) == 2

    # Verify first result
    assert results[0]["id"] == str(test_uuid_1)
    assert results[0]["title"] == "Machine Learning Basics"
    assert results[0]["quick_summary"] == "Introduction to ML concepts"
    assert results[0]["keywords"] == ["machine", "learning", "AI"]
    assert results[0]["url"] == "https://example.com/ml-basics"
    assert results[0]["rank"] == 0.95

    # Verify second result
    assert results[1]["id"] == str(test_uuid_2)
    assert results[1]["title"] == "Deep Learning Guide"
    assert results[1]["quick_summary"] == "Advanced neural networks"
    assert results[1]["keywords"] == ["deep", "learning", "neural"]
    assert results[1]["url"] == "https://example.com/deep-learning"
    assert results[1]["rank"] == 0.82


@pytest.mark.asyncio
async def test_search_rank_is_float():
    """Test that rank scores are converted to float."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    test_uuid = uuid4()

    mock_row = Mock()
    mock_row.id = test_uuid
    mock_row.title = "Test"
    mock_row.quick_summary = "Summary"
    mock_row.keywords = []
    mock_row.url = "https://test.com"
    mock_row.rank = 0.123456789  # High precision

    mock_result = Mock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    results = await search.search("test query")

    assert isinstance(results[0]["rank"], float)
    assert results[0]["rank"] == 0.123456789


@pytest.mark.asyncio
async def test_search_uses_session_parameter_over_init_session():
    """Test that session parameter takes precedence over init session."""
    init_session = AsyncMock()
    param_session = AsyncMock()

    search = KeywordSearch(session=init_session)

    mock_result = Mock()
    mock_result.fetchall.return_value = []
    param_session.execute.return_value = mock_result

    await search.search("test query", session=param_session)

    # Verify param_session was used, not init_session
    param_session.execute.assert_called_once()
    init_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_search_with_default_limit():
    """Test search with default limit parameter."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    mock_result = Mock()
    mock_result.fetchall.return_value = []
    mock_session.execute.return_value = mock_result

    await search.search("test query")

    # Verify default limit
    call_args = mock_session.execute.call_args
    params = call_args[0][1]
    assert params["limit"] == 10  # default limit


@pytest.mark.asyncio
async def test_search_handles_null_fields_in_results():
    """Test search handles null fields in database results."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    test_uuid = uuid4()

    # Mock row with some null fields
    mock_row = Mock()
    mock_row.id = test_uuid
    mock_row.title = None
    mock_row.quick_summary = None
    mock_row.keywords = None
    mock_row.url = None
    mock_row.rank = 0.5

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
    assert results[0]["rank"] == 0.5


@pytest.mark.asyncio
async def test_search_returns_empty_list_when_no_matches():
    """Test search returns empty list when no documents match."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    mock_result = Mock()
    mock_result.fetchall.return_value = []
    mock_session.execute.return_value = mock_result

    results = await search.search("nonexistent query")

    assert results == []


@pytest.mark.asyncio
async def test_search_results_ordered_by_rank_descending():
    """Test search results are ordered by rank in descending order."""
    mock_session = AsyncMock()
    search = KeywordSearch(session=mock_session)

    uuid_1 = uuid4()
    uuid_2 = uuid4()
    uuid_3 = uuid4()

    # Mock rows with different ranks
    mock_row_1 = Mock()
    mock_row_1.id = uuid_1
    mock_row_1.title = "High Rank"
    mock_row_1.quick_summary = "Best match"
    mock_row_1.keywords = []
    mock_row_1.url = "https://high.com"
    mock_row_1.rank = 0.95

    mock_row_2 = Mock()
    mock_row_2.id = uuid_2
    mock_row_2.title = "Medium Rank"
    mock_row_2.quick_summary = "Good match"
    mock_row_2.keywords = []
    mock_row_2.url = "https://medium.com"
    mock_row_2.rank = 0.75

    mock_row_3 = Mock()
    mock_row_3.id = uuid_3
    mock_row_3.title = "Low Rank"
    mock_row_3.quick_summary = "Weak match"
    mock_row_3.keywords = []
    mock_row_3.url = "https://low.com"
    mock_row_3.rank = 0.45

    # Results already ordered by rank DESC (simulating database ORDER BY)
    mock_result = Mock()
    mock_result.fetchall.return_value = [mock_row_1, mock_row_2, mock_row_3]
    mock_session.execute.return_value = mock_result

    results = await search.search("test query")

    # Verify results maintain descending order
    assert len(results) == 3
    assert results[0]["rank"] == 0.95
    assert results[1]["rank"] == 0.75
    assert results[2]["rank"] == 0.45
    assert results[0]["rank"] > results[1]["rank"] > results[2]["rank"]
