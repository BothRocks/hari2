"""add_api_key_hash

Revision ID: 179414c0c04d
Revises: 601a3f1f225c
Create Date: 2025-12-29 15:06:31.753436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '179414c0c04d'
down_revision: Union[str, Sequence[str], None] = '601a3f1f225c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("api_key_hash", sa.String(64), nullable=True, unique=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "api_key_hash")
