# backend/tests/test_api_key_hashing.py
"""Tests for API key hashing functionality."""
import pytest
from app.core.security import (
    generate_api_key,
    hash_api_key,
    verify_api_key_hash,
)


class TestApiKeyHashing:
    """Test API key hashing functions."""

    def test_hash_api_key_returns_hex_string(self):
        """hash_api_key should return a 64-character hex string (SHA-256)."""
        api_key = generate_api_key()
        hashed = hash_api_key(api_key)

        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA-256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_hash_api_key_deterministic(self):
        """Same API key should produce same hash."""
        api_key = "test-api-key-12345"
        hash1 = hash_api_key(api_key)
        hash2 = hash_api_key(api_key)

        assert hash1 == hash2

    def test_hash_api_key_different_keys_produce_different_hashes(self):
        """Different API keys should produce different hashes."""
        key1 = "api-key-one"
        key2 = "api-key-two"

        hash1 = hash_api_key(key1)
        hash2 = hash_api_key(key2)

        assert hash1 != hash2

    def test_verify_api_key_hash_valid_key(self):
        """verify_api_key_hash should return True for valid key."""
        api_key = generate_api_key()
        stored_hash = hash_api_key(api_key)

        assert verify_api_key_hash(api_key, stored_hash) is True

    def test_verify_api_key_hash_invalid_key(self):
        """verify_api_key_hash should return False for invalid key."""
        api_key = generate_api_key()
        stored_hash = hash_api_key(api_key)
        wrong_key = generate_api_key()

        assert verify_api_key_hash(wrong_key, stored_hash) is False

    def test_verify_api_key_hash_tampered_hash(self):
        """verify_api_key_hash should return False for tampered hash."""
        api_key = generate_api_key()
        stored_hash = hash_api_key(api_key)
        tampered_hash = "a" * 64  # Valid length but wrong hash

        assert verify_api_key_hash(api_key, tampered_hash) is False

    def test_hash_api_key_empty_string(self):
        """hash_api_key should handle empty string."""
        hashed = hash_api_key("")
        assert len(hashed) == 64

    def test_hash_api_key_special_characters(self):
        """hash_api_key should handle special characters."""
        api_key = "key-with-special-chars!@#$%^&*()"
        hashed = hash_api_key(api_key)

        assert len(hashed) == 64
        assert verify_api_key_hash(api_key, hashed) is True

    def test_hash_api_key_unicode(self):
        """hash_api_key should handle unicode characters."""
        api_key = "key-with-unicode-\u00e9\u00e8\u00ea"
        hashed = hash_api_key(api_key)

        assert len(hashed) == 64
        assert verify_api_key_hash(api_key, hashed) is True
