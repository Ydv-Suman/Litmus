"""drop unique constraints on applications_received email, phone, linkedin_url

Revision ID: d4e8f0a1b2c3
Revises: c3f7b2e1d5a8
Create Date: 2026-04-18 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4e8f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c3f7b2e1d5a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONTACT_COLS = frozenset({"email", "phone", "linkedin_url"})


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    for uc in insp.get_unique_constraints("applications_received"):
        cols = frozenset(uc.get("column_names") or [])
        if cols and cols <= _CONTACT_COLS:
            op.drop_constraint(uc["name"], "applications_received", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_applications_received_email",
        "applications_received",
        ["email"],
    )
    op.create_unique_constraint(
        "uq_applications_received_phone",
        "applications_received",
        ["phone"],
    )
    op.create_unique_constraint(
        "uq_applications_received_linkedin_url",
        "applications_received",
        ["linkedin_url"],
    )
