"""add assessment_score and assessment_submitted_at to applications_received

Revision ID: f6b2c3d4e5a6
Revises: e5a1b2c3d4e5
Create Date: 2026-04-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6b2c3d4e5a6"
down_revision: Union[str, None] = "e5a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications_received",
        sa.Column("assessment_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications_received", "assessment_submitted_at")
    op.drop_column("applications_received", "assessment_score")
