"""Tests for upload size limits."""
import pytest
from fastapi import HTTPException


def test_check_upload_size_rejects_large():
    """check_upload_size should raise 413 for files over limit."""
    from app.api.documents import check_upload_size

    # 400MB = over 350MB limit
    with pytest.raises(HTTPException) as exc_info:
        check_upload_size(400 * 1024 * 1024)

    assert exc_info.value.status_code == 413
    assert "too large" in exc_info.value.detail.lower()
    assert "350MB" in exc_info.value.detail


def test_check_upload_size_accepts_small():
    """check_upload_size should accept files under limit."""
    from app.api.documents import check_upload_size

    # 10MB = well under limit
    check_upload_size(10 * 1024 * 1024)  # Should not raise


def test_check_upload_size_boundary():
    """Boundary test - exactly at limit should pass."""
    from app.api.documents import check_upload_size

    # Exactly 350MB should pass (not strictly greater)
    check_upload_size(350 * 1024 * 1024)  # Should not raise


def test_check_upload_size_one_byte_over():
    """One byte over limit should fail."""
    from app.api.documents import check_upload_size

    # 350MB + 1 byte
    with pytest.raises(HTTPException) as exc_info:
        check_upload_size(350 * 1024 * 1024 + 1)

    assert exc_info.value.status_code == 413


def test_check_upload_size_zero():
    """Zero size should pass."""
    from app.api.documents import check_upload_size

    check_upload_size(0)  # Should not raise
