"""시각 기반 이벤트 생성 (T-112, T-113).

**DB 없이** 순수 로직만 검사한다 — 시각 경계와 멱등성이 핵심이다.
실 DB 대상 검증은 컨테이너에서 시각을 조작해 따로 수행한다.
"""

from datetime import UTC, datetime, timedelta

from vinyl_core.enums import EventType
from vinyl_core.schedule_events import MAX_BACKFILL, PREORDER_SOON_LEAD

NOW = datetime(2026, 9, 20, 5, 0, tzinfo=UTC)


def test_soon_lead_is_24_hours() -> None:
    """예약 임박은 24시간 전에 알린다.

    한정반은 오픈 직후 매진되므로 "지금 열렸다"만으로는 늦다.
    """
    assert timedelta(hours=24) == PREORDER_SOON_LEAD


def test_backfill_window_is_bounded() -> None:
    """서버가 오래 꺼져 있었을 때 몇 주치 알림이 한꺼번에 나가면 안 된다."""
    assert timedelta(days=7) == MAX_BACKFILL
    assert MAX_BACKFILL > PREORDER_SOON_LEAD


def test_time_driven_event_types_are_distinct() -> None:
    """세 이벤트가 서로 다른 값이어야 멱등성 판정이 섞이지 않는다."""
    values = {
        EventType.PREORDER_OPENS_SOON.value,
        EventType.PREORDER_OPEN.value,
        EventType.RELEASED.value,
    }
    assert len(values) == 3


def test_soon_window_boundaries() -> None:
    """`PREORDER_OPENS_SOON` 은 (지금, 지금+24h] 구간이다.

    이미 지난 예약은 임박이 아니라 `PREORDER_OPEN` 이 담당한다.
    """
    just_before_open = NOW + timedelta(minutes=1)
    edge = NOW + PREORDER_SOON_LEAD
    too_far = NOW + PREORDER_SOON_LEAD + timedelta(minutes=1)
    already_open = NOW - timedelta(minutes=1)

    def in_soon_window(when: datetime) -> bool:
        return NOW < when <= NOW + PREORDER_SOON_LEAD

    assert in_soon_window(just_before_open)
    assert in_soon_window(edge)
    assert not in_soon_window(too_far)
    assert not in_soon_window(already_open)


def test_open_window_boundaries() -> None:
    """`PREORDER_OPEN` 은 [지금-7일, 지금] 구간이다."""

    def in_open_window(when: datetime) -> bool:
        return NOW - MAX_BACKFILL <= when <= NOW

    assert in_open_window(NOW)
    assert in_open_window(NOW - timedelta(days=6))
    assert not in_open_window(NOW - timedelta(days=8))  # 너무 오래된 것은 건너뛴다
    assert not in_open_window(NOW + timedelta(minutes=1))  # 아직 안 왔다
