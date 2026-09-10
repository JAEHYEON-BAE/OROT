"""일정 변동 알림과 옛 이벤트 무효화 (T-118, T-119).

운영자가 **이미 공개된** 일정의 시각을 바꾸면 구독자에게 알려야 한다.
구독자는 옛 시각을 알고 기다리고 있으므로, 안 알리면 잘못된 시각을 믿는다.

그리고 옛 시각에서 나온 '예약 임박'·'예약 시작'은 **역할을 잃는다.**
무효화해서 피드에서 감추고, 새 시각에 맞춰 다시 나가게 한다 (T-119).
"""

from datetime import UTC, date, datetime
from pathlib import Path

from vinyl_core.enums import EventType
from vinyl_core.models import Release
from vinyl_core.schedule_events import STALE_ON_CHANGE

from vinyl_api.routers.admin import SCHEDULE_FIELDS, _schedule_snapshot

OPENS = datetime(2026, 10, 1, 5, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 2, 5, 0, tzinfo=UTC)


def _release(**kwargs: object) -> Release:
    return Release(title="t", **kwargs)  # type: ignore[arg-type]


def test_snapshot_covers_exactly_the_schedule_fields() -> None:
    """제목·메모가 바뀐 것은 알림거리가 아니다.

    무엇이든 바뀌면 알린다고 하면, 오타 하나 고칠 때마다 구독자 폰이 울린다.
    """
    assert set(SCHEDULE_FIELDS) == {
        "preorder_opens_at",
        "preorder_closes_at",
        "release_date",
    }
    assert set(_schedule_snapshot(_release())) == set(SCHEDULE_FIELDS)


def test_snapshot_is_json_serialisable() -> None:
    """`old_value`/`new_value` 는 JSONB 다 — datetime 을 그대로 넣으면 저장이 실패한다."""
    snapshot = _schedule_snapshot(
        _release(preorder_opens_at=OPENS, release_date=date(2026, 12, 25))
    )
    assert snapshot["preorder_opens_at"] == OPENS.isoformat()
    assert snapshot["release_date"] == "2026-12-25"
    assert all(v is None or isinstance(v, str) for v in snapshot.values())


def test_missing_values_are_recorded_as_null_not_omitted() -> None:
    """키가 빠지면 '값이 없음'과 '필드가 없음'을 구분할 수 없다.

    `{}` != `{"release_date": None}` 이므로, 빠뜨리면 발매일을 지운 변경이
    비교에서 사라져 알림이 안 나간다.
    """
    assert _schedule_snapshot(_release()) == {f: None for f in SCHEDULE_FIELDS}


def test_change_is_detected_by_comparing_snapshots() -> None:
    """라우터의 판정과 같은 비교다."""
    before = _schedule_snapshot(_release(preorder_opens_at=OPENS))
    after = _schedule_snapshot(_release(preorder_opens_at=LATER))
    assert before != after


def test_rewriting_the_same_value_is_not_a_change() -> None:
    """저장만 다시 한 것으로 알림이 나가면 노이즈다."""
    before = _schedule_snapshot(_release(preorder_opens_at=OPENS))
    after = _schedule_snapshot(_release(preorder_opens_at=OPENS))
    assert before == after


def test_clearing_a_date_counts_as_a_change() -> None:
    """발매일을 지운 것도 구독자에게는 일정 변동이다."""
    before = _schedule_snapshot(_release(release_date=date(2026, 12, 25)))
    after = _schedule_snapshot(_release())
    assert before != after


def test_only_published_releases_emit_the_event() -> None:
    """초안 수정은 아무에게도 나가지 않았으므로 뉴스가 아니다.

    라우터의 조건을 문서로 고정한다 — `is_published and before != after`.
    """
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[3]
        / "apps/api/src/vinyl_api/routers/admin.py"
    ).read_text(encoding="utf-8")
    assert "if release.is_published and changed:" in source
    # 변경된 필드만 넘겨야 영향 없는 이벤트가 무효화되지 않는다.
    assert "changed = [f for f in SCHEDULE_FIELDS if before[f] != after[f]]" in source
    assert "supersede_stale_events(session, release.id, changed)" in source


# ─── 무효화 (T-119) ──────────────────────────────────────────────


def test_only_the_events_the_changed_field_produced_go_stale() -> None:
    """예약 마감만 고쳤는데 '예약 시작'까지 무효화하면 같은 알림이 두 번 나간다."""
    assert STALE_ON_CHANGE["preorder_opens_at"] == (
        EventType.PREORDER_OPENS_SOON,
        EventType.PREORDER_OPEN,
    )
    assert STALE_ON_CHANGE["release_date"] == (EventType.RELEASED,)
    # 예약 마감 시각에 걸린 이벤트는 아직 없다.
    assert STALE_ON_CHANGE["preorder_closes_at"] == ()


def test_every_schedule_field_has_a_rule() -> None:
    """규칙이 빠진 필드가 있으면 그 필드를 고쳐도 옛 이벤트가 살아남는다."""
    assert set(STALE_ON_CHANGE) == set(SCHEDULE_FIELDS)


def test_schedule_added_never_goes_stale() -> None:
    """일정이 등록되었다는 사실은 시각이 바뀌어도 그대로다."""
    all_stale = {e for events in STALE_ON_CHANGE.values() for e in events}
    assert EventType.SCHEDULE_ADDED not in all_stale
    assert EventType.SCHEDULE_CHANGED not in all_stale


def test_stale_events_are_all_schedule_derived() -> None:
    """크롤 diff 계열은 일정 수정과 무관하다 — 건드리면 M3 에서 기록이 지워진다."""
    all_stale = {e for events in STALE_ON_CHANGE.values() for e in events}
    assert all_stale <= {
        EventType.PREORDER_OPENS_SOON,
        EventType.PREORDER_OPEN,
        EventType.RELEASED,
    }


def test_superseding_marks_rather_than_deletes() -> None:
    """**지우면 구독자에게 무엇을 보냈는지 알 수 없게 된다.**

    이 행은 `notification_deliveries` 가 참조하는 발송 기록이다.
    보낸 사실은 취소되지 않는다 — 무효 표시만 한다.
    """
    source = (
        Path(__file__).resolve().parents[3] / "packages/core/src/vinyl_core/schedule_events.py"
    ).read_text(encoding="utf-8")
    body = source.split("async def supersede_stale_events")[1]
    assert "update(ListingEvent)" in body
    assert "superseded_at=moment" in body
    assert "delete(" not in body, "이벤트를 지우면 발송 기록이 사라진다"


def test_already_superseded_events_are_not_restamped() -> None:
    """두 번 무효화하면 '언제 무효가 되었는가'를 알 수 없게 된다."""
    source = (
        Path(__file__).resolve().parents[3] / "packages/core/src/vinyl_core/schedule_events.py"
    ).read_text(encoding="utf-8")
    body = source.split("async def supersede_stale_events")[1]
    assert "ListingEvent.superseded_at.is_(None)" in body


def test_idempotency_check_ignores_superseded_events() -> None:
    """이게 **재발송의 근거**다.

    무효화된 이벤트를 '이미 보냈다'로 세면 새 시각에 예약 시작 알림이 안 나간다 —
    이 제품이 유일하게 놓치면 안 되는 순간이다.
    """
    source = (
        Path(__file__).resolve().parents[3] / "packages/core/src/vinyl_core/schedule_events.py"
    ).read_text(encoding="utf-8")
    body = source.split("async def _existing_event_release_ids")[1].split("async def ")[0]
    assert "superseded_at.is_(None)" in body
