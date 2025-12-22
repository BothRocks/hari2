# backend/tests/test_models_session.py
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from app.models.session import Session


def test_session_model_exists():
    """Test Session model can be instantiated."""
    session = Session(
        user_id=uuid4(),
        token_hash="abc123def456",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    assert session.user_id is not None
    assert session.token_hash == "abc123def456"


def test_session_has_required_fields():
    """Test Session has all required fields."""
    assert hasattr(Session, 'id')
    assert hasattr(Session, 'user_id')
    assert hasattr(Session, 'token_hash')
    assert hasattr(Session, 'expires_at')
    assert hasattr(Session, 'created_at')
