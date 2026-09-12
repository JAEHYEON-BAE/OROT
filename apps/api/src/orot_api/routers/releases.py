"""공개 발매 일정 API (T-105, 블루프린트 §5.2).

**초안(`is_published=false`)은 절대 노출하지 않는다.**
새어 나가면 아직 공지되지 않은 발매가 유출된다 — 이 API 의 가장 중요한 불변식이다.
"""

from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from orot_core.models import Release
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, literal_column, select
from sqlalchemy.orm import selectinload

from orot_api.caching import set_cache_headers
from orot_api.deps import SessionDep
from orot_api.pagination import (
    DEFAULT_LIMIT,
    InvalidCursorError,
    clamp_limit,
    decode_cursor,
    encode_cursor,
)
from orot_api.schemas.release import ReleaseOut
from orot_api.serializers import release_to_out

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["releases"])

# 날짜 미정 일정을 정렬 맨 뒤로 보낸다 (pagination 모듈 주석 참조).
_SORT_KEY = func.coalesce(Release.preorder_opens_at, literal_column("'infinity'::timestamptz"))


class ReleasePage(BaseModel):
    """커서 페이지네이션 응답 (§5.1)."""

    items: list[ReleaseOut]
    next_cursor: str | None = Field(
        default=None, description="다음 페이지 커서. null 이면 마지막 페이지."
    )


def _published_only(statement: Select) -> Select:
    """공개된 일정만. **이 프로젝트에서 가장 중요한 필터다.**"""
    return statement.where(Release.is_published.is_(True))


@router.get("/releases", response_model=ReleasePage)
async def list_releases(
    session: SessionDep,
    request: Request,
    response: Response,
    cursor: Annotated[str | None, Query(description="이전 응답의 next_cursor")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = DEFAULT_LIMIT,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    format_: Annotated[str | None, Query(alias="format")] = None,
    is_limited: bool | None = None,
) -> Response:
    """공개된 발매 일정 목록.

    정렬은 **예약 시작이 임박한 순**이며, 날짜 미정 일정은 맨 뒤로 간다.
    """
    statement = _published_only(select(Release).options(selectinload(Release.links)))

    if date_from is not None:
        statement = statement.where(Release.release_date >= date_from)
    if date_to is not None:
        statement = statement.where(Release.release_date <= date_to)
    if format_ is not None:
        statement = statement.where(Release.format == format_)
    if is_limited is not None:
        statement = statement.where(Release.is_limited.is_(is_limited))

    if cursor:
        try:
            last_key, last_id = decode_cursor(cursor)
        except InvalidCursorError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        key_value = literal_column("'infinity'::timestamptz") if last_key is None else last_key
        # keyset: (정렬키, id) 가 커서보다 뒤인 행만.
        statement = statement.where(
            (key_value < _SORT_KEY) | ((key_value == _SORT_KEY) & (Release.id > last_id))
        )

    size = clamp_limit(limit)
    # 다음 페이지 존재 여부를 알기 위해 한 건 더 가져온다.
    statement = statement.order_by(_SORT_KEY.asc(), Release.id.asc()).limit(size + 1)

    rows = list((await session.scalars(statement)).all())
    has_more = len(rows) > size
    rows = rows[:size]

    page = ReleasePage(
        items=[await release_to_out(session, r) for r in rows],
        next_cursor=(
            encode_cursor(rows[-1].preorder_opens_at, rows[-1].id) if has_more and rows else None
        ),
    )

    payload = Response(
        content=page.model_dump_json(),
        media_type="application/json",
        headers=dict(response.headers),
    )
    set_cache_headers(payload, page)

    # 조건부 요청: 내용이 그대로면 본문을 보내지 않는다.
    if request.headers.get("If-None-Match") == payload.headers.get("ETag"):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=dict(payload.headers))
    return payload


@router.get("/releases/{release_id}", response_model=ReleaseOut)
async def get_release(release_id: int, session: SessionDep) -> ReleaseOut:
    """공개된 일정 하나.

    초안은 **404** 로 응답한다 — 403 으로 구분하면 "존재는 한다"는 사실이 새어 나간다.
    """
    release = await session.scalar(
        _published_only(
            select(Release).where(Release.id == release_id).options(selectinload(Release.links))
        )
    )
    if release is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "일정을 찾을 수 없습니다.")
    return await release_to_out(session, release)
