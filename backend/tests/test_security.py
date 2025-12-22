# backend/tests/test_security.py
from app.core.security import generate_api_key, verify_api_key, create_access_token, decode_access_token


def test_generate_api_key_returns_string():
    key = generate_api_key()
    assert isinstance(key, str)
    assert len(key) == 43  # base64 of 32 bytes


def test_generate_api_key_unique():
    key1 = generate_api_key()
    key2 = generate_api_key()
    assert key1 != key2


def test_verify_api_key_returns_true_for_matching_keys():
    key = "test_api_key_12345"
    assert verify_api_key(key, key) is True


def test_verify_api_key_returns_false_for_non_matching_keys():
    key1 = "test_api_key_12345"
    key2 = "different_api_key_67890"
    assert verify_api_key(key1, key2) is False


def test_create_access_token_returns_string():
    token = create_access_token(data={"sub": "test@example.com"})
    assert isinstance(token, str)


def test_decode_access_token_returns_data_for_valid_token():
    data = {"sub": "test@example.com", "user_id": 123}
    token = create_access_token(data=data)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "test@example.com"
    assert decoded["user_id"] == 123
    assert "exp" in decoded


def test_decode_access_token_returns_none_for_invalid_token():
    invalid_token = "invalid.token.string"
    decoded = decode_access_token(invalid_token)
    assert decoded is None
