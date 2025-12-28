# backend/app/integrations/slack/events.py
"""Slack Events API endpoint."""
import hashlib
import hmac
import logging
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.config import settings
from app.services.drive.client import DriveService
from app.integrations.slack.bot import SlackBot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/slack", tags=["slack"])


def get_drive_service() -> DriveService | None:
    """Get Drive service if configured."""
    if settings.google_service_account_json:
        try:
            return DriveService(settings.google_service_account_json)
        except Exception as e:
            logger.warning(f"Failed to initialize Drive service: {e}")
    return None


def verify_slack_signature(
    body: bytes,
    timestamp: str,
    signature: str,
) -> bool:
    """Verify Slack request signature.

    Args:
        body: Raw request body.
        timestamp: X-Slack-Request-Timestamp header.
        signature: X-Slack-Signature header.

    Returns:
        True if signature is valid.
    """
    if not settings.slack_signing_secret:
        logger.warning("Slack signing secret not configured")
        return False

    # Check timestamp to prevent replay attacks (5 minutes tolerance)
    current_time = time.time()
    if abs(current_time - int(timestamp)) > 300:
        return False

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    expected_signature = (
        "v0="
        + hmac.new(
            settings.slack_signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(expected_signature, signature)


@router.post("/events")
async def slack_events(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Handle Slack Events API requests.

    Handles:
    - URL verification challenge
    - Message events
    - File share events
    """
    # Get raw body for signature verification
    body = await request.body()
    data = await request.json()

    # Handle URL verification first (Slack sends this when setting up the webhook)
    # This must work even without bot token configured
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    # For all other requests, require bot token
    if not settings.slack_bot_token:
        raise HTTPException(status_code=503, detail="Slack bot not configured")

    # Verify signature if signing secret is configured
    if settings.slack_signing_secret:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        if not verify_slack_signature(body, timestamp, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Handle events
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        event_type = event.get("type")

        # Handle @mentions in channels
        if event_type == "app_mention":
            try:
                drive_service = get_drive_service()
                bot = SlackBot(db, drive_service)
                response = await bot.process_mention(event)

                if response:
                    channel = event.get("channel")
                    if channel:
                        await send_message(channel, response)

            except Exception as e:
                logger.exception("Error processing Slack app_mention")

        # Handle DMs (not bot messages or edits, but allow file_share)
        elif event_type == "message" and not event.get("bot_id"):
            subtype = event.get("subtype")
            # Skip message edits and other subtypes, but allow file_share and no subtype
            if subtype and subtype != "file_share":
                return {"ok": True}
            # Only process DMs (channel type 'im')
            channel_type = event.get("channel_type")
            if channel_type == "im":
                try:
                    drive_service = get_drive_service()
                    bot = SlackBot(db, drive_service)
                    response = await bot.process_message(event)

                    if response:
                        channel = event.get("channel")
                        if channel:
                            await send_message(channel, response)

                except Exception as e:
                    logger.exception("Error processing Slack DM")

    return {"ok": True}


async def send_message(channel: str, text: str) -> None:
    """Send a message to a Slack channel.

    Args:
        channel: Slack channel ID.
        text: Message text.
    """
    if not settings.slack_bot_token:
        logger.warning("Cannot send message: Slack bot not configured")
        return

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
            json={
                "channel": channel,
                "text": text,
            },
        )

        data = response.json()
        if not data.get("ok"):
            logger.error(f"Failed to send Slack message: {data.get('error')}")
