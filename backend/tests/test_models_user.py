# backend/tests/test_models_user.py
from app.models.user import User, UserRole


def test_user_has_required_fields():
    assert hasattr(User, "id")
    assert hasattr(User, "email")
    assert hasattr(User, "role")
    assert hasattr(User, "api_key")


def test_user_role_enum():
    assert UserRole.USER.value == "user"
    assert UserRole.ADMIN.value == "admin"
