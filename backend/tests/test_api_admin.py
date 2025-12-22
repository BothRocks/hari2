import pytest


def test_admin_router_exists():
    from app.api.admin import router
    assert router is not None
