"""피드에 실을 이벤트를 고르는 질의 (T-118, T-119).

**한 발매당 가장 최근 이벤트 하나만 싣는다.**

같은 앨범에 `SCHEDULE_ADDED → PREORDER_OPENS_SOON → PREORDER_OPEN` 이 차례로
쌓이면, 피드 맨 위 세 줄이 전부 같은 앨범이 된다. 그중 사용자에게 쓸모 있는 것은
**마지막 하나**뿐이다 — 앞의 둘은 이미 지나간 상태를 말하고 있다.
일정이 수정된 경우(`SCHEDULE_CHANGED`)는 더 분명하다. 옛 시각을 말하는 알림이
새 시각을 말하는 알림 위에 남아 있으면 **어느 쪽을 믿어야 할지 알 수 없다.**

이 규칙은 기기 알림과도 맞물린다. 푸시는 `tag=release-<id>` 로 같은 발매의 알림을
하나로 묶으므로, 폰에는 이미 마지막 하나만 남아 있다. 피드가 셋을 보여 주면
**같은 제품이 두 곳에서 다르게 말하는 셈**이다.

일정이 바뀌어 **무효화된**(`superseded_at`) 이벤트도 뺀다 (T-119).

`/v1/feed` 와 `/v1/feed.rss` 가 같은 함수를 쓴다. 각자 질의를 쓰면 한쪽만
고쳐지고 다른 쪽이 조용히 어긋난다.
"""

from orot_core.models import ListingEvent, Release
from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload


def latest_event_per_release(limit: int) -> Select[tuple[ListingEvent, Release]]:
    """공개된 발매마다 가장 최근 이벤트 하나씩, 최신순으로.

    Postgres 의 `DISTINCT ON` 을 쓴다. `ORDER BY` 의 앞부분이 `DISTINCT ON` 의
    식과 같아야 한다는 제약이 있어서, **발매별로 고른 뒤 다시 시간순으로 정렬**하는
    두 단계가 된다.

    동시각 이벤트는 `id` 로 가른다 — 공개와 동시에 예약이 시작되면
    `SCHEDULE_ADDED` 와 `PREORDER_OPEN` 의 `occurred_at` 이 같을 수 있고,
    그때 나중에 만들어진 쪽(더 큰 id)이 더 최신 상태다.
    """
    newest = (
        select(ListingEvent.id)
        .join(Release, ListingEvent.release_id == Release.id)
        .where(
            Release.is_published.is_(True),
            # 일정이 바뀌어 역할을 잃은 이벤트는 감춘다 (T-119).
            # 옛 시각을 말하는 알림이 새 시각을 말하는 알림 옆에 남아 있으면
            # 어느 쪽을 믿어야 할지 알 수 없다.
            ListingEvent.superseded_at.is_(None),
        )
        .distinct(ListingEvent.release_id)
        .order_by(
            ListingEvent.release_id,
            ListingEvent.occurred_at.desc(),
            ListingEvent.id.desc(),
        )
        .subquery()
    )

    return (
        select(ListingEvent, Release)
        .join(Release, ListingEvent.release_id == Release.id)
        .where(ListingEvent.id.in_(select(newest.c.id)))
        .options(selectinload(Release.links))
        .order_by(ListingEvent.occurred_at.desc(), ListingEvent.id.desc())
        .limit(limit)
    )
