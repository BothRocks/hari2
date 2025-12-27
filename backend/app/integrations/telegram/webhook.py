# backend/app/integrations/telegram/webhook.py
"""Telegram webhook endpoint."""
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update

from app.core.database import get_session
from app.core.config import settings
from app.services.drive.client import DriveService
from app.integrations.telegram.bot import TelegramBot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/telegram", tags=["telegram"])


def get_drive_service() -> DriveService | None:
    """Get Drive service if configured."""
    if settings.google_service_account_json:
        try:
            return DriveService(settings.google_service_account_json)
        except Exception as e:
            logger.warning(f"Failed to initialize Drive service: {e}")
    return None


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Handle incoming Telegram webhook updates.

    Telegram sends updates here when users message the bot.
    """
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")

    try:
        # Parse the update from Telegram
        data = await request.json()
        update = Update.de_json(data, None)

        if update is None:
            logger.warning("Failed to parse Telegram update")
            return {"ok": True}

        # Process the update
        drive_service = get_drive_service()
        bot = TelegramBot(db, drive_service)
        response = await bot.process_update(update)

        # Send response if we have one
        if response and update.effective_chat:
            await send_message(
                chat_id=update.effective_chat.id,
                text=response,
            )

        return {"ok": True}

    except Exception as e:
        logger.exception("Error processing Telegram webhook")
        # Return OK to Telegram to prevent retries
        return {"ok": True, "error": str(e)}


async def send_message(chat_id: int, text: str) -> None:
    """Send a message to a Telegram chat.

    Args:
        chat_id: Telegram chat ID.
        text: Message text.
    """
    if not settings.telegram_bot_token:
        logger.warning("Cannot send message: Telegram bot not configured")
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
            },
        )

        if response.status_code != 200:
            logger.error(f"Failed to send Telegram message: {response.text}")


@router.post("/set-webhook")
async def set_telegram_webhook(webhook_url: str) -> dict:
    """Set the Telegram webhook URL.

    Call this once to configure Telegram to send updates to your server.

    Args:
        webhook_url: Full URL to the webhook endpoint (must be HTTPS).

    Returns:
        Result from Telegram API.
    """
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json={"url": webhook_url},
        )

        return response.json()
