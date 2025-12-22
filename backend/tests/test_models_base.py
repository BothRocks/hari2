import pytest
from uuid import UUID
from datetime import datetime
from app.models.base import Base, TimestampMixin


def test_base_has_metadata():
    assert Base.metadata is not None


def test_timestamp_mixin_has_fields():
    assert hasattr(TimestampMixin, "created_at")
    assert hasattr(TimestampMixin, "updated_at")
