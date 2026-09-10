"""add SCHEDULE_CHANGED event type (T-118)

Revision ID: a1c4e97f2b13
Revises: 5344203b6f27
Create Date: 2026-09-08 08:30:00.000000

**Alembic 은 CHECK 제약의 *내용* 변경을 감지하지 못한다.** autogenerate 로는
빈 마이그레이션이 나오므로 drop + create 를 직접 쓴다. 이때 이름은 명명 규칙이
접두사를 붙이므로 **짧은 이름**(`event_type_valid`)을 넘긴다.
"""

from alembic import op

revision = "a1c4e97f2b13"
down_revision = "5344203b6f27"
branch_labels = None
depends_on = None

_WITH_CHANGED = (
    "event_type IN ("
    "'SCHEDULE_ADDED','SCHEDULE_CHANGED','PREORDER_OPENS_SOON','PREORDER_OPEN','RELEASED',"
    "'NEW_LISTING','RESTOCK','SOLD_OUT','PRICE_DROP','PRICE_RISE','DELISTED')"
)

_WITHOUT_CHANGED = (
    "event_type IN ("
    "'SCHEDULE_ADDED','PREORDER_OPENS_SOON','PREORDER_OPEN','RELEASED',"
    "'NEW_LISTING','RESTOCK','SOLD_OUT','PRICE_DROP','PRICE_RISE','DELISTED')"
)


def upgrade() -> None:
    op.drop_constraint("event_type_valid", "listing_events", type_="check")
    op.create_check_constraint("event_type_valid", "listing_events", _WITH_CHANGED)


def downgrade() -> None:
    # 이미 만들어진 SCHEDULE_CHANGED 행이 있으면 제약을 되돌릴 수 없다.
    # 이벤트는 구독자에게 전달된 기록이라 지우지 않는다 — 다운그레이드하려면
    # 운영자가 그 행들을 어떻게 할지 먼저 정해야 한다.
    op.execute(
        "DELETE FROM notification_deliveries WHERE event_id IN ("
        "SELECT id FROM listing_events WHERE event_type = 'SCHEDULE_CHANGED')"
    )
    op.execute("DELETE FROM listing_events WHERE event_type = 'SCHEDULE_CHANGED'")
    op.drop_constraint("event_type_valid", "listing_events", type_="check")
    op.create_check_constraint("event_type_valid", "listing_events", _WITHOUT_CHANGED)
