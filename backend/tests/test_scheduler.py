"""Tests for DriveSyncScheduler."""
import pytest
from app.services.jobs.scheduler import DriveSyncScheduler


def test_scheduler_exists():
    """Test DriveSyncScheduler can be instantiated."""
    scheduler = DriveSyncScheduler()
    assert scheduler is not None


def test_scheduler_has_start_method():
    """Test scheduler has start method."""
    scheduler = DriveSyncScheduler()
    assert hasattr(scheduler, 'start')
    assert callable(scheduler.start)


def test_scheduler_has_stop_method():
    """Test scheduler has stop method."""
    scheduler = DriveSyncScheduler()
    assert hasattr(scheduler, 'stop')
    assert callable(scheduler.stop)


def test_scheduler_interval_from_settings():
    """Test scheduler uses interval from settings."""
    scheduler = DriveSyncScheduler()
    from app.core.config import settings
    assert scheduler.interval_minutes == settings.drive_sync_interval_minutes
