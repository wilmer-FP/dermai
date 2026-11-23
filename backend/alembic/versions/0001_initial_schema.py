"""Esquema inicial: images, model_versions y analyses

Revision ID: 0001
Revises:
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
ANALYSIS_STATUS = sa.Enum("pending", "processing", "completed", "failed", name="analysis_status")


def upgrade() -> None:
    op.create_table(
        "images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("file_size_bytes > 0", name=op.f("ck_images_file_size_positive")),
        sa.CheckConstraint("width IS NULL OR width > 0", name=op.f("ck_images_width_positive")),
        sa.CheckConstraint("height IS NULL OR height > 0", name=op.f("ck_images_height_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_images")),
        sa.UniqueConstraint("stored_filename", name=op.f("uq_images_stored_filename")),
    )
    op.create_index(op.f("ix_images_checksum_sha256"), "images", ["checksum_sha256"])

    op.create_table(
        "model_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("architecture", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("weights_path", sa.String(length=500), nullable=True),
        sa.Column("metrics", JSON_TYPE, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_versions")),
        sa.UniqueConstraint("name", "version", name=op.f("uq_model_versions_name_version")),
    )

    op.create_table(
        "analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", ANALYSIS_STATUS, server_default="pending", nullable=False),
        sa.Column("necrotic_area_ratio", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("processed_image_filename", sa.String(length=255), nullable=True),
        sa.Column("result", JSON_TYPE, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "necrotic_area_ratio IS NULL OR (necrotic_area_ratio >= 0 AND necrotic_area_ratio <= 1)",
            name=op.f("ck_analyses_necrotic_area_ratio_range"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_analyses_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["image_id"], ["images.id"],
            name=op.f("fk_analyses_image_id_images"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"], ["model_versions.id"],
            name=op.f("fk_analyses_model_version_id_model_versions"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analyses")),
    )
    op.create_index(op.f("ix_analyses_image_id"), "analyses", ["image_id"])
    op.create_index(op.f("ix_analyses_model_version_id"), "analyses", ["model_version_id"])
    op.create_index(op.f("ix_analyses_status"), "analyses", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_analyses_status"), table_name="analyses")
    op.drop_index(op.f("ix_analyses_model_version_id"), table_name="analyses")
    op.drop_index(op.f("ix_analyses_image_id"), table_name="analyses")
    op.drop_table("analyses")
    op.drop_table("model_versions")
    op.drop_index(op.f("ix_images_checksum_sha256"), table_name="images")
    op.drop_table("images")
    ANALYSIS_STATUS.drop(op.get_bind(), checkfirst=True)
