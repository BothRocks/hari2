# backend/tests/test_webhook_performance.py
"""Tests for webhook performance optimizations.

These tests verify that DriveService is only initialized when needed
(i.e., for PDF uploads) and not for status checks or URL submissions.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


@pytest.fixture
def mock_telegram_settings():
    """Mock settings for Telegram tests."""
    with patch("app.integrations.telegram.webhook.settings") as mock_settings:
        mock_settings.telegram_bot_token = "test-token"
        mock_settings.google_service_account_json = "test-credentials.json"
        yield mock_settings


@pytest.fixture
def mock_slack_settings():
    """Mock settings for Slack tests."""
    with patch("app.integrations.slack.events.settings") as mock_settings:
        mock_settings.slack_bot_token = "xoxb-test-token"
        mock_settings.slack_signing_secret = None  # Disable signature verification
        mock_settings.google_service_account_json = "test-credentials.json"
        yield mock_settings


class TestTelegramLazyDriveService:
    """Tests for lazy DriveService initialization in Telegram webhook."""

    @pytest.mark.asyncio
    async def test_status_command_does_not_init_drive_service(
        self, mock_telegram_settings
    ):
        """Status command should NOT initialize DriveService."""
        with patch(
            "app.integrations.telegram.webhook.get_drive_service"
        ) as mock_get_drive:
            with patch(
                "app.integrations.telegram.webhook.TelegramBot"
            ) as mock_bot_class:
                # Setup mock bot
                mock_bot = AsyncMock()
                mock_bot.process_update = AsyncMock(return_value="Status: OK")
                mock_bot_class.return_value = mock_bot

                # Import after patching
                from app.integrations.telegram.webhook import telegram_webhook

                # Create a mock request with status message
                mock_request = AsyncMock()
                mock_request.json = AsyncMock(
                    return_value={
                        "update_id": 123,
                        "message": {
                            "message_id": 1,
                            "from": {"id": 12345, "is_bot": False, "first_name": "Test"},
                            "chat": {"id": 12345, "type": "private"},
                            "date": 1234567890,
                            "text": "status",
                        },
                    }
                )

                mock_db = AsyncMock()

                # Call the webhook
                result = await telegram_webhook(mock_request, mock_db)

                # DriveService should NOT have been initialized
                mock_get_drive.assert_not_called()
                assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_url_submission_does_not_init_drive_service(
        self, mock_telegram_settings
    ):
        """URL submission should NOT initialize DriveService."""
        with patch(
            "app.integrations.telegram.webhook.get_drive_service"
        ) as mock_get_drive:
            with patch(
                "app.integrations.telegram.webhook.TelegramBot"
            ) as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot.process_update = AsyncMock(return_value="URL queued")
                mock_bot_class.return_value = mock_bot

                from app.integrations.telegram.webhook import telegram_webhook

                mock_request = AsyncMock()
                mock_request.json = AsyncMock(
                    return_value={
                        "update_id": 124,
                        "message": {
                            "message_id": 2,
                            "from": {"id": 12345, "is_bot": False, "first_name": "Test"},
                            "chat": {"id": 12345, "type": "private"},
                            "date": 1234567890,
                            "text": "https://example.com/article",
                        },
                    }
                )

                mock_db = AsyncMock()

                result = await telegram_webhook(mock_request, mock_db)

                # DriveService should NOT have been initialized
                mock_get_drive.assert_not_called()
                assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_pdf_upload_initializes_drive_service(self, mock_telegram_settings):
        """PDF upload SHOULD initialize DriveService."""
        with patch(
            "app.integrations.telegram.webhook.get_drive_service"
        ) as mock_get_drive:
            mock_get_drive.return_value = MagicMock()

            with patch(
                "app.integrations.telegram.webhook.TelegramBot"
            ) as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot.process_update = AsyncMock(return_value="PDF processing...")
                mock_bot_class.return_value = mock_bot

                from app.integrations.telegram.webhook import telegram_webhook

                mock_request = AsyncMock()
                mock_request.json = AsyncMock(
                    return_value={
                        "update_id": 125,
                        "message": {
                            "message_id": 3,
                            "from": {"id": 12345, "is_bot": False, "first_name": "Test"},
                            "chat": {"id": 12345, "type": "private"},
                            "date": 1234567890,
                            "document": {
                                "file_id": "abc123",
                                "file_unique_id": "xyz",
                                "file_name": "test.pdf",
                                "mime_type": "application/pdf",
                                "file_size": 1024,
                            },
                        },
                    }
                )

                mock_db = AsyncMock()

                result = await telegram_webhook(mock_request, mock_db)

                # DriveService SHOULD have been initialized for PDF
                mock_get_drive.assert_called_once()
                assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_non_pdf_document_does_not_init_drive_service(
        self, mock_telegram_settings
    ):
        """Non-PDF document should NOT initialize DriveService."""
        with patch(
            "app.integrations.telegram.webhook.get_drive_service"
        ) as mock_get_drive:
            with patch(
                "app.integrations.telegram.webhook.TelegramBot"
            ) as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot.process_update = AsyncMock(
                    return_value="Only PDFs are supported"
                )
                mock_bot_class.return_value = mock_bot

                from app.integrations.telegram.webhook import telegram_webhook

                mock_request = AsyncMock()
                mock_request.json = AsyncMock(
                    return_value={
                        "update_id": 126,
                        "message": {
                            "message_id": 4,
                            "from": {"id": 12345, "is_bot": False, "first_name": "Test"},
                            "chat": {"id": 12345, "type": "private"},
                            "date": 1234567890,
                            "document": {
                                "file_id": "abc124",
                                "file_unique_id": "xyz2",
                                "file_name": "test.docx",
                                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                "file_size": 2048,
                            },
                        },
                    }
                )

                mock_db = AsyncMock()

                result = await telegram_webhook(mock_request, mock_db)

                # DriveService should NOT have been initialized for non-PDF
                mock_get_drive.assert_not_called()
                assert result == {"ok": True}


class TestSlackLazyDriveService:
    """Tests for lazy DriveService initialization in Slack events."""

    @pytest.mark.asyncio
    async def test_status_dm_does_not_init_drive_service(self, mock_slack_settings):
        """Status DM should NOT initialize DriveService."""
        with patch(
            "app.integrations.slack.events.get_drive_service"
        ) as mock_get_drive:
            with patch("app.integrations.slack.events.SlackBot") as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot.process_message = AsyncMock(return_value="Status: OK")
                mock_bot_class.return_value = mock_bot

                from app.integrations.slack.events import slack_events

                mock_request = AsyncMock()
                mock_request.body = AsyncMock(return_value=b'{}')
                mock_request.json = AsyncMock(
                    return_value={
                        "type": "event_callback",
                        "event": {
                            "type": "message",
                            "user": "U12345",
                            "text": "status",
                            "channel": "D12345",
                            "channel_type": "im",
                        },
                    }
                )
                mock_request.headers = {}

                mock_db = AsyncMock()

                result = await slack_events(mock_request, mock_db)

                # DriveService should NOT have been initialized
                mock_get_drive.assert_not_called()
                assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_url_dm_does_not_init_drive_service(self, mock_slack_settings):
        """URL DM should NOT initialize DriveService."""
        with patch(
            "app.integrations.slack.events.get_drive_service"
        ) as mock_get_drive:
            with patch("app.integrations.slack.events.SlackBot") as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot.process_message = AsyncMock(return_value="URL queued")
                mock_bot_class.return_value = mock_bot

                from app.integrations.slack.events import slack_events

                mock_request = AsyncMock()
                mock_request.body = AsyncMock(return_value=b'{}')
                mock_request.json = AsyncMock(
                    return_value={
                        "type": "event_callback",
                        "event": {
                            "type": "message",
                            "user": "U12345",
                            "text": "<https://example.com|example.com>",
                            "channel": "D12345",
                            "channel_type": "im",
                        },
                    }
                )
                mock_request.headers = {}

                mock_db = AsyncMock()

                result = await slack_events(mock_request, mock_db)

                # DriveService should NOT have been initialized
                mock_get_drive.assert_not_called()
                assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_pdf_upload_initializes_drive_service(self, mock_slack_settings):
        """PDF file upload SHOULD initialize DriveService."""
        with patch(
            "app.integrations.slack.events.get_drive_service"
        ) as mock_get_drive:
            mock_get_drive.return_value = MagicMock()

            with patch("app.integrations.slack.events.SlackBot") as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot.process_message = AsyncMock(return_value="PDF processing...")
                mock_bot_class.return_value = mock_bot

                from app.integrations.slack.events import slack_events

                mock_request = AsyncMock()
                mock_request.body = AsyncMock(return_value=b'{}')
                mock_request.json = AsyncMock(
                    return_value={
                        "type": "event_callback",
                        "event": {
                            "type": "message",
                            "subtype": "file_share",
                            "user": "U12345",
                            "text": "",
                            "channel": "D12345",
                            "channel_type": "im",
                            "files": [
                                {
                                    "id": "F12345",
                                    "name": "document.pdf",
                                    "mimetype": "application/pdf",
                                    "url_private": "https://files.slack.com/...",
                                }
                            ],
                        },
                    }
                )
                mock_request.headers = {}

                mock_db = AsyncMock()

                result = await slack_events(mock_request, mock_db)

                # DriveService SHOULD have been initialized for PDF
                mock_get_drive.assert_called_once()
                assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_non_pdf_file_does_not_init_drive_service(self, mock_slack_settings):
        """Non-PDF file upload should NOT initialize DriveService."""
        with patch(
            "app.integrations.slack.events.get_drive_service"
        ) as mock_get_drive:
            with patch("app.integrations.slack.events.SlackBot") as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot.process_message = AsyncMock(
                    return_value="Only PDFs supported"
                )
                mock_bot_class.return_value = mock_bot

                from app.integrations.slack.events import slack_events

                mock_request = AsyncMock()
                mock_request.body = AsyncMock(return_value=b'{}')
                mock_request.json = AsyncMock(
                    return_value={
                        "type": "event_callback",
                        "event": {
                            "type": "message",
                            "subtype": "file_share",
                            "user": "U12345",
                            "text": "",
                            "channel": "D12345",
                            "channel_type": "im",
                            "files": [
                                {
                                    "id": "F12346",
                                    "name": "document.docx",
                                    "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    "url_private": "https://files.slack.com/...",
                                }
                            ],
                        },
                    }
                )
                mock_request.headers = {}

                mock_db = AsyncMock()

                result = await slack_events(mock_request, mock_db)

                # DriveService should NOT have been initialized for non-PDF
                mock_get_drive.assert_not_called()
                assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_app_mention_with_url_does_not_init_drive_service(
        self, mock_slack_settings
    ):
        """App mention with URL should NOT initialize DriveService."""
        with patch(
            "app.integrations.slack.events.get_drive_service"
        ) as mock_get_drive:
            with patch("app.integrations.slack.events.SlackBot") as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot.process_mention = AsyncMock(return_value="URL queued")
                mock_bot_class.return_value = mock_bot

                from app.integrations.slack.events import slack_events

                mock_request = AsyncMock()
                mock_request.body = AsyncMock(return_value=b'{}')
                mock_request.json = AsyncMock(
                    return_value={
                        "type": "event_callback",
                        "event": {
                            "type": "app_mention",
                            "user": "U12345",
                            "text": "<@U67890> <https://example.com|link>",
                            "channel": "C12345",
                        },
                    }
                )
                mock_request.headers = {}

                mock_db = AsyncMock()

                result = await slack_events(mock_request, mock_db)

                # DriveService should NOT have been initialized
                mock_get_drive.assert_not_called()
                assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_app_mention_with_pdf_initializes_drive_service(
        self, mock_slack_settings
    ):
        """App mention with PDF file SHOULD initialize DriveService."""
        with patch(
            "app.integrations.slack.events.get_drive_service"
        ) as mock_get_drive:
            mock_get_drive.return_value = MagicMock()

            with patch("app.integrations.slack.events.SlackBot") as mock_bot_class:
                mock_bot = AsyncMock()
                mock_bot.process_mention = AsyncMock(return_value="PDF processing...")
                mock_bot_class.return_value = mock_bot

                from app.integrations.slack.events import slack_events

                mock_request = AsyncMock()
                mock_request.body = AsyncMock(return_value=b'{}')
                mock_request.json = AsyncMock(
                    return_value={
                        "type": "event_callback",
                        "event": {
                            "type": "app_mention",
                            "user": "U12345",
                            "text": "<@U67890>",
                            "channel": "C12345",
                            "files": [
                                {
                                    "id": "F12347",
                                    "name": "report.pdf",
                                    "mimetype": "application/pdf",
                                    "url_private": "https://files.slack.com/...",
                                }
                            ],
                        },
                    }
                )
                mock_request.headers = {}

                mock_db = AsyncMock()

                result = await slack_events(mock_request, mock_db)

                # DriveService SHOULD have been initialized for PDF
                mock_get_drive.assert_called_once()
                assert result == {"ok": True}


class TestHasPdfFiles:
    """Tests for the _has_pdf_files helper function."""

    def test_empty_list(self):
        """Empty list returns False."""
        from app.integrations.slack.events import _has_pdf_files

        assert _has_pdf_files([]) is False

    def test_pdf_file(self):
        """PDF file returns True."""
        from app.integrations.slack.events import _has_pdf_files

        files = [{"name": "doc.pdf", "mimetype": "application/pdf"}]
        assert _has_pdf_files(files) is True

    def test_non_pdf_file(self):
        """Non-PDF file returns False."""
        from app.integrations.slack.events import _has_pdf_files

        files = [{"name": "doc.docx", "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}]
        assert _has_pdf_files(files) is False

    def test_mixed_files_with_pdf(self):
        """Mixed files with at least one PDF returns True."""
        from app.integrations.slack.events import _has_pdf_files

        files = [
            {"name": "image.png", "mimetype": "image/png"},
            {"name": "doc.pdf", "mimetype": "application/pdf"},
            {"name": "data.csv", "mimetype": "text/csv"},
        ]
        assert _has_pdf_files(files) is True

    def test_mixed_files_without_pdf(self):
        """Mixed files without PDF returns False."""
        from app.integrations.slack.events import _has_pdf_files

        files = [
            {"name": "image.png", "mimetype": "image/png"},
            {"name": "data.csv", "mimetype": "text/csv"},
        ]
        assert _has_pdf_files(files) is False

    def test_file_without_mimetype(self):
        """File without mimetype field returns False."""
        from app.integrations.slack.events import _has_pdf_files

        files = [{"name": "unknown"}]
        assert _has_pdf_files(files) is False
