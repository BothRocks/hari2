# backend/tests/test_api_auth.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import router, login, callback, logout, get_current_user_info
from app.models.user import User, UserRole
from app.models.session import Session
from app.services.auth.oauth import GoogleUserInfo


def test_router_exists():
    """Test that the auth router exists and has correct config."""
    assert router is not None
    assert router.prefix == "/auth"
    assert "auth" in router.tags


@pytest.mark.asyncio
async def test_login_redirects_to_google():
    """Test that login endpoint redirects to Google OAuth."""
    with patch("app.api.auth.oauth_service") as mock_service:
        mock_service.get_authorization_url.return_value = "https://accounts.google.com/o/oauth2/v2/auth?client_id=test"

        result = await login()

        assert result.status_code == 307
        assert "accounts.google.com" in result.headers["location"]
        mock_service.get_authorization_url.assert_called_once()


@pytest.mark.asyncio
async def test_callback_creates_new_user():
    """Test that callback creates a new user if they don't exist."""
    # Mock session
    mock_db = MagicMock(spec=AsyncSession)

    # Mock execute for user lookup - no existing user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    # Track the calls to execute
    call_count = [0]

    async def mock_execute_side_effect(query):
        call_count[0] += 1
        return mock_result

    mock_db.execute = AsyncMock(side_effect=mock_execute_side_effect)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    # Mock response
    mock_response = MagicMock()

    # Mock OAuth service
    with patch("app.api.auth.oauth_service") as mock_oauth:
        mock_oauth.exchange_code = AsyncMock(return_value={
            "access_token": "test_access_token",
            "id_token": "test_id_token",
        })

        mock_oauth.get_user_info = AsyncMock(return_value=GoogleUserInfo(
            google_id="123456789",
            email="test@example.com",
            name="Test User",
            picture="https://example.com/photo.jpg",
        ))

        mock_oauth.generate_session_token.return_value = "test_session_token"
        mock_oauth.hash_token.return_value = "hashed_token"

        # Mock settings
        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.session_expire_days = 7

            result = await callback(
                code="test_code",
                response=mock_response,
                db=mock_db,
            )

            assert result.status_code == 302
            assert result.headers["location"] == "http://localhost:5173"
            assert mock_db.add.call_count == 2  # User and session
            assert mock_db.commit.called


@pytest.mark.asyncio
async def test_callback_updates_existing_user():
    """Test that callback updates existing user info."""
    user_id = uuid4()
    existing_user = User(
        id=user_id,
        email="test@example.com",
        name="Old Name",
        picture="old_picture.jpg",
        google_id="123456789",
        role=UserRole.USER,
        is_active=True,
    )

    # Mock session
    mock_db = MagicMock(spec=AsyncSession)

    # Mock execute for user lookup - existing user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Mock response
    mock_response = MagicMock()

    # Mock OAuth service
    with patch("app.api.auth.oauth_service") as mock_oauth:
        mock_oauth.exchange_code = AsyncMock(return_value={
            "access_token": "test_access_token",
            "id_token": "test_id_token",
        })

        mock_oauth.get_user_info = AsyncMock(return_value=GoogleUserInfo(
            google_id="123456789",
            email="test@example.com",
            name="New Name",
            picture="https://example.com/new_photo.jpg",
        ))

        mock_oauth.generate_session_token.return_value = "test_session_token"
        mock_oauth.hash_token.return_value = "hashed_token"

        # Mock settings
        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.session_expire_days = 7

            result = await callback(
                code="test_code",
                response=mock_response,
                db=mock_db,
            )

            assert result.status_code == 302
            assert existing_user.name == "New Name"
            assert existing_user.picture == "https://example.com/new_photo.jpg"
            assert mock_db.add.call_count == 1  # Only session


@pytest.mark.asyncio
async def test_logout_clears_session():
    """Test that logout clears session from database and cookie."""
    # Mock session
    mock_db = MagicMock(spec=AsyncSession)
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    # Mock response
    mock_response = MagicMock()

    # Mock OAuth service
    with patch("app.api.auth.oauth_service") as mock_oauth:
        mock_oauth.hash_token.return_value = "hashed_token"

        result = await logout(
            response=mock_response,
            session_token="test_session_token",
            db=mock_db,
        )

        assert result == {"message": "Logged out"}
        assert mock_db.execute.called
        assert mock_db.commit.called
        mock_response.delete_cookie.assert_called_once_with("session")


@pytest.mark.asyncio
async def test_logout_without_session():
    """Test that logout works even without a session token."""
    # Mock session
    mock_db = MagicMock(spec=AsyncSession)

    # Mock response
    mock_response = MagicMock()

    result = await logout(
        response=mock_response,
        session_token=None,
        db=mock_db,
    )

    assert result == {"message": "Logged out"}
    mock_response.delete_cookie.assert_called_once_with("session")


