# backend/app/services/auth/oauth.py
import secrets
import hashlib
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import settings


class OAuthError(Exception):
    """Base OAuth error."""
    pass


class OAuthTokenExchangeError(OAuthError):
    """Failed to exchange code for token."""
    pass


class OAuthUserInfoError(OAuthError):
    """Failed to get user info."""
    pass


@dataclass
class GoogleUserInfo:
    google_id: str
    email: str
    name: str | None
    picture: str | None


class OAuthService:
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    SCOPES = ["openid", "email", "profile"]

    def __init__(self):
        """Initialize OAuth service and validate configuration."""
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID not configured")
        if not settings.google_client_secret:
            raise ValueError("GOOGLE_CLIENT_SECRET not configured")

    def get_authorization_url(self, state: str | None = None) -> str:
        """Generate Google OAuth authorization URL."""
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        return f"{self.GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for tokens."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.GOOGLE_TOKEN_URL,
                    data={
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": settings.google_redirect_uri,
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Validate required fields in response
                if "access_token" not in data:
                    raise OAuthTokenExchangeError("Missing access_token in response")

                return data
        except httpx.HTTPStatusError as e:
            raise OAuthTokenExchangeError(f"HTTP error during token exchange: {e}") from e
        except httpx.TimeoutException as e:
            raise OAuthTokenExchangeError(f"Timeout during token exchange: {e}") from e
        except httpx.RequestError as e:
            raise OAuthTokenExchangeError(f"Request error during token exchange: {e}") from e
        except KeyError as e:
            raise OAuthTokenExchangeError(f"Invalid response format: {e}") from e

    async def get_user_info(self, access_token: str) -> GoogleUserInfo:
        """Fetch user info from Google."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                data = response.json()

                # Validate required fields in response
                if "sub" not in data:
                    raise OAuthUserInfoError("Missing 'sub' (user ID) in response")
                if "email" not in data:
                    raise OAuthUserInfoError("Missing 'email' in response")

                return GoogleUserInfo(
                    google_id=data["sub"],
                    email=data["email"],
                    name=data.get("name"),
                    picture=data.get("picture"),
                )
        except httpx.HTTPStatusError as e:
            raise OAuthUserInfoError(f"HTTP error fetching user info: {e}") from e
        except httpx.TimeoutException as e:
            raise OAuthUserInfoError(f"Timeout fetching user info: {e}") from e
        except httpx.RequestError as e:
            raise OAuthUserInfoError(f"Request error fetching user info: {e}") from e
        except KeyError as e:
            raise OAuthUserInfoError(f"Invalid response format: {e}") from e

    @staticmethod
    def generate_session_token() -> str:
        """Generate a secure random session token."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a session token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
