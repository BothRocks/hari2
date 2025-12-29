# backend/app/integrations/telegram/bot.py
"""Telegram bot implementation."""
import logging
from telegram import Update
from telegram.ext import Application

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.bot_base import BotBase
from app.services.drive.client import DriveService
from app.core.config import settings

logger = logging.getLogger(__name__)


class TelegramBot(BotBase):
    """Telegram bot for document ingestion."""

    platform = "telegram"

    def __init__(self, db: AsyncSession, drive_service: DriveService | None = None):
        super().__init__(db, drive_service)

    async def process_update(self, update: Update) -> str | None:
        """Process a Telegram update and return response message.

        Args:
            update: Telegram Update object.

        Returns:
            Response message to send, or None if no response needed.
        """
        # Get user ID
        if update.effective_user is None:
            logger.warning("Received update without user")
            return None

        user_id_int = update.effective_user.id

        # Access control check
        allowed_users = settings.telegram_allowed_users_set
        if allowed_users and user_id_int not in allowed_users:
            logger.warning(f"Unauthorized Telegram user: {user_id_int}")
            return "You are not authorized to use this bot."

        user_id = str(user_id_int)

        # Handle document (PDF file)
        if update.message and update.message.document:
            doc = update.message.document

            # Only handle PDFs
            if doc.mime_type != "application/pdf":
                return "I can only process PDF files. Please send a PDF document."

            # Download the file
            try:
                app = Application.builder().token(settings.telegram_bot_token).build()
                file = await app.bot.get_file(doc.file_id)
                file_bytes = await file.download_as_bytearray()

                return await self.handle_file(
                    user_id=user_id,
                    file_bytes=bytes(file_bytes),
                    filename=doc.file_name or "document.pdf",
                )
            except Exception as e:
                logger.exception("Error downloading Telegram file")
                return f"Error downloading file: {str(e)}"

        # Handle text message
        if update.message and update.message.text:
            text = update.message.text.strip()

            # Status request
            if self.is_status_request(text):
                return await self.handle_status(user_id)

            # Search command
            if self.is_search_command(text):
                query = self.extract_search_query(text)
                return await self.handle_search(query)

            # URL
            if self.is_url(text):
                return await self.handle_url(user_id, text)

            # Unknown - show help
            return self.handle_help()

        return None
