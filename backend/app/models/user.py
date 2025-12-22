# backend/app/models/user.py
import enum
from uuid import UUID, uuid4
from sqlalchemy import String, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    picture: Mapped[str | None] = mapped_column(String(512))

    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # API key for programmatic access
    api_key: Mapped[str | None] = mapped_column(String(64), unique=True)

    # Google OAuth
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True)
