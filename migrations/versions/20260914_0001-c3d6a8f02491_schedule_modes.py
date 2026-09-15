"""Persist explicit schedule modes without changing existing dates.

Revision ID: c3d6a8f02491
Revises: b7e2d5a19c40
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d6a8f02491"
down_revision = "b7e2d5a19c40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "releases",
        sa.Column(
            "schedule_status", sa.Text(), nullable=False, server_default="SCHEDULED"
        ),
    )
    op.add_column(
        "releases",
        sa.Column(
            "until_sold_out", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_check_constraint(
        "schedule_status_valid",
        "releases",
        "schedule_status IN ('SCHEDULED','TBA','ON_SALE')",
    )
    op.create_check_constraint(
        "tba_dates_empty",
        "releases",
        "schedule_status != 'TBA' OR (preorder_opens_at IS NULL AND preorder_closes_at IS NULL AND release_date IS NULL AND NOT until_sold_out)",
    )
    op.create_check_constraint(
        "on_sale_start_empty",
        "releases",
        "schedule_status != 'ON_SALE' OR preorder_opens_at IS NULL",
    )
    op.create_check_constraint(
        "until_sold_out_end_empty",
        "releases",
        "NOT until_sold_out OR preorder_closes_at IS NULL",
    )


def downgrade() -> None:
    for name in (
        "until_sold_out_end_empty",
        "on_sale_start_empty",
        "tba_dates_empty",
        "schedule_status_valid",
    ):
        op.drop_constraint(name, "releases", type_="check")
    op.drop_column("releases", "until_sold_out")
    op.drop_column("releases", "schedule_status")
