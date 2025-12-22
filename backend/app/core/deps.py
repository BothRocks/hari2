# backend/app/core/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_session
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.user import User, UserRole

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key_header(
    api_key: str | None = Depends(api_key_header),
) -> str | None:
    return api_key


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    api_key: str | None = Depends(get_api_key_header),
) -> User | None:
    if not api_key:
        return None

    # Check admin API key
    if api_key == settings.admin_api_key:
        # Return a virtual admin user
        return User(email="admin@system", role=UserRole.ADMIN)

    # Check user API key
    result = await session.execute(
        select(User).where(User.api_key == api_key, User.is_active == True)
    )
    return result.scalar_one_or_none()


async def require_user(
    user: User | None = Depends(get_current_user),
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
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
