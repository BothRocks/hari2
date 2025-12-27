# backend/app/integrations/user_state.py
"""Simple in-memory state tracking for chatbot users."""
from dataclasses import dataclass
from uuid import UUID


@dataclass
class UserUpload:
    """Tracks a user's last upload."""

    job_id: UUID
    filename: str


# In-memory state: "{platform}:{user_id}" -> UserUpload
# e.g., "telegram:123456" or "slack:U12345"
_user_state: dict[str, UserUpload] = {}


def set_last_upload(platform: str, user_id: str, job_id: UUID, filename: str) -> None:
    """Store the last upload for a user.

    Args:
        platform: Platform identifier ("telegram" or "slack").
        user_id: Platform-specific user ID.
        job_id: HARI job ID for the upload.
        filename: Original filename or URL.
    """
    key = f"{platform}:{user_id}"
    _user_state[key] = UserUpload(job_id=job_id, filename=filename)


def get_last_upload(platform: str, user_id: str) -> UserUpload | None:
    """Get the last upload for a user.

    Args:
        platform: Platform identifier ("telegram" or "slack").
        user_id: Platform-specific user ID.

    Returns:
        UserUpload if found, None otherwise.
    """
    key = f"{platform}:{user_id}"
    return _user_state.get(key)


def clear_user_state(platform: str, user_id: str) -> None:
    """Clear state for a user (for testing).

    Args:
        platform: Platform identifier.
        user_id: Platform-specific user ID.
    """
    key = f"{platform}:{user_id}"
    _user_state.pop(key, None)


def clear_all_state() -> None:
    """Clear all state (for testing)."""
    _user_state.clear()
