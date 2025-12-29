# backend/app/core/deps.py
from datetime import datetime, timezone
from uuid import UUID
import secrets
from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_session
from app.core.config import settings
from app.core.security import verify_api_key_hash
from app.models.user import User, UserRole
from app.models.session import Session
from app.services.auth.oauth import OAuthService

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_oauth_service() -> OAuthService:
    """Dependency for OAuth service."""
    return OAuthService()


async def get_api_key_header(
    api_key: str | None = Depends(api_key_header),
) -> str | None:
    return api_key


async def get_current_user_from_session(
    session_token: str | None = Cookie(default=None, alias="session"),
    db: AsyncSession = Depends(get_session),
    oauth: OAuthService = Depends(get_oauth_service),
) -> User | None:
    """Get user from session cookie."""
    if not session_token:
        return None

    token_hash = oauth.hash_token(session_token)

    result = await db.execute(
        select(Session).where(
            Session.token_hash == token_hash,
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        return None

    result = await db.execute(
        select(User).where(User.id == session.user_id, User.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def get_current_user(
    db: AsyncSession = Depends(get_session),
    api_key: str | None = Depends(get_api_key_header),
    session_user: User | None = Depends(get_current_user_from_session),
) -> User | None:
    """Get current user from API key OR session cookie."""
    # Session takes precedence if present
    if session_user:
        return session_user

    if not api_key:
        return None

    # Check admin API key
    if settings.admin_api_key and secrets.compare_digest(api_key, settings.admin_api_key):
        # Return a virtual admin user
        return User(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            email="admin@system",
            role=UserRole.ADMIN
        )

    # Check user API key (try hash first, then legacy plaintext)
    result = await db.execute(
        select(User).where(User.is_active.is_(True))
    )
    users = result.scalars().all()

    for user in users:
        # Check hashed key first
        if user.api_key_hash and verify_api_key_hash(api_key, user.api_key_hash):
            return user
        # Legacy: check plaintext (to be removed after migration)
        if user.api_key and secrets.compare_digest(api_key, user.api_key):
            return user

    return None


async def require_user(
    user: User | None = Depends(get_current_user),
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication",
        )
    return user


async def require_admin(
    user: User = Depends(require_user),
) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
