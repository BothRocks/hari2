# backend/tests/test_deps.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_api_key_header,
    get_current_user,
    get_current_user_from_session,
    require_user,
    require_admin,
)
from app.models.user import User, UserRole
from app.models.session import Session
from app.services.auth.oauth import OAuthService


def test_get_api_key_header_exists():
    """Test that get_api_key_header function exists"""
    assert get_api_key_header is not None


@pytest.mark.asyncio
async def test_get_api_key_header_returns_api_key():
    """Test that get_api_key_header returns the API key when provided"""
    api_key = "test-api-key-123"
    result = await get_api_key_header(api_key=api_key)
    assert result == api_key


@pytest.mark.asyncio
async def test_get_api_key_header_returns_none_when_missing():
    """Test that get_api_key_header returns None when API key is missing"""
    result = await get_api_key_header(api_key=None)
    assert result is None


@pytest.mark.asyncio
async def test_get_current_user_with_admin_api_key():
    """Test that admin API key returns a virtual admin user"""
    from app.core.config import settings

    mock_db = MagicMock(spec=AsyncSession)

    user = await get_current_user(db=mock_db, api_key=settings.admin_api_key, session_user=None)

    assert user is not None
    assert user.email == "admin@system"
    assert user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_get_current_user_with_valid_user_api_key():
    """Test that valid user API key returns the user from database"""
    user_api_key = "user-api-key-456"
    user_id = uuid4()

    # Create a mock user
    mock_user = User(
        id=user_id,
        email="test@example.com",
        role=UserRole.USER,
        is_active=True,
        api_key=user_api_key
    )

    # Create mock session and result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.execute = AsyncMock(return_value=mock_result)

    user = await get_current_user(db=mock_db, api_key=user_api_key, session_user=None)

    assert user is not None
    assert user.email == "test@example.com"
    assert user.role == UserRole.USER
    assert user.api_key == user_api_key


@pytest.mark.asyncio
async def test_get_current_user_with_invalid_api_key():
    """Test that invalid API key returns None"""
    invalid_key = "invalid-key-789"

    # Create mock session with no user found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.execute = AsyncMock(return_value=mock_result)

    user = await get_current_user(db=mock_db, api_key=invalid_key, session_user=None)

    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_with_no_api_key():
    """Test that missing API key returns None"""
    mock_db = MagicMock(spec=AsyncSession)

    user = await get_current_user(db=mock_db, api_key=None, session_user=None)

    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_with_inactive_user():
    """Test that inactive user returns None even with valid API key"""
    user_api_key = "inactive-user-key"

    # Create mock session with no user found (inactive users filtered out)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.execute = AsyncMock(return_value=mock_result)

    user = await get_current_user(db=mock_db, api_key=user_api_key, session_user=None)

    assert user is None


@pytest.mark.asyncio
async def test_require_user_with_valid_user():
    """Test that require_user returns user when authenticated"""
    mock_user = User(
        id=uuid4(),
        email="test@example.com",
        role=UserRole.USER,
        is_active=True
    )

    user = await require_user(user=mock_user)

    assert user == mock_user


@pytest.mark.asyncio
async def test_require_user_raises_401_when_no_user():
    """Test that require_user raises 401 when user is None"""
    with pytest.raises(HTTPException) as exc_info:
        await require_user(user=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or missing authentication"


@pytest.mark.asyncio
async def test_require_admin_with_admin_user():
    """Test that require_admin returns admin user"""
    mock_admin = User(
        id=uuid4(),
        email="admin@example.com",
        role=UserRole.ADMIN,
        is_active=True
    )

    user = await require_admin(user=mock_admin)

    assert user == mock_admin
    assert user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_require_admin_raises_403_for_non_admin():
    """Test that require_admin raises 403 for regular users"""
    mock_user = User(
        id=uuid4(),
        email="user@example.com",
        role=UserRole.USER,
        is_active=True
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_admin(user=mock_user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Admin access required"


@pytest.mark.asyncio
async def test_get_current_user_from_session_cookie():
    """Test that valid session cookie returns the user"""
    user_id = uuid4()
    session_token = "test-session-token"
    token_hash = "hashed-token"

    # Create mock user
    mock_user = User(
        id=user_id,
        email="test@example.com",
        role=UserRole.USER,
        is_active=True
    )

    # Create mock session
    mock_session_obj = Session(
        id=uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )

    # Mock database session with two queries (session lookup, then user lookup)
    mock_db = MagicMock(spec=AsyncSession)

    mock_session_result = MagicMock()
    mock_session_result.scalar_one_or_none.return_value = mock_session_obj

    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user

    # First call returns session, second call returns user
    mock_db.execute = AsyncMock(side_effect=[mock_session_result, mock_user_result])

    # Mock OAuth service
    mock_oauth = MagicMock(spec=OAuthService)
    mock_oauth.hash_token.return_value = token_hash

    user = await get_current_user_from_session(
        session_token=session_token,
        db=mock_db,
        oauth=mock_oauth
    )

    assert user is not None
    assert user.email == "test@example.com"
    assert user.id == user_id
    mock_oauth.hash_token.assert_called_once_with(session_token)


@pytest.mark.asyncio
async def test_get_current_user_from_session_cookie_no_token():
    """Test that missing session cookie returns None"""
    mock_db = MagicMock(spec=AsyncSession)
    mock_oauth = MagicMock(spec=OAuthService)

    user = await get_current_user_from_session(
        session_token=None,
        db=mock_db,
        oauth=mock_oauth
    )

    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_from_session_cookie_expired():
    """Test that expired session cookie returns None"""
    session_token = "test-session-token"
    token_hash = "hashed-token"

    # Mock database with no session found (expired sessions filtered out)
    mock_db = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Mock OAuth service
    mock_oauth = MagicMock(spec=OAuthService)
    mock_oauth.hash_token.return_value = token_hash

    user = await get_current_user_from_session(
        session_token=session_token,
        db=mock_db,
        oauth=mock_oauth
    )

    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_prefers_session_over_api_key():
    """Test that session cookie takes precedence over API key"""
    user_id = uuid4()

    # Create a mock user from session
    session_user = User(
        id=user_id,
        email="session@example.com",
        role=UserRole.USER,
        is_active=True
    )

    # Mock database (shouldn't be called since session user is provided)
    mock_db = MagicMock(spec=AsyncSession)

    user = await get_current_user(
        db=mock_db,
        api_key="some-api-key",
        session_user=session_user
    )

    assert user is not None
    assert user.email == "session@example.com"
    # Verify database was not queried for API key
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_require_user_updated_error_message():
    """Test that require_user error message is updated for both auth methods"""
    with pytest.raises(HTTPException) as exc_info:
        await require_user(user=None)

    assert exc_info.value.status_code == 401
    assert "Invalid or missing authentication" in exc_info.value.detail
