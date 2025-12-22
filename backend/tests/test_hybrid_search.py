# backend/tests/test_hybrid_search.py
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from app.services.search.hybrid import reciprocal_rank_fusion, HybridSearch


# Tests for reciprocal_rank_fusion function

def test_rrf_with_empty_lists():
    """Test RRF with empty lists."""
    result = reciprocal_rank_fusion([])
    assert result == []


def test_rrf_with_multiple_empty_lists():
    """Test RRF with multiple empty lists."""
    result = reciprocal_rank_fusion([], [], [])
    assert result == []


def test_rrf_with_single_list():
    """Test RRF with single list."""
    items = [
        {"id": "doc1", "title": "First"},
        {"id": "doc2", "title": "Second"},
        {"id": "doc3", "title": "Third"},
    ]

    result = reciprocal_rank_fusion(items)

    assert len(result) == 3
    assert result[0]["id"] == "doc1"
    assert result[1]["id"] == "doc2"
    assert result[2]["id"] == "doc3"

    # Verify RRF scores are added
    assert "rrf_score" in result[0]
    assert "rrf_score" in result[1]
    assert "rrf_score" in result[2]


def test_rrf_combines_items_with_same_id():
    """Test RRF combines items with same ID (score accumulation)."""
    list1 = [
        {"id": "doc1", "title": "Document 1"},
        {"id": "doc2", "title": "Document 2"},
    ]

    list2 = [
        {"id": "doc2", "title": "Document 2"},  # Same doc appears in both lists
        {"id": "doc3", "title": "Document 3"},
    ]

    result = reciprocal_rank_fusion(list1, list2)

    # doc2 appears in both lists, so should have higher combined score
    # Find doc2 in results
    doc2_result = [r for r in result if r["id"] == "doc2"][0]
    doc1_result = [r for r in result if r["id"] == "doc1"][0]
    doc3_result = [r for r in result if r["id"] == "doc3"][0]

    # doc2 should have accumulated score from both lists
    # In list1: rank 1 -> score = 1/(60+1+1) = 1/62
    # In list2: rank 0 -> score = 1/(60+0+1) = 1/61
    # Total = 1/62 + 1/61
    expected_doc2_score = 1.0 / 62 + 1.0 / 61
    assert abs(doc2_result["rrf_score"] - expected_doc2_score) < 0.0001

    # doc2 should rank highest due to combined score
    assert result[0]["id"] == "doc2"


def test_rrf_scoring_formula():
    """Test RRF scoring formula (1/(k + rank + 1))."""
    k = 60
    items = [
        {"id": "doc1", "title": "First"},
        {"id": "doc2", "title": "Second"},
        {"id": "doc3", "title": "Third"},
    ]

    result = reciprocal_rank_fusion(items, k=k)

    # Verify scores match formula: 1/(k + rank + 1)
    # rank 0: 1/(60+0+1) = 1/61
    expected_score_0 = 1.0 / (k + 0 + 1)
    assert abs(result[0]["rrf_score"] - expected_score_0) < 0.0001

    # rank 1: 1/(60+1+1) = 1/62
    expected_score_1 = 1.0 / (k + 1 + 1)
    assert abs(result[1]["rrf_score"] - expected_score_1) < 0.0001

    # rank 2: 1/(60+2+1) = 1/63
    expected_score_2 = 1.0 / (k + 2 + 1)
    assert abs(result[2]["rrf_score"] - expected_score_2) < 0.0001


def test_rrf_scoring_formula_with_custom_k():
    """Test RRF scoring formula with custom k value."""
    k = 100
    items = [{"id": "doc1", "title": "First"}]

    result = reciprocal_rank_fusion(items, k=k)

    # With k=100, rank 0: 1/(100+0+1) = 1/101
    expected_score = 1.0 / (k + 0 + 1)
    assert abs(result[0]["rrf_score"] - expected_score) < 0.0001


