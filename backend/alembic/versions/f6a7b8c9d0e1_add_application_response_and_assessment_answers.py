"""add application response snapshot and assessment answers

Revision ID: f6a7b8c9d0e1
Revises: e5a1b2c3d4e5
Create Date: 2026-04-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications_received",
        sa.Column("pipeline_resume_max", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("pipeline_github_points", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("pipeline_github_max", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("pipeline_linkedin_max", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("submission_response_payload", sa.JSON(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_candidate_answers", sa.JSON(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_run_result", sa.JSON(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_mcq_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_mcq_max", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_coding_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_coding_max", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_total_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_total_max", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("final_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("final_score_max", sa.Float(), nullable=True),
    )
    op.add_column(
        "applications_received",
        sa.Column("assessment_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications_received", "assessment_submitted_at")
    op.drop_column("applications_received", "final_score_max")
    op.drop_column("applications_received", "final_score")
    op.drop_column("applications_received", "assessment_total_max")
    op.drop_column("applications_received", "assessment_total_score")
    op.drop_column("applications_received", "assessment_coding_max")
    op.drop_column("applications_received", "assessment_coding_score")
    op.drop_column("applications_received", "assessment_mcq_max")
    op.drop_column("applications_received", "assessment_mcq_score")
    op.drop_column("applications_received", "assessment_run_result")
    op.drop_column("applications_received", "assessment_candidate_answers")
    op.drop_column("applications_received", "submission_response_payload")
    op.drop_column("applications_received", "pipeline_linkedin_max")
    op.drop_column("applications_received", "pipeline_github_max")
    op.drop_column("applications_received", "pipeline_github_points")
    op.drop_column("applications_received", "pipeline_resume_max")