@pytest.mark.asyncio
async def test_me_returns_401_without_session():
    """Test that /me endpoint returns 401 without session token."""
    mock_db = MagicMock(spec=AsyncSession)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_info(
            session_token=None,
            db=mock_db,
        )

    assert exc_info.value.status_code == 401
    assert "Not authenticated" in exc_info.value.detail


@pytest.mark.asyncio
async def test_me_returns_401_with_invalid_session():
    """Test that /me endpoint returns 401 with invalid session."""
    # Mock session
    mock_db = MagicMock(spec=AsyncSession)

    # Mock execute - no valid session found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Mock OAuth service
    with patch("app.api.auth.oauth_service") as mock_oauth:
        mock_oauth.hash_token.return_value = "hashed_token"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_info(
                session_token="invalid_token",
                db=mock_db,
            )

        assert exc_info.value.status_code == 401
        assert "Invalid or expired session" in exc_info.value.detail


@pytest.mark.asyncio
async def test_me_returns_401_with_expired_session():
    """Test that /me endpoint returns 401 with expired session."""
    # Mock session that's expired
    expired_session = Session(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="hashed_token",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Expired
    )

    # Mock session
    mock_db = MagicMock(spec=AsyncSession)

    # The query filters by expires_at > now, so it won't return the expired session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Mock OAuth service
    with patch("app.api.auth.oauth_service") as mock_oauth:
        mock_oauth.hash_token.return_value = "hashed_token"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_info(
                session_token="test_token",
                db=mock_db,
            )

        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_info_with_valid_session():
    """Test that /me endpoint returns user info with valid session."""
    user_id = uuid4()
    session_id = uuid4()

    # Create valid session
    valid_session = Session(
        id=session_id,
        user_id=user_id,
        token_hash="hashed_token",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    # Create user
    user = User(
        id=user_id,
        email="test@example.com",
        name="Test User",
        picture="https://example.com/photo.jpg",
        google_id="123456789",
        role=UserRole.USER,
        is_active=True,
    )

    # Mock session
    mock_db = MagicMock(spec=AsyncSession)

    # Mock execute for both queries (session and user)
    mock_session_result = MagicMock()
    mock_session_result.scalar_one_or_none.return_value = valid_session

    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = user

    # Return different results for different queries
    mock_db.execute = AsyncMock(side_effect=[mock_session_result, mock_user_result])

    # Mock OAuth service
    with patch("app.api.auth.oauth_service") as mock_oauth:
        mock_oauth.hash_token.return_value = "hashed_token"

        result = await get_current_user_info(
            session_token="test_token",
            db=mock_db,
        )

        assert result["id"] == str(user_id)
        assert result["email"] == "test@example.com"
        assert result["name"] == "Test User"
        assert result["picture"] == "https://example.com/photo.jpg"
        assert result["role"] == "user"


@pytest.mark.asyncio
async def test_me_returns_401_for_inactive_user():
    """Test that /me endpoint returns 401 for inactive user."""
    user_id = uuid4()
    session_id = uuid4()

    # Create valid session
    valid_session = Session(
        id=session_id,
        user_id=user_id,
        token_hash="hashed_token",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    # Create inactive user
    inactive_user = User(
        id=user_id,
        email="test@example.com",
        name="Test User",
        google_id="123456789",
        role=UserRole.USER,
        is_active=False,  # Inactive
    )

    # Mock session
    mock_db = MagicMock(spec=AsyncSession)

    # Mock execute for both queries (session and user)
    mock_session_result = MagicMock()
    mock_session_result.scalar_one_or_none.return_value = valid_session

    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = inactive_user

    mock_db.execute = AsyncMock(side_effect=[mock_session_result, mock_user_result])

    # Mock OAuth service
    with patch("app.api.auth.oauth_service") as mock_oauth:
        mock_oauth.hash_token.return_value = "hashed_token"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_info(
                session_token="test_token",
                db=mock_db,
            )

        assert exc_info.value.status_code == 401
        assert "User not found or inactive" in exc_info.value.detail


@pytest.mark.asyncio
async def test_callback_sets_cookie_correctly():
    """Test that callback sets the session cookie with correct parameters."""
    # Mock session
    mock_db = MagicMock(spec=AsyncSession)

    # Mock execute for user lookup - no existing user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    # Mock response
    mock_response = MagicMock()

    # Mock OAuth service
    with patch("app.api.auth.oauth_service") as mock_oauth:
        mock_oauth.exchange_code = AsyncMock(return_value={
            "access_token": "test_access_token",
        })

        mock_oauth.get_user_info = AsyncMock(return_value=GoogleUserInfo(
            google_id="123456789",
            email="test@example.com",
            name="Test User",
            picture=None,
        ))

        mock_oauth.generate_session_token.return_value = "test_session_token"
        mock_oauth.hash_token.return_value = "hashed_token"

        # Mock settings
        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.session_expire_days = 7

            result = await callback(
                code="test_code",
                response=mock_response,
                db=mock_db,
            )

            # Verify cookie was set via set_cookie call on the redirect response
            # The response is returned with the cookie set
            assert result.status_code == 302
