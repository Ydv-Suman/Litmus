"""add hr users and job owner relation

Revision ID: b2f6a1d9c4e7
Revises: 92e5c7a2baff
Create Date: 2026-04-18 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2f6a1d9c4e7"
down_revision: Union[str, Sequence[str], None] = "92e5c7a2baff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hr_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=512), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_hr_users_email"), "hr_users", ["email"], unique=False)
    op.create_index(op.f("ix_hr_users_id"), "hr_users", ["id"], unique=False)

    op.add_column("job_listings", sa.Column("hr_user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_job_listings_hr_user_id"), "job_listings", ["hr_user_id"], unique=False)
    op.create_foreign_key(
        "fk_job_listings_hr_user_id_hr_users",
        "job_listings",
        "hr_users",
        ["hr_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_job_listings_hr_user_id_hr_users", "job_listings", type_="foreignkey")
    op.drop_index(op.f("ix_job_listings_hr_user_id"), table_name="job_listings")
    op.drop_column("job_listings", "hr_user_id")

    op.drop_index(op.f("ix_hr_users_id"), table_name="hr_users")
    op.drop_index(op.f("ix_hr_users_email"), table_name="hr_users")
    op.drop_table("hr_users")
