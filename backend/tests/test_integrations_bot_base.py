# backend/tests/test_integrations_bot_base.py
"""Tests for bot base functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.integrations.bot_base import BotBase


class ConcretBot(BotBase):
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
    return db


@pytest.fixture
def bot(mock_db):
    """Create bot instance."""
    return ConcretBot(mock_db)


class TestIsUrl:
    """Tests for is_url method."""

    def test_http_url(self, bot):
        assert bot.is_url("http://example.com") is True

    def test_https_url(self, bot):
        assert bot.is_url("https://example.com") is True

    def test_url_with_path(self, bot):
        assert bot.is_url("https://example.com/path/to/doc.pdf") is True

    def test_plain_text(self, bot):
        assert bot.is_url("hello world") is False

    def test_ftp_url(self, bot):
        assert bot.is_url("ftp://example.com") is False

    def test_url_with_whitespace(self, bot):
        assert bot.is_url("  https://example.com  ") is True


class TestIsStatusRequest:
    """Tests for is_status_request method."""

    def test_status(self, bot):
        assert bot.is_status_request("status") is True

    def test_status_command(self, bot):
        assert bot.is_status_request("/status") is True

    def test_status_uppercase(self, bot):
        assert bot.is_status_request("STATUS") is True

    def test_status_with_whitespace(self, bot):
        assert bot.is_status_request("  status  ") is True

    def test_not_status(self, bot):
        assert bot.is_status_request("hello") is False

    def test_status_in_sentence(self, bot):
        assert bot.is_status_request("check status please") is False


class TestHandleHelp:
    """Tests for handle_help method."""

    def test_returns_help_text(self, bot):
        result = bot.handle_help()
        assert "PDF" in result
        assert "URL" in result
        assert "status" in result
