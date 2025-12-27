# backend/tests/test_integrations_user_state.py
"""Tests for user state tracking."""
import pytest
from uuid import uuid4

from app.integrations.user_state import (
    set_last_upload,
    get_last_upload,
    clear_user_state,
    clear_all_state,
)


@pytest.fixture(autouse=True)
def clean_state():
    """Clean state before and after each test."""
    clear_all_state()
    yield
    clear_all_state()


def test_set_and_get_last_upload():
    """Test setting and getting last upload."""
    job_id = uuid4()

    set_last_upload("telegram", "123", job_id, "test.pdf")

    result = get_last_upload("telegram", "123")
    assert result is not None
    assert result.job_id == job_id
    assert result.filename == "test.pdf"


def test_get_nonexistent_upload():
    """Test getting upload for user with no uploads."""
    result = get_last_upload("telegram", "999")
    assert result is None


def test_different_platforms_isolated():
    """Test that different platforms have isolated state."""
    job_id_telegram = uuid4()
    job_id_slack = uuid4()

    set_last_upload("telegram", "123", job_id_telegram, "telegram.pdf")
    set_last_upload("slack", "123", job_id_slack, "slack.pdf")

    telegram_result = get_last_upload("telegram", "123")
    slack_result = get_last_upload("slack", "123")

    assert telegram_result is not None
    assert slack_result is not None
    assert telegram_result.job_id == job_id_telegram
    assert slack_result.job_id == job_id_slack


def test_overwrites_previous_upload():
    """Test that new upload overwrites previous."""
    job_id_1 = uuid4()
    job_id_2 = uuid4()

    set_last_upload("telegram", "123", job_id_1, "first.pdf")
    set_last_upload("telegram", "123", job_id_2, "second.pdf")

    result = get_last_upload("telegram", "123")
    assert result is not None
    assert result.job_id == job_id_2
    assert result.filename == "second.pdf"


def test_clear_user_state():
    """Test clearing state for a specific user."""
    job_id = uuid4()

    set_last_upload("telegram", "123", job_id, "test.pdf")
    clear_user_state("telegram", "123")

    result = get_last_upload("telegram", "123")
    assert result is None


def test_clear_all_state():
    """Test clearing all state."""
    set_last_upload("telegram", "123", uuid4(), "test1.pdf")
    set_last_upload("slack", "456", uuid4(), "test2.pdf")

    clear_all_state()

    assert get_last_upload("telegram", "123") is None
    assert get_last_upload("slack", "456") is None
