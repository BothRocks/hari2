# backend/tests/test_bot_search.py
"""Tests for bot search functionality."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.integrations.bot_base import BotBase


class ConcreteBot(BotBase):
    """Concrete implementation for testing."""

    platform = "test"


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def bot(mock_db):
    """Create bot instance."""
    return ConcreteBot(mock_db)


class TestIsSearchCommand:
    """Tests for is_search_command method."""

    def test_find_command(self, bot):
        assert bot.is_search_command("find climate change") is True

    def test_search_command(self, bot):
        assert bot.is_search_command("search AI research") is True

    def test_find_slash_command(self, bot):
        assert bot.is_search_command("/find neural networks") is True

    def test_search_slash_command(self, bot):
        assert bot.is_search_command("/search machine learning") is True

    def test_find_uppercase(self, bot):
        assert bot.is_search_command("FIND data science") is True

    def test_find_with_whitespace(self, bot):
        assert bot.is_search_command("  find query  ") is True

    def test_not_search_command(self, bot):
        assert bot.is_search_command("hello world") is False

    def test_find_without_space(self, bot):
        assert bot.is_search_command("findstuff") is False

    def test_contains_find(self, bot):
        assert bot.is_search_command("I want to find something") is False


class TestExtractSearchQuery:
    """Tests for extract_search_query method."""

    def test_extract_from_find(self, bot):
        assert bot.extract_search_query("find climate change") == "climate change"

    def test_extract_from_search(self, bot):
        assert bot.extract_search_query("search AI research") == "AI research"

    def test_extract_from_slash_find(self, bot):
        assert bot.extract_search_query("/find neural networks") == "neural networks"

    def test_extract_from_slash_search(self, bot):
        assert bot.extract_search_query("/search machine learning") == "machine learning"

    def test_extract_with_extra_spaces(self, bot):
        assert bot.extract_search_query("find   multiple   words") == "multiple   words"

    def test_extract_preserves_case(self, bot):
        assert bot.extract_search_query("Find Climate Change") == "Climate Change"

    def test_extract_trims_whitespace(self, bot):
        assert bot.extract_search_query("  find query  ") == "query"


class TestHandleSearch:
    """Tests for handle_search method."""

    @pytest.mark.asyncio
    async def test_empty_query(self, bot):
        result = await bot.handle_search("")
        assert "Please provide a search query" in result

    @pytest.mark.asyncio
    async def test_no_results(self, bot):
        with patch.object(bot, "_search_documents", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            result = await bot.handle_search("nonexistent topic")
            assert "No documents found" in result
            assert "nonexistent topic" in result

    @pytest.mark.asyncio
    async def test_formats_results(self, bot):
        with patch.object(bot, "_search_documents", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                {
                    "id": str(uuid4()),
                    "title": "Climate Change Report",
                    "author": "Dr. Smith",
                    "url": "https://example.com/climate.pdf",
                    "created_at": datetime(2024, 1, 15),
                },
                {
                    "id": str(uuid4()),
                    "title": "AI in Healthcare",
                    "author": None,
                    "url": None,
                    "created_at": datetime(2024, 2, 20),
                },
            ]
            result = await bot.handle_search("climate")

            assert "Found 2 document(s)" in result
            assert "Climate Change Report" in result
            assert "Dr. Smith" in result
            assert "2024-01-15" in result
            assert "https://example.com/climate.pdf" in result
            assert "AI in Healthcare" in result
            assert "2024-02-20" in result

    @pytest.mark.asyncio
    async def test_handles_untitled_document(self, bot):
        with patch.object(bot, "_search_documents", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                {
                    "id": str(uuid4()),
                    "title": None,
                    "author": None,
                    "url": "https://example.com/doc.pdf",
                    "created_at": datetime(2024, 3, 10),
                },
            ]
            result = await bot.handle_search("query")
            assert "Untitled" in result


class TestSearchDocuments:
    """Tests for _search_documents method."""

    @pytest.mark.asyncio
    async def test_calls_hybrid_search(self, bot, mock_db):
        with patch("app.services.search.hybrid.HybridSearch") as MockHybridSearch:
            mock_search = AsyncMock()
            mock_search.search.return_value = []
            MockHybridSearch.return_value = mock_search

            await bot._search_documents("test query")

            MockHybridSearch.assert_called_once_with(mock_db)
            mock_search.search.assert_called_once_with(
                "test query", limit=5, session=mock_db
            )

    @pytest.mark.asyncio
    async def test_enriches_results_from_database(self, bot, mock_db):
        doc_id = uuid4()

        with patch("app.services.search.hybrid.HybridSearch") as MockHybridSearch:
            mock_search = AsyncMock()
            mock_search.search.return_value = [{"id": doc_id}]
            MockHybridSearch.return_value = mock_search

            # Mock document query result
            mock_doc = MagicMock()
            mock_doc.id = doc_id
            mock_doc.title = "Test Document"
            mock_doc.author = "Test Author"
            mock_doc.url = "https://example.com/test"
            mock_doc.created_at = datetime(2024, 1, 1)

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_doc
            mock_db.execute.return_value = mock_result

            results = await bot._search_documents("test")

            assert len(results) == 1
            assert results[0]["id"] == str(doc_id)
            assert results[0]["title"] == "Test Document"
            assert results[0]["author"] == "Test Author"
            assert results[0]["url"] == "https://example.com/test"

    @pytest.mark.asyncio
    async def test_respects_limit(self, bot, mock_db):
        with patch("app.services.search.hybrid.HybridSearch") as MockHybridSearch:
            mock_search = AsyncMock()
            mock_search.search.return_value = []
            MockHybridSearch.return_value = mock_search

            await bot._search_documents("test query", limit=10)

            mock_search.search.assert_called_once_with(
                "test query", limit=10, session=mock_db
            )


class TestHelpMessage:
    """Tests for updated help message."""

    def test_includes_search_command(self, bot):
        result = bot.handle_help()
        assert "find" in result.lower()
        assert "search" in result.lower() or "find <query>" in result
