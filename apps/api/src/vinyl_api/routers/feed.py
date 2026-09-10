"""통합 피드 (T-106, 블루프린트 §5.2).

"놓치지 않게" 가 제품의 약속이므로 피드의 첫 화면은 **곧 일어날 일**이어야 한다.
그래서 한 배열 안에 두 종류를 섞되 순서를 이렇게 둔다.

1. `UPCOMING` — 아직 예약이 시작되지 않은 일정. **임박한 순**
2. `EVENT`    — 이미 일어난 일 (`SCHEDULE_ADDED` 등). **최신순**

지금은 `SCHEDULE_ADDED` 밖에 없어 아래쪽이 얇지만,
M2 에서 시각 기반 알림(`PREORDER_OPEN` 등)이 붙으면 그대로 채워진다.

> 커서 페이지네이션을 쓰지 않는다. 피드는 앞부분만 보는 화면이고,
> 종류가 섞인 목록에 keyset 커서를 얹으면 복잡도만 늘고 얻는 것이 없다.
> 깊이 훑어야 할 때는 `/v1/releases` 를 쓴다.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from vinyl_core.enums import EventType
from vinyl_core.models import Release

from vinyl_api.caching import set_cache_headers
from vinyl_api.deps import SessionDep
from vinyl_api.feed_query import latest_event_per_release
from vinyl_api.schemas.release import ReleaseOut
from vinyl_api.serializers import release_to_out

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


@router.get("/feed", response_model=FeedPage)
async def get_feed(
    session: SessionDep,
    request: Request,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=MAX_FEED_LIMIT)] = DEFAULT_FEED_LIMIT,
) -> Response:
    """다가오는 일정과 최근 이벤트를 한 타임라인으로 반환한다."""
    now = datetime.now(UTC)

    upcoming_rows = (
        await session.scalars(
            select(Release)
            .where(
                Release.is_published.is_(True),
                Release.preorder_opens_at.is_not(None),
                Release.preorder_opens_at >= now,
            )
            .options(selectinload(Release.links))
            .order_by(Release.preorder_opens_at.asc(), Release.id.asc())
            .limit(limit)
        )
    ).all()

    items: list[FeedItem] = [
        FeedItem(
            kind=FeedKind.UPCOMING,
            at=row.preorder_opens_at,  # type: ignore[arg-type]  # 위 where 절이 NULL 을 배제한다
            release=await release_to_out(session, row),
        )
        for row in upcoming_rows
    ]

    remaining = limit - len(items)
    if remaining > 0:
        # 발매당 최신 이벤트 하나만 (T-118). 같은 앨범이 피드 상단을 여러 줄
        # 차지하는 것을 막는다 — 자세한 이유는 `feed_query` 참조.
        event_rows = (await session.execute(latest_event_per_release(remaining))).all()
        for event, release in event_rows:
            items.append(
                FeedItem(
                    kind=FeedKind.EVENT,
                    at=event.occurred_at,
                    event_type=event.event_type,
                    release=await release_to_out(session, release),
                )
            )

    page = FeedPage(items=items, generated_at=now)
    payload = Response(content=page.model_dump_json(), media_type="application/json")
    # generated_at 이 매번 바뀌므로 ETag 는 항목 부분만으로 계산한다.
    set_cache_headers(payload, page.items)

    if request.headers.get("If-None-Match") == payload.headers.get("ETag"):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=dict(payload.headers))
    return payload
