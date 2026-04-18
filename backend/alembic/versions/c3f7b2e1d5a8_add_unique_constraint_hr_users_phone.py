"""add unique constraint to hr_users phone

Revision ID: c3f7b2e1d5a8
Revises: b2f6a1d9c4e7
Create Date: 2026-04-18 19:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c3f7b2e1d5a8"
down_revision: Union[str, Sequence[str], None] = "b2f6a1d9c4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_hr_users_phone", "hr_users", ["phone"])


def downgrade() -> None:
    op.drop_constraint("uq_hr_users_phone", "hr_users", type_="unique")
