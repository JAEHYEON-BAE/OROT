"""RSS 구독 (T-108, 블루프린트 §5.2).

iCalendar 와 함께 **인증 없이 핵심 가치를 배송하는 두 번째 경로**다.

> 피드에는 **이미 일어난 일(이벤트)만** 싣는다. RSS 리더는 `pubDate` 기준 최신순으로
> 정렬하고 `guid` 로 읽음 표시를 하므로, 미래 시각을 가진 "다가오는 일정"을 섞으면
> 읽지 않은 글이 목록 위에 계속 떠 있게 된다. 다가오는 일정은 `/v1/feed` 와 `.ics` 의 몫이다.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from vinyl_core.enums import EventType
from vinyl_core.models import Artist
from vinyl_core.settings import get_settings

from vinyl_api.deps import SessionDep
from vinyl_api.feed_query import latest_event_per_release
from vinyl_api.rss import RssBuilder

router = APIRouter(prefix="/v1", tags=["rss"])

FEED_TITLE = "Vinyl Radar — 신규 발매·예약 일정"
FEED_DESCRIPTION = "국내 바이닐 신규 발매와 예약판매 소식"
MAX_ITEMS = 50

# 이벤트 종류를 사람이 읽는 말로.
# 컬럼이 TEXT 라 ORM 이 문자열로 돌려준다 — 키를 문자열로 둔다.
_EVENT_LABEL: dict[str, str] = {
    EventType.SCHEDULE_ADDED.value: "일정 등록",
    EventType.SCHEDULE_CHANGED.value: "일정 변동",
    EventType.PREORDER_OPENS_SOON.value: "예약 임박",
    EventType.PREORDER_OPEN.value: "예약 시작",
    EventType.RELEASED.value: "발매",
    EventType.NEW_LISTING.value: "신규 등록",
    EventType.RESTOCK.value: "재입고",
}


@router.get(
    "/feed.rss",
    response_class=Response,
    responses={200: {"content": {"application/rss+xml": {}}, "description": "RSS 2.0 피드"}},
)
async def feed_rss(session: SessionDep, request: Request) -> Response:
    """공개된 일정의 이벤트를 RSS 2.0 으로 반환한다."""
    now = datetime.now(UTC)
    base = get_settings().public_web_url.rstrip("/")

    # `/v1/feed` 와 **같은 규칙**으로 고른다 (T-118) — 발매당 최신 이벤트 하나.
    # 두 피드가 다른 것을 보여 주면 어느 쪽이 맞는지 알 수 없다.
    rows = (await session.execute(latest_event_per_release(MAX_ITEMS))).all()

    feed = RssBuilder(
        title=FEED_TITLE,
        link=base,
        description=FEED_DESCRIPTION,
        self_url=f"{base}/v1/feed.rss",
        build_time=now,
    )

    for event, release in rows:
        artist_name = None
        if release.primary_artist_id is not None:
            artist = await session.get(Artist, release.primary_artist_id)
            artist_name = artist.name_display if artist else None

        label = f"{artist_name} — {release.title}" if artist_name else release.title
        action = _EVENT_LABEL.get(str(event.event_type), str(event.event_type))

        details: list[str] = []
        if release.format:
            details.append(f"포맷: {release.format}")
        if release.variant:
            details.append(f"바리언트: {release.variant}")
        if release.is_limited:
            details.append("한정반")
        if release.preorder_opens_at:
            details.append(f"예약 시작: {release.preorder_opens_at.isoformat()}")
        if release.preorder_closes_at:
            details.append(f"예약 마감: {release.preorder_closes_at.isoformat()}")
        if release.release_date:
            details.append(f"발매일: {release.release_date.isoformat()}")
        details += [f"{link.shop_name}: {link.url}" for link in release.links]

        categories = [action]
        if release.is_limited:
            categories.append("한정반")

        feed.add_item(
            title=f"[{action}] {label}",
            link=release.links[0].url if release.links else f"{base}/releases/{release.id}",
            guid=f"event-{event.id}@vinyl-radar",
            published_at=event.occurred_at,
            description=" · ".join(details),
            categories=categories,
        )

    return Response(
        content=feed.render(),
        media_type="application/rss+xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )
