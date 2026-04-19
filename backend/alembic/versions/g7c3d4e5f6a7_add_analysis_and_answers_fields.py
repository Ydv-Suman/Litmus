"""add resume_detail, github_detail, linkedin_detail, assessment_answers to applications_received

Revision ID: g7c3d4e5f6a7
Revises: f6b2c3d4e5a6
Create Date: 2026-04-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g7c3d4e5f6a7"
down_revision: Union[str, None] = "f6b2c3d4e5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("applications_received", sa.Column("assessment_answers", sa.JSON(), nullable=True))
    op.add_column("applications_received", sa.Column("resume_detail", sa.JSON(), nullable=True))
    op.add_column("applications_received", sa.Column("github_detail", sa.JSON(), nullable=True))
    op.add_column("applications_received", sa.Column("linkedin_detail", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("applications_received", "linkedin_detail")
    op.drop_column("applications_received", "github_detail")
    op.drop_column("applications_received", "resume_detail")
    op.drop_column("applications_received", "assessment_answers")
