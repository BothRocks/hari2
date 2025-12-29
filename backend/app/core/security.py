# backend/app/core/security.py
import hashlib
import hmac
import secrets
import base64
from datetime import datetime, timedelta, timezone
from jose import jwt
from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def generate_api_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")


def verify_api_key(provided_key: str, stored_key: str) -> bool:
    return secrets.compare_digest(provided_key, stored_key)


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage using SHA-256 with pepper."""
    pepper = settings.secret_key.encode()
    return hmac.new(pepper, api_key.encode(), hashlib.sha256).hexdigest()


def verify_api_key_hash(provided_key: str, stored_hash: str) -> bool:
    """Verify a provided API key against a stored hash."""
    provided_hash = hash_api_key(provided_key)
    return secrets.compare_digest(provided_hash, stored_hash)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.JWTError:
        return None
