"""Tests for Telegram bot access control."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_unauthorized_user_rejected():
    """Users not in allowlist should be rejected."""
    from app.integrations.telegram.bot import TelegramBot

    with patch("app.integrations.telegram.bot.settings") as mock_settings:
        mock_settings.telegram_allowed_users_set = {111, 222}
        mock_settings.telegram_bot_token = "test-token"

        mock_db = AsyncMock()
        bot = TelegramBot(mock_db)

        mock_update = MagicMock()
        mock_update.effective_user.id = 999  # Not in allowlist
        mock_update.message = None

        response = await bot.process_update(mock_update)

        assert response is not None
        assert "not authorized" in response.lower()


@pytest.mark.asyncio
async def test_authorized_user_allowed():
    """Users in allowlist should be allowed to proceed."""
    from app.integrations.telegram.bot import TelegramBot

    with patch("app.integrations.telegram.bot.settings") as mock_settings:
        mock_settings.telegram_allowed_users_set = {111, 222}
        mock_settings.telegram_bot_token = "test-token"

        mock_db = AsyncMock()
        bot = TelegramBot(mock_db)

        mock_update = MagicMock()
        mock_update.effective_user.id = 111  # In allowlist
        mock_update.message.text = "help"
        mock_update.message.document = None

        response = await bot.process_update(mock_update)

        # Should get help message, not unauthorized
        assert response is not None
        assert "not authorized" not in response.lower()


@pytest.mark.asyncio
async def test_empty_allowlist_allows_all():
    """Empty allowlist should allow all users (dev mode)."""
    from app.integrations.telegram.bot import TelegramBot

    with patch("app.integrations.telegram.bot.settings") as mock_settings:
        mock_settings.telegram_allowed_users_set = set()  # Empty = allow all
        mock_settings.telegram_bot_token = "test-token"

        mock_db = AsyncMock()
        bot = TelegramBot(mock_db)

        mock_update = MagicMock()
        mock_update.effective_user.id = 999  # Any user
        mock_update.message.text = "help"
        mock_update.message.document = None

        response = await bot.process_update(mock_update)

        # Should get help message, not unauthorized
        assert response is not None
        assert "not authorized" not in response.lower()


@pytest.mark.asyncio
async def test_no_user_returns_none():
    """Updates without a user should return None."""
    from app.integrations.telegram.bot import TelegramBot

    with patch("app.integrations.telegram.bot.settings") as mock_settings:
        mock_settings.telegram_allowed_users_set = {111}
        mock_settings.telegram_bot_token = "test-token"

        mock_db = AsyncMock()
        bot = TelegramBot(mock_db)

        mock_update = MagicMock()
        mock_update.effective_user = None

        response = await bot.process_update(mock_update)

        assert response is None


class TestConfigParsing:
    """Test the config parsing for allowed users."""

    def test_parse_comma_separated_users(self):
        """Parse comma-separated user IDs correctly."""
        from app.core.config import Settings

        settings = Settings(telegram_allowed_users="111,222,333")
        assert settings.telegram_allowed_users_set == {111, 222, 333}

    def test_parse_with_whitespace(self):
        """Handle whitespace in user ID list."""
        from app.core.config import Settings

        settings = Settings(telegram_allowed_users="111 , 222 , 333")
        assert settings.telegram_allowed_users_set == {111, 222, 333}

    def test_parse_empty_string(self):
        """Empty string returns empty set."""
        from app.core.config import Settings

        settings = Settings(telegram_allowed_users="")
        assert settings.telegram_allowed_users_set == set()

    def test_parse_none(self):
        """None returns empty set."""
        from app.core.config import Settings

        settings = Settings(telegram_allowed_users=None)
        assert settings.telegram_allowed_users_set == set()

    def test_parse_single_user(self):
        """Single user ID works correctly."""
        from app.core.config import Settings

        settings = Settings(telegram_allowed_users="12345")
        assert settings.telegram_allowed_users_set == {12345}