def test_rrf_sorts_by_score_descending():
    """Test RRF sorts by score descending."""
    # Create two lists where different docs rank differently
    list1 = [
        {"id": "doc1", "title": "Doc 1"},  # rank 0 in list1
        {"id": "doc2", "title": "Doc 2"},  # rank 1 in list1
        {"id": "doc3", "title": "Doc 3"},  # rank 2 in list1
    ]

    list2 = [
        {"id": "doc3", "title": "Doc 3"},  # rank 0 in list2 (boosted!)
        {"id": "doc2", "title": "Doc 2"},  # rank 1 in list2 (boosted!)
        {"id": "doc1", "title": "Doc 1"},  # rank 2 in list2
    ]

    result = reciprocal_rank_fusion(list1, list2)

    # Verify results are sorted by score descending
    for i in range(len(result) - 1):
        assert result[i]["rrf_score"] >= result[i + 1]["rrf_score"]

    # Calculate expected scores
    # doc1: 1/61 (list1 rank 0) + 1/63 (list2 rank 2) = 0.032266
    # doc2: 1/62 (list1 rank 1) + 1/62 (list2 rank 1) = 0.032258
    # doc3: 1/63 (list1 rank 2) + 1/61 (list2 rank 0) = 0.032266

    # doc1 and doc3 should have equal highest scores (symmetric)
    # doc2 should be slightly lower
    doc1_result = [r for r in result if r["id"] == "doc1"][0]
    doc2_result = [r for r in result if r["id"] == "doc2"][0]
    doc3_result = [r for r in result if r["id"] == "doc3"][0]

    assert doc1_result["rrf_score"] > doc2_result["rrf_score"]
    assert doc3_result["rrf_score"] > doc2_result["rrf_score"]
    # doc1 and doc3 should have equal scores (symmetric positions)
    assert abs(doc1_result["rrf_score"] - doc3_result["rrf_score"]) < 0.0001


def test_rrf_preserves_item_fields():
    """Test RRF preserves all fields from items."""
    items = [
        {
            "id": "doc1",
            "title": "Document 1",
            "quick_summary": "Summary 1",
            "keywords": ["test"],
            "url": "https://example.com/1",
            "similarity": 0.95,
        }
    ]

    result = reciprocal_rank_fusion(items)

    assert result[0]["id"] == "doc1"
    assert result[0]["title"] == "Document 1"
    assert result[0]["quick_summary"] == "Summary 1"
    assert result[0]["keywords"] == ["test"]
    assert result[0]["url"] == "https://example.com/1"
    assert result[0]["similarity"] == 0.95
    assert "rrf_score" in result[0]


def test_rrf_with_three_lists():
    """Test RRF with three result lists."""
    list1 = [{"id": "doc1", "title": "Doc 1"}]
    list2 = [{"id": "doc1", "title": "Doc 1"}]
    list3 = [{"id": "doc1", "title": "Doc 1"}]

    result = reciprocal_rank_fusion(list1, list2, list3)

    # doc1 appears in all 3 lists at rank 0
    # Score = 3 * (1/61)
    expected_score = 3 * (1.0 / 61)
    assert abs(result[0]["rrf_score"] - expected_score) < 0.0001


# Tests for HybridSearch class

def test_hybrid_search_initialization_no_session():
    """Test HybridSearch initialization without session."""
    search = HybridSearch()
    assert search.session is None
    assert hasattr(search, 'semantic')
    assert hasattr(search, 'keyword')


def test_hybrid_search_initialization_with_session():
    """Test HybridSearch initialization with session."""
    mock_session = Mock()
    search = HybridSearch(session=mock_session)
    assert search.session == mock_session


def test_hybrid_search_has_search_method():
    """Test that HybridSearch has search method."""
    search = HybridSearch()
    assert hasattr(search, 'search')
    assert callable(search.search)


@pytest.mark.asyncio
async def test_hybrid_search_runs_both_searches():
    """Test hybrid search runs both semantic and keyword search."""
    mock_session = AsyncMock()
    search = HybridSearch(session=mock_session)

    # Mock both search methods
    semantic_results = [
        {"id": "doc1", "title": "Doc 1", "similarity": 0.9}
    ]
    keyword_results = [
        {"id": "doc2", "title": "Doc 2", "rank": 0.8}
    ]

    with patch.object(search.semantic, 'search', new=AsyncMock(return_value=semantic_results)) as mock_semantic:
        with patch.object(search.keyword, 'search', new=AsyncMock(return_value=keyword_results)) as mock_keyword:
            await search.search("test query", limit=10, session=mock_session)

            # Verify both searches were called
            mock_semantic.assert_called_once()
            mock_keyword.assert_called_once()

            # Verify they were called with correct parameters
            semantic_call = mock_semantic.call_args
            keyword_call = mock_keyword.call_args

            assert semantic_call[0][0] == "test query"  # query
            assert semantic_call[1]["limit"] == 20  # limit * 2
            assert semantic_call[1]["session"] == mock_session

            assert keyword_call[0][0] == "test query"  # query
            assert keyword_call[1]["limit"] == 20  # limit * 2
            assert keyword_call[1]["session"] == mock_session


