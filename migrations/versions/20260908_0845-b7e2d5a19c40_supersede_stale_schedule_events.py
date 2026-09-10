"""mark stale schedule events as superseded (T-119)

Revision ID: b7e2d5a19c40
Revises: a1c4e97f2b13
Create Date: 2026-09-08 08:45:00.000000

일정이 바뀌면 그 일정에서 나온 `PREORDER_OPENS_SOON`/`PREORDER_OPEN`/`RELEASED` 는
역할을 잃는다. **지우지 않고 표시한다** — 그 행은 구독자에게 보낸 기록이고
`notification_deliveries` 가 참조한다.
"""

import sqlalchemy as sa
from alembic import op

revision = "b7e2d5a19c40"
down_revision = "a1c4e97f2b13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "listing_events",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 피드와 멱등성 판정이 모두 "무효화되지 않은 것"만 훑는다.
    op.create_index(
        "ix_listing_events_live",
        "listing_events",
        ["release_id", sa.text("occurred_at DESC")],
        postgresql_where=sa.text("superseded_at IS NULL"),
    )


def downgrade() -> None:
    """**무효화 표시가 함께 사라진다.**

    컬럼을 지우므로 "이 이벤트는 역할을 잃었다"는 사실이 복구 불가능하게 없어진다.
    코드를 함께 되돌리면 옛 코드는 그 개념 자체를 모르므로 동작에 문제는 없다.
    다만 **스키마만 되돌렸다가 다시 올리면** 무효화된 이벤트가 되살아나
    피드에 옛 시각을 말하는 알림이 다시 뜬다 — 그때는 일정을 한 번 더 저장해
    `SCHEDULE_CHANGED` 경로로 다시 무효화하는 편이 안전하다.
    """
    op.drop_index("ix_listing_events_live", table_name="listing_events")
    op.drop_column("listing_events", "superseded_at")
