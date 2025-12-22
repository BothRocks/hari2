import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session, engine


@pytest.mark.asyncio
async def test_engine_created():
    assert engine is not None


@pytest.mark.asyncio
async def test_get_session_yields_async_session():
    async for session in get_session():
        assert isinstance(session, AsyncSession)
        break
