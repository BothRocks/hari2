# backend/tests/test_security.py
import pytest
from app.core.security import generate_api_key, verify_api_key, create_access_token


def test_generate_api_key_returns_string():
    key = generate_api_key()
    assert isinstance(key, str)
    assert len(key) == 43  # base64 of 32 bytes


def test_generate_api_key_unique():
    key1 = generate_api_key()
    key2 = generate_api_key()
    assert key1 != key2


def test_create_access_token_returns_string():
    token = create_access_token(data={"sub": "test@example.com"})
    assert isinstance(token, str)
