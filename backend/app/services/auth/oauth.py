# backend/app/services/auth/oauth.py
import secrets
import hashlib
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import settings


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
        async with httpx.AsyncClient() as client:
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
            return response.json()

    async def get_user_info(self, access_token: str) -> GoogleUserInfo:
        """Fetch user info from Google."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            return GoogleUserInfo(
                google_id=data["sub"],
                email=data["email"],
                name=data.get("name"),
                picture=data.get("picture"),
            )

    @staticmethod
    def generate_session_token() -> str:
        """Generate a secure random session token."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a session token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
