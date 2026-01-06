# backend/tests/test_config.py
from app.core.config import settings


def test_settings_loads_defaults():
    assert settings.app_name == "HARI"
    assert settings.environment in ["development", "staging", "production", "test"]


def test_settings_database_url_required():
    assert settings.database_url is not None
