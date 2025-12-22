# backend/app/api/auth.py
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import get_session
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.session import Session
from app.services.auth.oauth import OAuthService

router = APIRouter(prefix="/auth", tags=["auth"])

# Lazy instantiation to avoid config validation errors in tests
_oauth_service = None


def get_oauth_service() -> OAuthService:
    """Get or create OAuth service singleton."""
    global _oauth_service
    if _oauth_service is None:
        _oauth_service = OAuthService()
    return _oauth_service


# For testing purposes, allow direct access
oauth_service = None


@router.get("/login")
async def login():
    """Redirect to Google OAuth login."""
    service = oauth_service if oauth_service is not None else get_oauth_service()
    url = service.get_authorization_url()
    return RedirectResponse(url=url, status_code=307)


@router.get("/callback")
async def callback(
    code: str,
    response: Response,
    db: AsyncSession = Depends(get_session),
):
    """Handle Google OAuth callback."""
    service = oauth_service if oauth_service is not None else get_oauth_service()

    # Exchange code for tokens
    tokens = await service.exchange_code(code)

    # Get user info from Google
    user_info = await service.get_user_info(tokens["access_token"])

    # Find or create user
    result = await db.execute(
        select(User).where(User.google_id == user_info.google_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Create new user
        user = User(
            email=user_info.email,
            name=user_info.name,
            picture=user_info.picture,
            google_id=user_info.google_id,
            role=UserRole.USER,
        )
        db.add(user)
        await db.flush()
    else:
        # Update existing user info
        user.name = user_info.name
        user.picture = user_info.picture

    # Create session
    session_token = service.generate_session_token()
    token_hash = service.hash_token(session_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_expire_days)

    session = Session(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()

    # Set session cookie and redirect to frontend
    redirect = RedirectResponse(url="http://localhost:5173", status_code=302)
    redirect.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=False,  # Set True in production with HTTPS
        samesite="lax",
        max_age=settings.session_expire_days * 24 * 60 * 60,
    )
    return redirect


@router.post("/logout")
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias="session"),
    db: AsyncSession = Depends(get_session),
):
    """Logout and clear session."""
    if session_token:
        service = oauth_service if oauth_service is not None else get_oauth_service()
        token_hash = service.hash_token(session_token)
        await db.execute(delete(Session).where(Session.token_hash == token_hash))
        await db.commit()

    response.delete_cookie("session")
    return {"message": "Logged out"}


@router.get("/me")
async def get_current_user_info(
    session_token: str | None = Cookie(default=None, alias="session"),
    db: AsyncSession = Depends(get_session),
):
    """Get current authenticated user info."""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    service = oauth_service if oauth_service is not None else get_oauth_service()
    token_hash = service.hash_token(session_token)

    # Find valid session
    result = await db.execute(
        select(Session).where(
            Session.token_hash == token_hash,
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # Get user
    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "role": user.role.value,
    }
