# backend/app/integrations/slack/bot.py
"""Slack bot implementation."""
import logging
import re
import httpx

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.bot_base import BotBase
from app.services.drive.client import DriveService
from app.core.config import settings

logger = logging.getLogger(__name__)

# Regex to extract URLs from Slack messages (Slack wraps URLs in <url|text> or <url>)
SLACK_URL_PATTERN = re.compile(r"<(https?://[^|>]+)(?:\|[^>]*)?>")
# Regex to strip @mentions from text
MENTION_PATTERN = re.compile(r"<@[A-Z0-9]+>")


class SlackBot(BotBase):
    """Slack bot for document ingestion."""

    platform = "slack"

    def __init__(self, db: AsyncSession, drive_service: DriveService | None = None):
        super().__init__(db, drive_service)

    async def process_message(self, event: dict) -> str | None:
        """Process a Slack DM event.

        Args:
            event: Slack event payload.

        Returns:
            Response message, or None if no response needed.
        """
        user_id = event.get("user")
        if not user_id:
            return None

        text = event.get("text", "").strip()
        files = event.get("files", [])
        logger.info(f"Slack DM received - text: {repr(text)}, files: {len(files)}, event keys: {list(event.keys())}")

        # Check for file shares
        if files:
            return await self._handle_files(user_id, files)

        # Status request
        if self.is_status_request(text):
            return await self.handle_status(user_id)

        # Extract URLs from Slack's formatted text <url|display> or <url>
        urls = SLACK_URL_PATTERN.findall(text)
        if urls:
            return await self.handle_url(user_id, urls[0])

        # Fallback: check for plain URL (in case Slack doesn't wrap it)
        if self.is_url(text):
            return await self.handle_url(user_id, text)

        # Unknown
        return self.handle_help()

    async def process_mention(self, event: dict) -> str | None:
        """Process a Slack @mention event in a channel.

        Args:
            event: Slack app_mention event payload.

        Returns:
            Response message, or None if no response needed.
        """
        user_id = event.get("user")
        if not user_id:
            return None

        text = event.get("text", "")

        # Check for file shares (user can @mention with a file)
        files = event.get("files", [])
        if files:
            return await self._handle_files(user_id, files)

        # Extract URLs from Slack's formatted text <url|display> or <url>
        urls = SLACK_URL_PATTERN.findall(text)
        if urls:
            # Process the first URL found
            return await self.handle_url(user_id, urls[0])

        # Strip the @mention and check remaining text
        clean_text = MENTION_PATTERN.sub("", text).strip()

        # Status request
        if self.is_status_request(clean_text):
            return await self.handle_status(user_id)

        # Check if remaining text is a plain URL (shouldn't happen, but fallback)
        if self.is_url(clean_text):
            return await self.handle_url(user_id, clean_text)

        # No URL found
        return (
            "Send me a URL to add to the knowledge base!\n\n"
            "Example: `@HARI https://example.com/article`\n\n"
            "Or DM me directly to upload PDFs."
        )

    async def _handle_files(self, user_id: str, files: list[dict]) -> str:
        """Handle file uploads from Slack.

        Args:
            user_id: Slack user ID.
            files: List of Slack file objects.

        Returns:
            Response message.
        """
        # Only process the first PDF
        for file in files:
            if file.get("mimetype") == "application/pdf":
                return await self._download_and_process_file(user_id, file)

        return "I can only process PDF files. Please upload a PDF document."

    async def _download_and_process_file(self, user_id: str, file: dict) -> str:
        """Download a file from Slack and process it.

        Args:
            user_id: Slack user ID.
            file: Slack file object.

        Returns:
            Response message.
        """
        if not settings.slack_bot_token:
            return "Slack bot not properly configured."

        url_private = file.get("url_private")
        if not url_private:
            return "Could not get file download URL."

        filename = file.get("name", "document.pdf")

        try:
            # Download file from Slack (requires bot token for auth, follow redirects)
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(
                    url_private,
                    headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
                )
                response.raise_for_status()
                file_bytes = response.content

            return await self.handle_file(user_id, file_bytes, filename)

        except httpx.HTTPError as e:
            logger.exception("Error downloading Slack file")
            return f"Error downloading file: {str(e)}"
