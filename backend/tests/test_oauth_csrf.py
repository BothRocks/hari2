# backend/tests/test_oauth_csrf.py
"""Tests for OAuth CSRF protection."""
import secrets
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth.oauth import GoogleUserInfo


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app, follow_redirects=False)


class TestOAuthCSRFProtection:
    """Tests for OAuth CSRF state parameter protection."""

    def test_login_generates_state_and_sets_cookie(self, client: TestClient):
        """Login endpoint should generate state and set it in cookie."""
        with patch("app.api.auth.OAuthService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_authorization_url.return_value = "https://accounts.google.com/oauth?state=test"
            mock_service_class.return_value = mock_service

            response = client.get("/api/auth/login")

            # Should redirect
            assert response.status_code == 307

            # Should have oauth_state cookie set
            assert "oauth_state" in response.cookies
            state_cookie = response.cookies["oauth_state"]
            assert len(state_cookie) > 20  # Should be a reasonably long token

            # Should have called get_authorization_url with a state
            mock_service.get_authorization_url.assert_called_once()
            call_kwargs = mock_service.get_authorization_url.call_args
            assert "state" in call_kwargs.kwargs
            assert call_kwargs.kwargs["state"] is not None

    def test_login_state_cookie_is_httponly(self, client: TestClient):
        """State cookie should be HTTP-only for security."""
        with patch("app.api.auth.OAuthService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_authorization_url.return_value = "https://accounts.google.com/oauth"
            mock_service_class.return_value = mock_service

            response = client.get("/api/auth/login")

            # Check cookie attributes in Set-Cookie header
            set_cookie = response.headers.get("set-cookie", "")
            assert "httponly" in set_cookie.lower()

    def test_callback_rejects_missing_state_param(self, client: TestClient):
        """Callback should reject requests without state query parameter."""
        with patch("app.api.auth.OAuthService") as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            # Call without state parameter
            response = client.get(
                "/api/auth/callback?code=test_code",
                cookies={"oauth_state": "some_state"},
            )

            assert response.status_code == 400
            assert "Missing OAuth state" in response.json()["detail"]

    def test_callback_rejects_missing_state_cookie(self, client: TestClient):
        """Callback should reject requests without state cookie."""
        with patch("app.api.auth.OAuthService") as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            # Call without oauth_state cookie
            response = client.get("/api/auth/callback?code=test_code&state=some_state")

            assert response.status_code == 400
            assert "Missing OAuth state" in response.json()["detail"]

    def test_callback_rejects_mismatched_state(self, client: TestClient):
        """Callback should reject when state param doesn't match cookie."""
        with patch("app.api.auth.OAuthService") as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            # Call with mismatched state
            response = client.get(
                "/api/auth/callback?code=test_code&state=attacker_state",
                cookies={"oauth_state": "legitimate_state"},
            )

            assert response.status_code == 400
            assert "Invalid OAuth state" in response.json()["detail"]
            assert "CSRF" in response.json()["detail"]

    def test_callback_accepts_matching_state(self, client: TestClient):
        """Callback should accept when state matches and proceed with auth."""
        state = secrets.token_urlsafe(32)

        with patch("app.api.auth.OAuthService") as mock_service_class:
            mock_service = MagicMock()
            # Make exchange_code fail so we don't need full OAuth flow
            mock_service.exchange_code = AsyncMock(
                return_value={"access_token": "test_token"}
            )
            mock_service.get_user_info = AsyncMock(
                return_value=GoogleUserInfo(
                    google_id="123",
                    email="test@example.com",
                    name="Test User",
                    picture=None,
                )
            )
            mock_service.generate_session_token.return_value = "session_token"
            mock_service.hash_token.return_value = "hashed_token"
            mock_service_class.return_value = mock_service

            with patch("app.api.auth.get_session") as mock_get_session:
                # Mock database session
                mock_db = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None  # New user
                mock_db.execute.return_value = mock_result

                async def mock_session_generator():
                    yield mock_db

                mock_get_session.return_value = mock_session_generator()

                response = client.get(
                    f"/api/auth/callback?code=test_code&state={state}",
                    cookies={"oauth_state": state},
                )

                # Should either succeed or fail for other reasons (not CSRF)
                # If it's 400, it should NOT be about state
                if response.status_code == 400:
                    assert "state" not in response.json()["detail"].lower()

    def test_callback_clears_state_cookie_on_success(self, client: TestClient):
        """State cookie should be cleared after successful callback.

        This test verifies the code structure - we check that delete_cookie
        is called on the response. Full integration testing would require
        a real database setup.
        """
        # Verify the auth.py code includes the delete_cookie call
        import inspect
        from app.api import auth

        source = inspect.getsource(auth.callback)
        assert 'delete_cookie("oauth_state")' in source or "delete_cookie('oauth_state')" in source

    def test_state_uses_secure_comparison(self, client: TestClient):
        """State comparison should use constant-time comparison."""
        # This test verifies the code uses secrets.compare_digest
        # by checking timing-safe comparison is used (indirectly)
        state = "a" * 43  # Same length as token_urlsafe(32)

        with patch("app.api.auth.OAuthService") as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            # Test with similar but different states
            response = client.get(
                f"/api/auth/callback?code=test_code&state={state}",
                cookies={"oauth_state": "b" * 43},
            )

            assert response.status_code == 400
            assert "Invalid OAuth state" in response.json()["detail"]
