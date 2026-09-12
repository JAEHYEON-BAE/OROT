"""공개 음반당 한 줄인 피드. 최근 변경순 또는 시작 일정 임박순으로 정렬한다."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response, status
from orot_core.enums import EventType
from orot_core.models import Release
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, case, cast, func, select
from sqlalchemy.orm import selectinload

from orot_api.caching import set_cache_headers
from orot_api.deps import SessionDep
from orot_api.feed_query import latest_event_per_release
from orot_api.schemas.release import ReleaseOut
from orot_api.serializers import release_to_out

router = APIRouter(prefix="/v1", tags=["feed"])

DEFAULT_FEED_LIMIT = 50
MAX_FEED_LIMIT = 100


class FeedKind(StrEnum):
    """피드 항목의 종류."""

    UPCOMING = "UPCOMING"  # 아직 오지 않은 일정
    EVENT = "EVENT"  # 이미 일어난 일


class FeedItem(BaseModel):
    """피드 한 줄."""

    kind: FeedKind
    at: datetime = Field(description="UPCOMING 이면 예약 시작 시각, EVENT 면 발생 시각")
    event_type: EventType | None = None
    release: ReleaseOut


class FeedPage(BaseModel):
    items: list[FeedItem]
    generated_at: datetime


def release_feed_query(sort: str, now: datetime, limit: int):
    """날짜만 있는 발매일은 한국 시간 자정으로 정렬한다."""
    start = func.coalesce(
        Release.preorder_opens_at,
        func.timezone("Asia/Seoul", cast(Release.release_date, DateTime)),
    )
    query = (
        select(Release).where(Release.is_published.is_(True)).options(selectinload(Release.links))
    )
    if sort == "recent":
        # **등록이 아니라 마지막 손댄 시각** 기준이다. 일정을 고치면 그것이 소식이므로
        # 위로 올라와야 한다 — 등록 시각으로 줄세우면 방금 바꾼 일정이 아래에 묻힌다.
        # `updated_at` 은 모델의 `onupdate=func.now()` 가 갱신한다.
        query = query.order_by(Release.updated_at.desc(), Release.id.desc())
    else:
        # Future first, most recently started next, unknown dates last.
        query = query.order_by(
            case((start >= now, 0), (start.is_not(None), 1), else_=2),
            case((start >= now, start)).asc(),
            case((start < now, start)).desc(),
            Release.created_at.desc(),
            Release.id.desc(),
        )
    return query.limit(limit)


@router.get("/feed", response_model=FeedPage)
async def get_feed(
    session: SessionDep,
    request: Request,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=MAX_FEED_LIMIT)] = DEFAULT_FEED_LIMIT,
    sort: Literal["recent", "imminent"] = "imminent",
) -> Response:
    """중복 제거와 정렬을 LIMIT 전에 적용한다."""
    now = datetime.now(UTC)
    rows = (await session.scalars(release_feed_query(sort, now, limit))).all()
    ids = [row.id for row in rows]
    event_rows = (
        (await session.execute(latest_event_per_release(limit).where(Release.id.in_(ids)))).all()
        if ids
        else []
    )
    events = {release.id: event for event, release in event_rows}
    items = []
    for row in rows:
        event = events.get(row.id)
        upcoming = row.preorder_opens_at is not None and row.preorder_opens_at > now
        items.append(
            FeedItem(
                kind=FeedKind.UPCOMING if upcoming else FeedKind.EVENT,
                at=row.preorder_opens_at
                if upcoming
                else (event.occurred_at if event else row.created_at),
                event_type=None if upcoming or event is None else event.event_type,
                release=await release_to_out(session, row),
            )
        )

    page = FeedPage(items=items, generated_at=now)
    payload = Response(content=page.model_dump_json(), media_type="application/json")
    # generated_at 이 매번 바뀌므로 ETag 는 항목 부분만으로 계산한다.
    set_cache_headers(payload, page.items)

    if request.headers.get("If-None-Match") == payload.headers.get("ETag"):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=dict(payload.headers))
    return payload
