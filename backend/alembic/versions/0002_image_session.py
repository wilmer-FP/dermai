"""Sesión anónima de la imagen (modo demo)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("images", sa.Column("session_id", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_images_session_id"), "images", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_images_session_id"), table_name="images")
    with op.batch_alter_table("images") as batch:  # batch: SQLite no admite DROP COLUMN directo en todas las versiones
        batch.drop_column("session_id")
