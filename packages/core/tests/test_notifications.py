"""알림 발송 계획과 페이로드 (T-115, ADR-0006).

DB 없이 순수 로직만 검사한다. 배송 흐름은 컨테이너에서 가짜 발송기로 검증했다.
"""

from datetime import timedelta

from vinyl_core.enums import EventType
from vinyl_core.notifications import (
    MAX_BATCH,
    MAX_NOTIFY_AGE,
    NOTIFIABLE,
    SendOutcome,
    build_payload,
)


class _Event:
    def __init__(self, event_type: str) -> None:
        self.event_type = event_type


class _Release:
    def __init__(self, **kw: object) -> None:
        self.id = 1
        self.title = "Machine Boy"
        self.format = None
        self.variant = None
        self.is_limited = False
        for k, v in kw.items():
            setattr(self, k, v)


def test_only_time_driven_events_are_notifiable() -> None:
    """크롤 diff 계열(`NEW_LISTING` 등)은 M3 에서 판단한다."""
    assert {
        EventType.SCHEDULE_ADDED,
        # 공개된 일정의 시각이 바뀐 것도 알림 대상이다 (T-118) —
        # 구독자는 옛 시각을 알고 기다리고 있다.
        EventType.SCHEDULE_CHANGED,
        EventType.PREORDER_OPENS_SOON,
        EventType.PREORDER_OPEN,
        EventType.RELEASED,
    } == NOTIFIABLE
    assert EventType.NEW_LISTING not in NOTIFIABLE


def test_notify_window_is_bounded() -> None:
    """발송기가 며칠 멈췄다고 지난 알림을 쏟아내면 안 된다."""
    assert timedelta(hours=48) == MAX_NOTIFY_AGE
    assert MAX_BATCH > 0


def test_payload_has_everything_the_browser_needs() -> None:
    payload = build_payload(
        _Event(EventType.PREORDER_OPEN.value),  # type: ignore[arg-type]
        _Release(format="2LP", is_limited=True, variant="Clear Vinyl"),  # type: ignore[arg-type]
        "실리카겔",
        "http://localhost:3000",
    )
    assert payload["title"] == "[예약 시작] 실리카겔 — Machine Boy"
    assert payload["body"] == "2LP · 한정반 · Clear Vinyl"
    assert payload["url"] == "http://localhost:3000/releases/1"
    # 같은 발매의 알림이 쌓이지 않도록 브라우저가 묶는 키.
    assert payload["tag"] == "release-1"


def test_payload_without_artist_uses_title_only() -> None:
    payload = build_payload(
        _Event(EventType.SCHEDULE_ADDED.value),  # type: ignore[arg-type]
        _Release(),  # type: ignore[arg-type]
        None,
        "http://x",
    )
    assert payload["title"] == "[새 일정] Machine Boy"


def test_payload_body_is_never_empty() -> None:
    """빈 본문은 알림이 잘린 것처럼 보인다."""
    payload = build_payload(
        _Event(EventType.RELEASED.value),  # type: ignore[arg-type]
        _Release(),  # type: ignore[arg-type]
        None,
        "http://x",
    )
    assert payload["body"]


def test_gone_is_distinct_from_failed() -> None:
    """404/410 은 재시도 대상이 아니다 — 죽은 구독을 계속 두드리면 차단당한다."""
    assert SendOutcome.GONE is not SendOutcome.FAILED
