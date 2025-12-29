"""Tests for startup security validation."""
import pytest
from unittest.mock import MagicMock

from app.main import validate_production_secrets


def _create_mock_settings(
    environment: str = "development",
    secret_key: str = "dev-secret-key-change-in-production",
    admin_api_key: str = "dev-admin-key",
) -> MagicMock:
    """Create a mock settings object for testing."""
    mock = MagicMock()
    mock.environment = environment
    mock.secret_key = secret_key
    mock.admin_api_key = admin_api_key
    return mock


def test_production_rejects_default_secret_key():
    """Production should reject default secret_key."""
    mock_settings = _create_mock_settings(
        environment="production",
        secret_key="dev-secret-key-change-in-production",
        admin_api_key="real-admin-key-abc123",
    )

    with pytest.raises(RuntimeError, match="SECRET_KEY must be set in production"):
        validate_production_secrets(mock_settings)


def test_production_rejects_default_admin_key():
    """Production should reject default admin_api_key."""
    mock_settings = _create_mock_settings(
        environment="production",
        secret_key="real-secret-key-abc123",
        admin_api_key="dev-admin-key",
    )

    with pytest.raises(RuntimeError, match="ADMIN_API_KEY must be set in production"):
        validate_production_secrets(mock_settings)


def test_development_allows_default_secrets():
    """Development should allow default secrets."""
    mock_settings = _create_mock_settings(
        environment="development",
        secret_key="dev-secret-key-change-in-production",
        admin_api_key="dev-admin-key",
    )

    # Should not raise
    validate_production_secrets(mock_settings)


def test_production_with_real_secrets_succeeds():
    """Production with real secrets should succeed."""
    mock_settings = _create_mock_settings(
        environment="production",
        secret_key="real-secret-key-abc123",
        admin_api_key="real-admin-key-xyz789",
    )

    # Should not raise
    validate_production_secrets(mock_settings)


def test_staging_rejects_default_secrets():
    """Non-development environments should reject default secrets."""
    mock_settings = _create_mock_settings(
        environment="staging",
        secret_key="dev-secret-key-change-in-production",
        admin_api_key="dev-admin-key",
    )

    with pytest.raises(RuntimeError, match="SECRET_KEY must be set in production"):
        validate_production_secrets(mock_settings)


def test_error_message_includes_generation_command():
    """Error messages should include helpful generation commands."""
    mock_settings = _create_mock_settings(
        environment="production",
        secret_key="dev-secret-key-change-in-production",
        admin_api_key="real-admin-key",
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_secrets(mock_settings)

    assert "secrets.token_urlsafe" in str(exc_info.value)
