# backend/tests/test_slack_events.py
"""Tests for Slack events deduplication."""
import pytest
import time

from app.integrations.slack.events import (
    _is_duplicate_event,
    _processed_events,
    _EVENT_CACHE_TTL,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the event cache before each test."""
    _processed_events.clear()
    yield
    _processed_events.clear()


def test_first_event_not_duplicate():
    """First time seeing an event should not be duplicate."""
    assert _is_duplicate_event("event_123") is False


def test_same_event_is_duplicate():
    """Same event_id should be detected as duplicate."""
    assert _is_duplicate_event("event_123") is False
    assert _is_duplicate_event("event_123") is True


def test_different_events_not_duplicate():
    """Different event_ids should not be duplicates."""
    assert _is_duplicate_event("event_1") is False
    assert _is_duplicate_event("event_2") is False
    assert _is_duplicate_event("event_3") is False


def test_event_cached_for_lookup():
    """Processed events should be stored in cache."""
    _is_duplicate_event("event_abc")
    assert "event_abc" in _processed_events


def test_multiple_duplicates_detected():
    """Multiple calls with same id should all be detected after first."""
    assert _is_duplicate_event("event_xyz") is False
    assert _is_duplicate_event("event_xyz") is True
    assert _is_duplicate_event("event_xyz") is True
    assert _is_duplicate_event("event_xyz") is True
