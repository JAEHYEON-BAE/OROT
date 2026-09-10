"""이벤트 종류가 여러 곳에 흩어져 있다 — 그 사이가 벌어지는 것을 막는다 (T-118).

같은 목록이 네 군데 있다.
  1. `EventType` enum
  2. `listing_events` 의 CHECK 제약 (모델 + 마이그레이션)
  3. 알림 라벨 (`vinyl_core.notifications`)
  4. 화면 라벨 (`routers/rss.py`, `apps/web/lib/format.ts`)

enum 에만 값을 더하면 **INSERT 가 런타임에 제약 위반으로 죽고**, 라벨만 빠뜨리면
사용자에게 `PREORDER_OPENS_SOON` 같은 원문이 그대로 보인다. 둘 다 배포 후에야 드러난다.
"""

import re
from pathlib import Path

from vinyl_core.enums import EventType
from vinyl_core.models import ListingEvent
from vinyl_core.notifications import _EVENT_LABEL, NOTIFIABLE

REPO_ROOT = Path(__file__).resolve().parents[3]


def _constraint_values() -> set[str]:
    """모델의 CHECK 제약에 적힌 이벤트 종류."""
    for arg in ListingEvent.__table_args__:
        text = str(getattr(arg, "sqltext", ""))
        if "event_type IN" in text:
            return set(re.findall(r"'([A-Z_]+)'", text))
    raise AssertionError("event_type CHECK 제약을 찾지 못했습니다")


def test_check_constraint_matches_the_enum() -> None:
    """제약에 없는 값을 넣으면 INSERT 가 죽는다 — enum 과 정확히 같아야 한다."""
    assert _constraint_values() == {e.value for e in EventType}


def test_schedule_changed_exists() -> None:
    """일정이 바뀐 사실 자체가 알림 대상이다.

    구독자는 **옛 시각을 알고 기다리고 있다.** 바뀐 것을 안 알리면
    잘못된 시각을 믿고 기다리다 예약을 통째로 놓친다.
    """
    assert EventType.SCHEDULE_CHANGED in NOTIFIABLE


def test_every_notifiable_event_has_a_label() -> None:
    """알림으로 나가는 종류에 라벨이 없으면 제목에 enum 원문이 찍힌다."""
    missing = {e.value for e in NOTIFIABLE} - set(_EVENT_LABEL)
    assert not missing, f"알림 라벨 누락: {missing}"


def test_notifiable_events_are_all_time_driven() -> None:
    """diff 기반(M3) 이벤트는 아직 알림으로 내보내지 않는다.

    수집이 붙기 전에 열어 두면 첫 크롤에서 수천 건이 한꺼번에 나간다.
    """
    time_driven = {
        EventType.SCHEDULE_ADDED,
        EventType.SCHEDULE_CHANGED,
        EventType.PREORDER_OPENS_SOON,
        EventType.PREORDER_OPEN,
        EventType.RELEASED,
    }
    assert time_driven >= NOTIFIABLE


def test_rss_labels_cover_every_notifiable_event() -> None:
    """알림에서 '일정 변동'이라 본 것이 RSS 에서 원문이면 같은 일로 읽히지 않는다."""
    source = (REPO_ROOT / "apps/api/src/vinyl_api/routers/rss.py").read_text(encoding="utf-8")
    labelled = set(re.findall(r"EventType\.([A-Z_]+)\.value:", source))
    missing = {e.name for e in NOTIFIABLE} - labelled
    assert not missing, f"RSS 라벨 누락: {missing}"


def test_web_labels_cover_every_event_type() -> None:
    """화면에도 같은 말이 있어야 한다.

    웹은 모르는 값이면 원문을 그대로 보여 주므로 깨지지는 않지만,
    사용자에게는 `SCHEDULE_CHANGED` 라는 글자가 그대로 노출된다.
    """
    source = (REPO_ROOT / "apps/web/lib/format.ts").read_text(encoding="utf-8")
    block = source.split("EVENT_LABELS: Record<string, string> = {")[1].split("};")[0]
    labelled = set(re.findall(r"([A-Z_]+):", block))
    missing = {e.value for e in EventType} - labelled
    assert not missing, f"웹 라벨 누락: {missing}"
