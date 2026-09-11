"""iCalendar 구독 (T-107, 블루프린트 §5.2).

**이 엔드포인트가 제품의 핵심 약속을 처음으로 배송한다.**
계정도 푸시 인프라도 없이, 사용자가 캘린더 앱에 URL 하나를 등록하면
예약 시작 일정이 자기 캘린더에 뜨고 앱이 알아서 알림까지 준다.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from vinyl_core.models import Artist, Release
from vinyl_core.settings import get_settings

from vinyl_api.deps import SessionDep
from vinyl_api.icalendar import CalendarBuilder

router = APIRouter(prefix="/v1", tags=["calendar"])

CALENDAR_NAME = "Vinyl Radar — 발매·예약 일정"
CALENDAR_DESC = "국내 바이닐 신규 발매와 예약판매 일정"

# 예약 시작 30분 전에 캘린더 앱이 알려 준다.
# 한정반은 오픈 직후 매진되므로 "지금 열렸다"보다 "곧 열린다"가 쓸모 있다.
ALARM_MINUTES_BEFORE = 30

# 예약 시작은 순간이지만 캘린더에 점으로 찍히면 잘 안 보인다. 30분짜리 블록으로 만든다.
PREORDER_BLOCK_MINUTES = 30


def _uid(release_id: int, kind: str) -> str:
    """RFC 5545 §3.8.4.7 — 전역 유일해야 한다. 같은 일정은 항상 같은 UID 여야
    캘린더 앱이 '수정'으로 인식하고 중복 생성하지 않는다."""
    return f"{kind}-{release_id}@vinyl-radar"


@router.get(
    "/releases.ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}, "description": "iCalendar 구독 피드"}},
)
async def releases_ics(
    session: SessionDep,
    request: Request,
    include_release_dates: Annotated[
        bool, Query(description="발매일도 종일 일정으로 포함할지")
    ] = True,
) -> Response:
    """공개된 일정을 iCalendar 로 반환한다. 캘린더 앱에서 **구독** 하면 된다."""
    now = datetime.now(UTC)

    releases = (
        await session.scalars(
            select(Release)
            .where(
                Release.is_published.is_(True),
                # 날짜가 하나도 없는 일정은 캘린더에 찍을 자리가 없다.
                or_(Release.preorder_opens_at.is_not(None), Release.release_date.is_not(None)),
            )
            .options(selectinload(Release.links))
            .order_by(Release.preorder_opens_at.asc().nullslast(), Release.id.asc())
        )
    ).all()

    calendar = CalendarBuilder(CALENDAR_NAME, CALENDAR_DESC)
    base = get_settings().public_web_url.rstrip("/")

    for release in releases:
        artist_name = None
        if release.primary_artist_id is not None:
            artist = await session.get(Artist, release.primary_artist_id)
            artist_name = artist.name_display if artist else None

        label = f"{artist_name} — {release.title}" if artist_name else release.title
        if release.format:
            label = f"{label} ({release.format})"

        buy_url = release.links[0].url if release.links else f"{base}/releases/{release.id}"
        details = [f"{shop.shop_name}: {shop.url}" for shop in release.links]
        if release.variant:
            details.insert(0, f"바리언트: {release.variant}")
        if release.is_limited:
            details.insert(0, "한정반")
        if release.preorder_closes_at:
            details.append(f"예약 마감: {release.preorder_closes_at.isoformat()}")

        if release.preorder_opens_at is not None:
            end = release.preorder_opens_at + timedelta(minutes=PREORDER_BLOCK_MINUTES)
            calendar.add_timed_event(
                uid=_uid(release.id, "preorder"),
                start=release.preorder_opens_at,
                end=end,
                summary=f"예약 시작 · {label}",
                description="\n".join(details),
                url=buy_url,
                stamp=now,
                alarm_minutes_before=ALARM_MINUTES_BEFORE,
            )

        if include_release_dates and release.release_date is not None:
            calendar.add_all_day_event(
                uid=_uid(release.id, "release"),
                day=release.release_date,
                summary=f"발매 · {label}",
                url=buy_url,
                stamp=now,
            )

    return Response(
        content=calendar.render(),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'inline; filename="vinyl-radar.ics"',
            # 구독 클라이언트는 주기적으로 다시 가져간다. 너무 자주 오지 않게 한다.
            "Cache-Control": "public, max-age=600",
        },
    )
