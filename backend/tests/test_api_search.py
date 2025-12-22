import pytest


def test_search_router_exists():
    from app.api.search import router
    assert router is not None


def test_query_router_exists():
    from app.api.query import router
    assert router is not None
