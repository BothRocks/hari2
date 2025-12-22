# backend/tests/test_oauth_service.py
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.auth.oauth import (
    OAuthService,
    OAuthTokenExchangeError,
    OAuthUserInfoError,
)


def test_oauth_service_exists():
    """Test OAuthService can be instantiated."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()
        assert service is not None


def test_get_authorization_url():
    """Test generating Google OAuth authorization URL."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()
        url = service.get_authorization_url()
        assert "accounts.google.com" in url
        assert "client_id" in url
        assert "redirect_uri" in url
        assert "scope" in url


@pytest.mark.asyncio
async def test_exchange_code_for_tokens():
    """Test exchanging auth code for tokens."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "id_token": "test_id_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            tokens = await service.exchange_code("test_code")
            assert tokens["access_token"] == "test_access_token"


@pytest.mark.asyncio
async def test_get_user_info():
    """Test fetching user info from Google."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sub": "123456789",
            "email": "test@example.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            user_info = await service.get_user_info("test_access_token")
            assert user_info.email == "test@example.com"
            assert user_info.google_id == "123456789"


def test_configuration_validation_missing_client_id():
    """Test that missing client ID raises ValueError."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = None
        mock_settings.google_client_secret = "test_client_secret"
        with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID not configured"):
            OAuthService()


def test_configuration_validation_missing_client_secret():
    """Test that missing client secret raises ValueError."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = None
        with pytest.raises(ValueError, match="GOOGLE_CLIENT_SECRET not configured"):
            OAuthService()


def test_generate_session_token_uniqueness():
    """Test that generate_session_token creates unique tokens."""
    tokens = set()
    for _ in range(100):
        token = OAuthService.generate_session_token()
        assert token not in tokens, "Token collision detected"
        tokens.add(token)
        assert len(token) > 0, "Token should not be empty"


def test_hash_token_consistency():
    """Test that hash_token produces consistent hashes."""
    token = "test_token_123"
    hash1 = OAuthService.hash_token(token)
    hash2 = OAuthService.hash_token(token)
    assert hash1 == hash2, "Hash should be consistent"


def test_hash_token_output_format():
    """Test that hash_token produces 64-character hex string."""
    token = "test_token_123"
    hashed = OAuthService.hash_token(token)
    assert len(hashed) == 64, "SHA-256 hash should be 64 characters"
    assert all(c in "0123456789abcdef" for c in hashed), "Hash should be hex"


@pytest.mark.asyncio
async def test_exchange_code_http_error():
    """Test that exchange_code handles HTTP errors."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(OAuthTokenExchangeError, match="HTTP error"):
                await service.exchange_code("test_code")


@pytest.mark.asyncio
async def test_exchange_code_timeout_error():
    """Test that exchange_code handles timeout errors."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timeout")
            with pytest.raises(OAuthTokenExchangeError, match="Timeout"):
                await service.exchange_code("test_code")


@pytest.mark.asyncio
async def test_exchange_code_missing_access_token():
    """Test that exchange_code validates response contains access_token."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id_token": "test_id_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(OAuthTokenExchangeError, match="Missing access_token"):
                await service.exchange_code("test_code")


@pytest.mark.asyncio
async def test_get_user_info_http_error():
    """Test that get_user_info handles HTTP errors."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            with pytest.raises(OAuthUserInfoError, match="HTTP error"):
                await service.get_user_info("test_access_token")


@pytest.mark.asyncio
async def test_get_user_info_timeout_error():
    """Test that get_user_info handles timeout errors."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")
            with pytest.raises(OAuthUserInfoError, match="Timeout"):
                await service.get_user_info("test_access_token")


@pytest.mark.asyncio
async def test_get_user_info_missing_sub():
    """Test that get_user_info validates response contains 'sub'."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "email": "test@example.com",
            "name": "Test User",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            with pytest.raises(OAuthUserInfoError, match="Missing 'sub'"):
                await service.get_user_info("test_access_token")


@pytest.mark.asyncio
async def test_get_user_info_missing_email():
    """Test that get_user_info validates response contains 'email'."""
    with patch("app.services.auth.oauth.settings") as mock_settings:
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_client_secret"
        service = OAuthService()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sub": "123456789",
            "name": "Test User",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            with pytest.raises(OAuthUserInfoError, match="Missing 'email'"):
                await service.get_user_info("test_access_token")
