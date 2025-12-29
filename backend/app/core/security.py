# backend/app/core/security.py
import hashlib
import hmac
import ipaddress
import secrets
import socket
import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

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


# SSRF Protection
# Whitelisted domains that bypass IP validation (e.g., Slack file downloads)
WHITELISTED_DOMAINS = {"files.slack.com", "api.slack.com"}


def validate_url(url: str) -> None:
    """
    Validate URL is safe to fetch. Raises ValueError if not.

    Blocks:
    - Non-http/https schemes
    - Private IP ranges (10.x, 172.16-31.x, 192.168.x)
    - Localhost and loopback addresses
    - Link-local addresses
    - Reserved addresses
    - Cloud metadata endpoints (169.254.169.254)

    Allows:
    - Whitelisted domains (files.slack.com, api.slack.com)
    """
    parsed = urlparse(url)

    # Require http/https
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")

    if not parsed.hostname:
        raise ValueError("URL must have a hostname")

    hostname = parsed.hostname.lower()

    # Check whitelist - these domains bypass IP validation
    if hostname in WHITELISTED_DOMAINS:
        return

    # Resolve hostname to IP
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}")

    # Block private/reserved ranges
    if ip.is_private:
        raise ValueError(f"Blocked: private IP range ({ip})")
    if ip.is_loopback:
        raise ValueError(f"Blocked: loopback address ({ip})")
    if ip.is_link_local:
        raise ValueError(f"Blocked: link-local address ({ip})")
    if ip.is_reserved:
        raise ValueError(f"Blocked: reserved address ({ip})")

    # Specifically block cloud metadata endpoint
    if str(ip) == "169.254.169.254":
        raise ValueError("Blocked: cloud metadata endpoint")
