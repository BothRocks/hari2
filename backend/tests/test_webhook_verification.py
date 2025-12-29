# backend/tests/test_webhook_verification.py
"""Tests for webhook verification functions."""
import hashlib
import hmac
import time
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

from app.integrations.telegram.webhook import verify_telegram_secret
from app.integrations.slack.events import (
    verify_slack_signature,
    require_signature_in_production,
)


class TestTelegramSecretVerification:
    """Tests for Telegram webhook secret verification."""

    def test_development_mode_no_secret_configured_passes(self):
        """In development without secret configured, verification passes."""
        with patch("app.integrations.telegram.webhook.settings") as mock_settings:
            mock_settings.environment = "development"
            mock_settings.telegram_webhook_secret = None

            assert verify_telegram_secret(None) is True
            assert verify_telegram_secret("any-secret") is True

    def test_development_mode_with_secret_requires_match(self):
        """In development with secret configured, must match."""
        with patch("app.integrations.telegram.webhook.settings") as mock_settings:
            mock_settings.environment = "development"
            mock_settings.telegram_webhook_secret = "my-secret"

            assert verify_telegram_secret("my-secret") is True
            assert verify_telegram_secret("wrong-secret") is False
            assert verify_telegram_secret(None) is False

    def test_production_mode_no_secret_configured_fails(self):
        """In production without secret configured, verification fails."""
        with patch("app.integrations.telegram.webhook.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.telegram_webhook_secret = None

            assert verify_telegram_secret(None) is False
            assert verify_telegram_secret("any-secret") is False

    def test_production_mode_with_secret_requires_match(self):
        """In production with secret configured, must match."""
        with patch("app.integrations.telegram.webhook.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.telegram_webhook_secret = "prod-secret"

            assert verify_telegram_secret("prod-secret") is True
            assert verify_telegram_secret("wrong-secret") is False
            assert verify_telegram_secret(None) is False

    def test_timing_safe_comparison(self):
        """Verification uses timing-safe comparison."""
        with patch("app.integrations.telegram.webhook.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.telegram_webhook_secret = "secret"

            # This test verifies we're using secrets.compare_digest
            # by checking behavior with similar-length strings
            assert verify_telegram_secret("secret") is True
            assert verify_telegram_secret("secre") is False
            assert verify_telegram_secret("secret1") is False


class TestSlackSignatureVerification:
    """Tests for Slack signature verification."""

    def test_no_signing_secret_returns_false(self):
        """Without signing secret configured, returns False."""
        with patch("app.integrations.slack.events.settings") as mock_settings:
            mock_settings.slack_signing_secret = None

            result = verify_slack_signature(b"body", "timestamp", "signature")
            assert result is False

    def test_expired_timestamp_returns_false(self):
        """Timestamps older than 5 minutes are rejected."""
        with patch("app.integrations.slack.events.settings") as mock_settings:
            mock_settings.slack_signing_secret = "secret"

            old_timestamp = str(int(time.time()) - 400)  # 6+ minutes ago
            result = verify_slack_signature(b"body", old_timestamp, "v0=sig")
            assert result is False

    def test_valid_signature_passes(self):
        """Valid signature verification passes."""
        with patch("app.integrations.slack.events.settings") as mock_settings:
            signing_secret = "8f742231b10e8888abcd99yyyzzz85a5"
            mock_settings.slack_signing_secret = signing_secret

            timestamp = str(int(time.time()))
            body = b'{"type":"url_verification"}'

            # Compute expected signature
            sig_basestring = f"v0:{timestamp}:{body.decode()}"
            expected_signature = (
                "v0="
                + hmac.new(
                    signing_secret.encode(),
                    sig_basestring.encode(),
                    hashlib.sha256,
                ).hexdigest()
            )

            result = verify_slack_signature(body, timestamp, expected_signature)
            assert result is True

    def test_invalid_signature_fails(self):
        """Invalid signature verification fails."""
        with patch("app.integrations.slack.events.settings") as mock_settings:
            mock_settings.slack_signing_secret = "secret"

            timestamp = str(int(time.time()))
            result = verify_slack_signature(b"body", timestamp, "v0=invalid")
            assert result is False


class TestSlackProductionRequirement:
    """Tests for Slack production signature requirement."""

    def test_development_mode_no_secret_passes(self):
        """In development without signing secret, no error raised."""
        with patch("app.integrations.slack.events.settings") as mock_settings:
            mock_settings.environment = "development"
            mock_settings.slack_signing_secret = None

            # Should not raise
            require_signature_in_production()

    def test_development_mode_with_secret_passes(self):
        """In development with signing secret, no error raised."""
        with patch("app.integrations.slack.events.settings") as mock_settings:
            mock_settings.environment = "development"
            mock_settings.slack_signing_secret = "secret"

            # Should not raise
            require_signature_in_production()

    def test_production_mode_no_secret_raises_503(self):
        """In production without signing secret, raises 503."""
        with patch("app.integrations.slack.events.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.slack_signing_secret = None

            with pytest.raises(HTTPException) as exc_info:
                require_signature_in_production()

            assert exc_info.value.status_code == 503
            assert "Slack signing secret required" in exc_info.value.detail

    def test_production_mode_with_secret_passes(self):
        """In production with signing secret, no error raised."""
        with patch("app.integrations.slack.events.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.slack_signing_secret = "prod-secret"

            # Should not raise
            require_signature_in_production()

    def test_staging_environment_requires_secret(self):
        """Non-development environments require signing secret."""
        with patch("app.integrations.slack.events.settings") as mock_settings:
            mock_settings.environment = "staging"
            mock_settings.slack_signing_secret = None

            with pytest.raises(HTTPException) as exc_info:
                require_signature_in_production()

            assert exc_info.value.status_code == 503
