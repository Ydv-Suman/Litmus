"""add pipeline screening and assessment fields to applications_received

Revision ID: e5a1b2c3d4e5
Revises: d4e8f0a1b2c3
Create Date: 2026-04-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "d4e8f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "applications_received",
        "linkedin_url",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.add_column(
        "applications_received",
        sa.Column("pipeline_resume_points", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("pipeline_linkedin_points", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("pipeline_total", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("pipeline_max", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("screening_passed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_token", sa.String(length=96), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_payload", sa.JSON(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_applications_received_assessment_token"),
        "applications_received",
        ["assessment_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_applications_received_assessment_token"),
        table_name="applications_received",
    )
    op.drop_column("applications_received", "assessment_sent_at")
    op.drop_column("applications_received", "assessment_payload")
    op.drop_column("applications_received", "assessment_token")
    op.drop_column("applications_received", "screening_passed")
    op.drop_column("applications_received", "pipeline_max")
    op.drop_column("applications_received", "pipeline_total")
    op.drop_column("applications_received", "pipeline_linkedin_points")
    op.drop_column("applications_received", "pipeline_resume_points")
    op.alter_column(
        "applications_received",
        "linkedin_url",
        existing_type=sa.String(length=255),
        nullable=False,
    )
