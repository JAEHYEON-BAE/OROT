"""시각 기반 이벤트 생성 (M2, ADR-0005 §4.2).

운영자가 `preorder_opens_at` 을 직접 입력하므로 **직전 상태와 비교하는 diff 엔진이 필요 없다.**
스케줄러가 주기적으로 "지금 시점에서 나왔어야 할 이벤트가 아직 없는가"를 묻고 채워 넣는다.

이 구조가 갖는 성질이 둘 있다.

1. **멱등하다.** 이미 있는 이벤트는 다시 만들지 않으므로, 몇 번을 돌려도 결과가 같다.
   스케줄러가 재기동하거나 두 번 겹쳐 돌아도 중복 발송이 생기지 않는다 (T-113).
2. **놓친 것을 따라잡는다.** 서버가 몇 시간 꺼져 있었어도, 다시 켜면 그 사이 지났어야 할
   이벤트를 만들어 낸다. "시각에 맞춰 깨어 있어야만 동작"하는 구조가 아니다.

> 발송 누락은 추정 오류가 아니라 **버그**다 (성공 지표 99%).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, cast
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import and_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from vinyl_core.enums import EventType
from vinyl_core.models import ListingEvent, Release

log = structlog.get_logger(__name__)

# 예약 시작 몇 시간 전에 "곧 열린다"를 알릴지.
# 한정반은 오픈 직후 매진되므로 미리 알려 주는 편이 쓸모 있다.
PREORDER_SOON_LEAD: Final = timedelta(hours=24)

# 너무 오래 지난 일정까지 거슬러 올라가 알림을 쏟아내지 않는다.
# 서버가 오래 꺼져 있었을 때 몇 주 전 이벤트가 한꺼번에 나가는 것을 막는다.
MAX_BACKFILL: Final = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class GeneratedEvents:
    """한 번의 검사에서 만들어진 이벤트 수."""

    preorder_opens_soon: int = 0
    preorder_open: int = 0
    released: int = 0

    @property
    def total(self) -> int:
        return self.preorder_opens_soon + self.preorder_open + self.released


async def _existing_event_release_ids(
    session: AsyncSession, event_type: EventType, release_ids: list[int]
) -> set[int]:
    """이미 그 이벤트가 만들어진 발매 id 집합.

    **이것이 멱등성의 근거다.** `is_published` 같은 가변 상태가 아니라
    이벤트 자체의 존재로 판단한다 — 공개를 껐다 켜도 알림이 두 번 나가지 않는다.
    """
    if not release_ids:
        return set()
    rows = await session.scalars(
        select(ListingEvent.release_id).where(
            ListingEvent.event_type == event_type.value,
            ListingEvent.release_id.in_(release_ids),
            # **무효화된 이벤트는 없는 것으로 친다** (T-119). 예약 시각이 미뤄지면
            # 옛 '예약 시작'은 역할을 잃었으므로, 새 시각에 다시 나가야 한다.
            ListingEvent.superseded_at.is_(None),
        )
    )
    return {rid for rid in rows if rid is not None}


async def _emit(
    session: AsyncSession,
    event_type: EventType,
    candidates: list[Release],
    *,
    value_of: str,
    occurred_at: datetime,
) -> int:
    """후보 중 아직 이벤트가 없는 것에만 이벤트를 만든다."""
    if not candidates:
        return 0

    ids = [r.id for r in candidates]
    already = await _existing_event_release_ids(session, event_type, ids)

    created = 0
    for release in candidates:
        if release.id in already:
            continue
        moment = getattr(release, value_of)
        session.add(
            ListingEvent(
                release_id=release.id,
                event_type=event_type,
                occurred_at=occurred_at,
                new_value={
                    "title": release.title,
                    value_of: moment.isoformat() if moment is not None else None,
                },
            )
        )
        created += 1
        log.info(
            "schedule_event.created",
            event_type=event_type.value,
            release_id=release.id,
            title=release.title,
        )
    return created


async def generate_due_events(
    session: AsyncSession, *, now: datetime | None = None
) -> GeneratedEvents:
    """지금 시점에서 나왔어야 할 이벤트를 만든다.

    `now` 를 주입받는 이유는 시각을 조작해 시험하기 위해서다 (T-112).
    """
    moment = now or datetime.now(UTC)
    horizon = moment - MAX_BACKFILL

    published = Release.is_published.is_(True)

    # ── 예약 임박: 예약 시작이 24시간 안쪽으로 들어왔고 아직 시작 전 ──
    soon = list(
        await session.scalars(
            select(Release).where(
                published,
                Release.preorder_opens_at.is_not(None),
                Release.preorder_opens_at > moment,
                Release.preorder_opens_at <= moment + PREORDER_SOON_LEAD,
            )
        )
    )

    # ── 예약 시작: 시각이 지났다 ──
    opened = list(
        await session.scalars(
            select(Release).where(
                published,
                Release.preorder_opens_at.is_not(None),
                and_(Release.preorder_opens_at <= moment, Release.preorder_opens_at >= horizon),
            )
        )
    )

    # ── 발매: 발매일이 되었다. DATE 라 그 날 00:00 KST 를 기준으로 본다 ──
    released = list(
        await session.scalars(
            select(Release).where(
                published,
                Release.release_date.is_not(None),
                Release.release_date <= moment.astimezone(ZoneInfo("Asia/Seoul")).date(),
                Release.release_date >= horizon.astimezone(ZoneInfo("Asia/Seoul")).date(),
            )
        )
    )

    result = GeneratedEvents(
        preorder_opens_soon=await _emit(
            session,
            EventType.PREORDER_OPENS_SOON,
            soon,
            value_of="preorder_opens_at",
            occurred_at=moment,
        ),
        preorder_open=await _emit(
            session,
            EventType.PREORDER_OPEN,
            opened,
            value_of="preorder_opens_at",
            occurred_at=moment,
        ),
        released=await _emit(
            session, EventType.RELEASED, released, value_of="release_date", occurred_at=moment
        ),
    )
    await session.flush()

    if result.total:
        log.info(
            "schedule_events.generated",
            soon=result.preorder_opens_soon,
            opened=result.preorder_open,
            released=result.released,
        )
    return result


# 어떤 시각을 바꾸면 어떤 이벤트가 역할을 잃는가.
#
# **정확히 영향받는 것만 무효화한다.** 예약 마감만 고쳤는데 '예약 시작'까지
# 무효화하면 같은 알림이 이유 없이 두 번 나간다.
STALE_ON_CHANGE: Final[dict[str, tuple[EventType, ...]]] = {
    "preorder_opens_at": (EventType.PREORDER_OPENS_SOON, EventType.PREORDER_OPEN),
    "release_date": (EventType.RELEASED,),
    # 예약 마감 시각에 걸린 이벤트는 아직 없다. 바뀌어도 무효화할 것이 없지만,
    # `SCHEDULE_CHANGED` 자체는 나간다 — 구독자가 알아야 하는 변경이다.
    "preorder_closes_at": (),
}


async def supersede_stale_events(
    session: AsyncSession,
    release_id: int,
    changed_fields: Iterable[str],
    *,
    now: datetime | None = None,
) -> int:
    """일정이 바뀌어 역할을 잃은 이벤트에 무효 표시를 한다 (T-119).

    **지우지 않는다.** 그 행은 구독자에게 실제로 보낸 기록이고
    `notification_deliveries` 가 참조한다. 보낸 사실은 취소되지 않는다.
    표시해 두면 두 가지가 동시에 해결된다.

    1. **피드에서 사라진다** — 옛 시각을 말하는 알림이 새 시각을 말하는 알림 옆에
       남아 있으면 어느 쪽을 믿어야 할지 알 수 없다
    2. **다시 발생할 수 있다** — 멱등성 판정이 무효화된 것을 세지 않으므로,
       스케줄러가 새 시각에 맞춰 '예약 임박'과 '예약 시작'을 새로 만든다

    `SCHEDULE_ADDED` 는 무효화하지 않는다. 일정이 등록되었다는 사실은 시각이
    바뀌어도 그대로다.
    """
    stale: set[EventType] = set()
    for field in changed_fields:
        stale.update(STALE_ON_CHANGE.get(field, ()))
    if not stale:
        return 0

    moment = now or datetime.now(UTC)
    result = await session.execute(
        update(ListingEvent)
        .where(
            ListingEvent.release_id == release_id,
            ListingEvent.event_type.in_([e.value for e in stale]),
            # 이미 무효화된 것을 다시 건드리면 표시 시각이 뒤로 밀려
            # "언제 무효가 되었는가"를 알 수 없게 된다.
            ListingEvent.superseded_at.is_(None),
        )
        .values(superseded_at=moment)
    )
    # `AsyncSession.execute` 의 반환 타입은 `Result` 로 선언돼 있지만 UPDATE 는
    # 실제로 `CursorResult` 다. 영향받은 행 수를 알려면 여기서 좁혀야 한다.
    count = cast("CursorResult[Any]", result).rowcount or 0
    if count:
        log.info(
            "schedule_events.superseded",
            release_id=release_id,
            count=count,
            event_types=sorted(e.value for e in stale),
        )
    return count