@pytest.mark.asyncio
async def test_hybrid_search_returns_combined_results():
    """Test hybrid search returns combined results limited by limit parameter."""
    mock_session = AsyncMock()
    search = HybridSearch(session=mock_session)

    # Create mock results
    semantic_results = [
        {"id": "doc1", "title": "Doc 1", "similarity": 0.9},
        {"id": "doc2", "title": "Doc 2", "similarity": 0.8},
    ]
    keyword_results = [
        {"id": "doc2", "title": "Doc 2", "rank": 0.85},
        {"id": "doc3", "title": "Doc 3", "rank": 0.75},
    ]

    with patch.object(search.semantic, 'search', new=AsyncMock(return_value=semantic_results)):
        with patch.object(search.keyword, 'search', new=AsyncMock(return_value=keyword_results)):
            results = await search.search("test query", limit=10, session=mock_session)

            # Results should be combined with RRF
            assert isinstance(results, list)
            assert len(results) <= 10  # Limited by limit parameter

            # All results should have rrf_score
            for result in results:
                assert "rrf_score" in result


@pytest.mark.asyncio
async def test_hybrid_search_respects_limit_parameter():
    """Test hybrid search respects limit parameter."""
    mock_session = AsyncMock()
    search = HybridSearch(session=mock_session)

    # Create more results than the limit
    semantic_results = [
        {"id": f"doc{i}", "title": f"Doc {i}", "similarity": 0.9 - i * 0.1}
        for i in range(10)
    ]
    keyword_results = [
        {"id": f"doc{i+10}", "title": f"Doc {i+10}", "rank": 0.9 - i * 0.1}
        for i in range(10)
    ]

    with patch.object(search.semantic, 'search', new=AsyncMock(return_value=semantic_results)):
        with patch.object(search.keyword, 'search', new=AsyncMock(return_value=keyword_results)):
            results = await search.search("test query", limit=5, session=mock_session)

            # Should return exactly 5 results
            assert len(results) == 5


@pytest.mark.asyncio
async def test_hybrid_search_with_empty_results():
    """Test hybrid search with empty results from both searches."""
    mock_session = AsyncMock()
    search = HybridSearch(session=mock_session)

    with patch.object(search.semantic, 'search', new=AsyncMock(return_value=[])):
        with patch.object(search.keyword, 'search', new=AsyncMock(return_value=[])):
            results = await search.search("test query", session=mock_session)

            assert results == []


@pytest.mark.asyncio
async def test_hybrid_search_with_only_semantic_results():
    """Test hybrid search with only semantic results."""
    mock_session = AsyncMock()
    search = HybridSearch(session=mock_session)

    semantic_results = [
        {"id": "doc1", "title": "Doc 1", "similarity": 0.9}
    ]

    with patch.object(search.semantic, 'search', new=AsyncMock(return_value=semantic_results)):
        with patch.object(search.keyword, 'search', new=AsyncMock(return_value=[])):
            results = await search.search("test query", session=mock_session)

            assert len(results) == 1
            assert results[0]["id"] == "doc1"
            assert "rrf_score" in results[0]


@pytest.mark.asyncio
async def test_hybrid_search_with_only_keyword_results():
    """Test hybrid search with only keyword results."""
    mock_session = AsyncMock()
    search = HybridSearch(session=mock_session)

    keyword_results = [
        {"id": "doc1", "title": "Doc 1", "rank": 0.8}
    ]

    with patch.object(search.semantic, 'search', new=AsyncMock(return_value=[])):
        with patch.object(search.keyword, 'search', new=AsyncMock(return_value=keyword_results)):
            results = await search.search("test query", session=mock_session)

            assert len(results) == 1
            assert results[0]["id"] == "doc1"
            assert "rrf_score" in results[0]


@pytest.mark.asyncio
async def test_hybrid_search_uses_session_parameter():
    """Test hybrid search uses session parameter over init session."""
    init_session = AsyncMock()
    param_session = AsyncMock()

    search = HybridSearch(session=init_session)

    with patch.object(search.semantic, 'search', new=AsyncMock(return_value=[])) as mock_semantic:
        with patch.object(search.keyword, 'search', new=AsyncMock(return_value=[])) as mock_keyword:
            await search.search("test query", session=param_session)

            # Both searches should use param_session
            assert mock_semantic.call_args[1]["session"] == param_session
            assert mock_keyword.call_args[1]["session"] == param_session


@pytest.mark.asyncio
async def test_hybrid_search_default_limit():
    """Test hybrid search with default limit parameter."""
    mock_session = AsyncMock()
    search = HybridSearch(session=mock_session)

    with patch.object(search.semantic, 'search', new=AsyncMock(return_value=[])) as mock_semantic:
        with patch.object(search.keyword, 'search', new=AsyncMock(return_value=[])) as mock_keyword:
            await search.search("test query", session=mock_session)

            # Default limit is 10, so both searches should get limit * 2 = 20
            assert mock_semantic.call_args[1]["limit"] == 20
            assert mock_keyword.call_args[1]["limit"] == 20
