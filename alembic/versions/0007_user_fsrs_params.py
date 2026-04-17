"""Add user_fsrs_params table for per-user desired-retention calibration.

Stores the calibrated (or manually set) desired_retention value per user,
along with metadata from the last auto-calibration run.  A missing row
means "use the global default (0.90)".

Revision ID: 0007
Revises:     0006
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_fsrs_params",
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("desired_retention", sa.Float, nullable=False, server_default="0.9"),
        sa.Column("last_calibrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviews_used", sa.Integer, nullable=True),
        sa.Column("calibration_rmse", sa.Float, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_fsrs_params")
