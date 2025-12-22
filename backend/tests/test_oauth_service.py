# backend/tests/test_oauth_service.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.auth.oauth import OAuthService, GoogleUserInfo


def test_oauth_service_exists():
    """Test OAuthService can be instantiated."""
    service = OAuthService()
    assert service is not None


def test_get_authorization_url():
    """Test generating Google OAuth authorization URL."""
    service = OAuthService()
    url = service.get_authorization_url()
    assert "accounts.google.com" in url
    assert "client_id" in url
    assert "redirect_uri" in url
    assert "scope" in url


@pytest.mark.asyncio
async def test_exchange_code_for_tokens():
    """Test exchanging auth code for tokens."""
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
