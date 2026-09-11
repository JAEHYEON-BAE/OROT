"""운영자 API — 발매 일정 수동 등록 (ADR-0005, 블루프린트 §5.2-1).

인증은 `X-Admin-Key` 헤더 하나다. 계정 시스템을 쓰지 않는다.
"""

import re
import unicodedata
from typing import Any, Final, cast

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from vinyl_core.enums import Curation, EventType
from vinyl_core.models import Artist, Listing, ListingEvent, Release, ReleaseLink
from vinyl_core.schedule_events import supersede_stale_events

from vinyl_api.deps import AdminDep, SessionDep
from vinyl_api.schemas.release import (
    ReleaseAdminOut,
    ReleaseIn,
    ReleaseLinkIn,
    ReleaseLinkOut,
    ReleaseUpdate,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def normalize_name(value: str) -> str:
    """병합 키용 최소 정규화.

    본격적인 `normalize.py`(구 T-008)는 자동 수집 재개(M3) 때 필요해진다.
    수동 등록 단계에서는 같은 아티스트를 같은 행에 모으는 정도면 충분하다.
    """
    text = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"\s+", " ", text)


async def _get_or_create_artist(session: AsyncSession, name: str) -> Artist:
    """이름으로 아티스트를 찾고 없으면 만든다."""
    name_norm = normalize_name(name)
    existing = await session.scalar(select(Artist).where(Artist.name_norm == name_norm))
    if existing is not None:
        return existing
    await session.execute(
        insert(Artist)
        .values(name_display=name.strip(), name_norm=name_norm)
        .on_conflict_do_nothing(index_elements=[Artist.name_norm])
    )
    artist = await session.scalar(select(Artist).where(Artist.name_norm == name_norm))
    assert artist is not None
    return artist


async def _load(session: AsyncSession, release_id: int, *, lock: bool = False) -> Release:
    release = await session.scalar(
        select(Release)
        .where(Release.id == release_id)
        .options(selectinload(Release.links))
        .with_for_update()
        if lock
        else select(Release).where(Release.id == release_id).options(selectinload(Release.links))
    )
    if release is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="일정을 찾을 수 없습니다."
        )
    return release


async def _linked_listing_exists(session: AsyncSession, release_id: int) -> bool:
    """이 발매에 묶인 크롤 산출물(`listings`)이 있는가.

    `listings` 행은 **절대 지우지 않는다** (CLAUDE.md §2 규칙 4). 그렇다고 남겨 두면
    사라진 발매를 가리키는 행이 되므로, 이 경우에는 삭제를 거절한다.
    현재(M2)는 수동 등록만 있어 이런 행이 없지만, M3 에서 수집이 붙으면 생긴다.
    """
    return (
        await session.scalar(select(Listing.id).where(Listing.release_id == release_id).limit(1))
    ) is not None


async def _to_out(session: AsyncSession, release: Release) -> ReleaseAdminOut:
    artist_name = None
    if release.primary_artist_id is not None:
        artist = await session.get(Artist, release.primary_artist_id)
        artist_name = artist.name_display if artist else None
    return ReleaseAdminOut(
        can_delete=not release.is_published
        and not await _linked_listing_exists(session, release.id),
        id=release.id,
        title=release.title,
        artist_name=artist_name,
        label=release.label,
        format=release.format,
        variant=release.variant,
        is_limited=release.is_limited,
        release_date=release.release_date,
        preorder_opens_at=release.preorder_opens_at,
        preorder_closes_at=release.preorder_closes_at,
        cover_url=release.cover_url,
        curation=release.curation,
        is_published=release.is_published,
        notes=release.notes,
        links=[ReleaseLinkOut.model_validate(link) for link in release.links],
    )


@router.get("/releases", response_model=list[ReleaseAdminOut])
async def list_releases(session: SessionDep, _: AdminDep) -> list[ReleaseAdminOut]:
    """초안을 포함한 전체 일정."""
    releases = (
        await session.scalars(
            select(Release)
            .options(selectinload(Release.links))
            .order_by(Release.preorder_opens_at.desc().nullslast(), Release.id.desc())
        )
    ).all()
    return [await _to_out(session, r) for r in releases]


@router.get("/releases/{release_id}", response_model=ReleaseAdminOut)
async def get_release(release_id: int, session: SessionDep, _: AdminDep) -> ReleaseAdminOut:
    """일정 하나. 초안이어도 운영자에게는 보인다 (공개 API 와 다른 점)."""
    return await _to_out(session, await _load(session, release_id))


@router.post("/releases", response_model=ReleaseAdminOut, status_code=status.HTTP_201_CREATED)
async def create_release(payload: ReleaseIn, session: SessionDep, _: AdminDep) -> ReleaseAdminOut:
    """일정을 등록한다. **기본은 초안**이며 공개하려면 별도 호출이 필요하다."""
    # 예약 창 검사는 `ReleaseIn` 의 모델 검증기가 이미 마쳤다 (빠뜨릴 수 없도록).
    artist = (
        await _get_or_create_artist(session, payload.artist_name) if payload.artist_name else None
    )

    release = Release(
        title=payload.title.strip(),
        title_norm=normalize_name(payload.title),
        primary_artist_id=artist.id if artist else None,
        label=payload.label,
        format=payload.format,
        variant=payload.variant,
        is_limited=payload.is_limited,
        release_date=payload.release_date,
        preorder_opens_at=payload.preorder_opens_at,
        preorder_closes_at=payload.preorder_closes_at,
        cover_url=payload.cover_url,
        notes=payload.notes,
        curation=Curation.MANUAL,
        is_published=False,
    )
    session.add(release)
    await session.flush()

    # 같은 URL 을 두 번 넣는 것은 운영자의 실수지 오류가 아니다 — 조용히 하나로 합친다.
    # (DB 에는 UNIQUE(release_id, url) 이 걸려 있어 막지 않으면 500 이 난다.)
    seen_urls: set[str] = set()
    for link in payload.links:
        if link.url in seen_urls:
            log.info("admin.link.duplicate_ignored", release_id=release.id, url=link.url)
            continue
        seen_urls.add(link.url)
        session.add(
            ReleaseLink(
                release_id=release.id,
                source_id=link.source_id,
                shop_name=link.shop_name,
                url=link.url,
                price_krw=link.price_krw,
            )
        )
    await session.flush()
    await session.refresh(release, ["links"])

    log.info("admin.release.created", release_id=release.id, title=release.title)
    return await _to_out(session, release)


# 바뀌면 **구독자가 알아야 하는** 필드. 제목·메모가 바뀐 것은 알림거리가 아니지만,
# 시각이 바뀐 것은 다르다 — 구독자는 옛 시각을 알고 기다리고 있다.
SCHEDULE_FIELDS: Final = ("preorder_opens_at", "preorder_closes_at", "release_date")


def _schedule_snapshot(release: Release) -> dict[str, str | None]:
    """알림·기록에 남길 일정 시각. JSONB 에 넣을 수 있게 문자열로."""
    snapshot: dict[str, str | None] = {}
    for field in SCHEDULE_FIELDS:
        value = getattr(release, field)
        snapshot[field] = value.isoformat() if value is not None else None
    return snapshot


@router.patch("/releases/{release_id}", response_model=ReleaseAdminOut)
async def update_release(
    release_id: int, payload: ReleaseUpdate, session: SessionDep, _: AdminDep
) -> ReleaseAdminOut:
    release = await _load(session, release_id, lock=True)
    # 수정 **전** 시각을 먼저 떠 둔다. setattr 뒤에는 옛 값을 알 방법이 없다.
    before = _schedule_snapshot(release)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "links":
            continue
        if field == "artist_name":
            artist = await _get_or_create_artist(session, value) if value else None
            release.primary_artist_id = artist.id if artist else None
            continue
        setattr(release, field, value)
        if field == "title" and value:
            release.title_norm = normalize_name(value)

    if (
        release.preorder_opens_at
        and release.preorder_closes_at
        and release.preorder_closes_at <= release.preorder_opens_at
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "preorder_closes_at 은 preorder_opens_at 보다 뒤여야 합니다.",
        )

    after = _schedule_snapshot(release)
    changed = [f for f in SCHEDULE_FIELDS if before[f] != after[f]]
    # An unpublished release may still have events from its previous publication.
    # Invalidate those too, otherwise republishing suppresses the new schedule.
    superseded = await supersede_stale_events(session, release.id, changed) if changed else 0
    # **공개된 일정의 시각이 바뀐 경우에만** 알린다.
    # 초안은 아직 아무에게도 나가지 않았으므로 바뀐 사실이 뉴스가 아니고,
    # 값이 그대로면 저장만 다시 한 것이라 알림을 보내면 노이즈가 된다.
    if release.is_published and changed:
        session.add(
            ListingEvent(
                release_id=release.id,
                event_type=EventType.SCHEDULE_CHANGED,
                old_value=before,
                new_value={"title": release.title, **after},
            )
        )
        # 옛 시각에서 나온 '예약 임박'·'예약 시작'·'발매'는 역할을 잃었다 (T-119).
        # 무효화하면 피드에서 사라지고, 스케줄러가 **새 시각에 맞춰 다시** 만든다.
        log.info(
            "admin.release.schedule_changed",
            release_id=release.id,
            changed=changed,
            superseded=superseded,
        )

    if "links" in payload.model_fields_set:
        # Keep unchanged URL identities and apply the whole form in this transaction.
        desired = {link.url: link for link in payload.links}
        existing_links = {link.url: link for link in release.links}
        for url, link in existing_links.items():
            if url not in desired:
                await session.delete(link)
        for url, data in desired.items():
            link = existing_links.get(url)
            if link is None:
                session.add(ReleaseLink(release_id=release.id, **data.model_dump()))
            else:
                for field, value in data.model_dump().items():
                    setattr(link, field, value)
    await session.flush()
    await session.refresh(release, ["links"])
    log.info("admin.release.updated", release_id=release.id)
    return await _to_out(session, release)


@router.post("/releases/{release_id}/publish", response_model=ReleaseAdminOut)
async def publish_release(release_id: int, session: SessionDep, _: AdminDep) -> ReleaseAdminOut:
    """공개한다. 이 시점에 `SCHEDULE_ADDED` 이벤트가 **한 번만** 생긴다."""
    release = await _load(session, release_id, lock=True)
    release.is_published = True

    # **`is_published` 가 아니라 이벤트 존재 여부로 판단한다.**
    # 공개 → 취소 → 재공개 시 `is_published` 만 보면 이벤트가 두 번 생긴다.
    # 구독자에게 "새 일정"이 두 번 나가는 셈이라 알림 신뢰를 깎는다.
    already_announced = await session.scalar(
        select(ListingEvent.id)
        .where(
            ListingEvent.release_id == release.id,
            ListingEvent.event_type == EventType.SCHEDULE_ADDED.value,
        )
        .limit(1)
    )
    if already_announced is None:
        session.add(
            ListingEvent(
                release_id=release.id,
                event_type=EventType.SCHEDULE_ADDED,
                new_value={"title": release.title},
            )
        )
    await session.flush()
    log.info("admin.release.published", release_id=release.id)
    return await _to_out(session, release)


@router.post("/releases/{release_id}/unpublish", response_model=ReleaseAdminOut)
async def unpublish_release(release_id: int, session: SessionDep, _: AdminDep) -> ReleaseAdminOut:
    """공개를 취소해 초안으로 되돌린다.

    잘못 공개한 일정을 되돌릴 수단이 없으면 삭제도 못 한다
    (공개본 삭제는 409 로 막혀 있다).

    **이미 나간 `SCHEDULE_ADDED` 이벤트는 지우지 않는다.** 구독자에게 전달된 사실은
    남아야 하고, 다시 공개해도 이벤트가 또 생기지는 않는다.
    """
    release = await _load(session, release_id, lock=True)
    release.is_published = False
    await session.flush()
    log.info("admin.release.unpublished", release_id=release.id)
    return await _to_out(session, release)


@router.delete("/releases/{release_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_release(release_id: int, session: SessionDep, _: AdminDep) -> None:
    """**초안만** 삭제할 수 있다. 공개 중이면 먼저 공개를 취소해야 한다 (T-133).

    이전에는 "한 번도 공개된 적 없는" 것만 지울 수 있었다. 발송 이력을 지키려는
    규칙이었지만, 그 결과 **운영자가 남은 방법이 SQL 뿐**이 되었다.
    손으로 여러 테이블을 순서대로 지우는 쪽이 훨씬 위험하다 — 한 줄 틀리면
    남의 데이터까지 지운다. 그래서 가드를 여기로 옮긴다.

    **공개 중인 것은 여전히 못 지운다.** 공개 취소를 한 번 거치게 해서,
    실수로 살아 있는 일정을 지우는 일이 없도록 한 단계를 남긴다.

    감수하는 것 — 이 발매에 대해 **무엇을 언제 보냈는지 기록이 사라진다.**
    `notification_deliveries` 는 `listing_events` 의 CASCADE 로 함께 지워진다.
    """
    release = await _load(session, release_id, lock=True)

    if release.is_published:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "공개 중인 일정은 삭제할 수 없습니다. 공개를 먼저 취소하십시오.",
        )

    if await _linked_listing_exists(session, release.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "수집된 상품이 연결되어 있어 삭제할 수 없습니다.",
        )

    # 이벤트는 `release_id` 에 CASCADE 가 없어 직접 지운다.
    # 발송 기록(`notification_deliveries`)은 `event_id` CASCADE 로 함께 사라진다.
    events = await session.execute(
        delete(ListingEvent).where(ListingEvent.release_id == release.id)
    )
    await session.delete(release)
    try:
        # **여기서 flush 하지 않으면 오류가 응답 뒤에 터진다.**
        # 세션 커밋은 의존성 종료 시점이라, 그때 실패해도 클라이언트는 이미 204 를 받은 뒤다.
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "다른 데이터가 참조 중이라 삭제할 수 없습니다."
        ) from exc
    log.info(
        "admin.release.deleted",
        release_id=release_id,
        title=release.title,
        deleted_events=cast("CursorResult[Any]", events).rowcount,
    )


@router.post(
    "/releases/{release_id}/links",
    response_model=ReleaseLinkOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_link(
    release_id: int, payload: ReleaseLinkIn, session: SessionDep, _: AdminDep
) -> ReleaseLinkOut:
    release = await _load(session, release_id, lock=True)

    if any(existing.url == payload.url for existing in release.links):
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 등록된 구매처 URL 입니다.")

    link = ReleaseLink(
        release_id=release_id,
        source_id=payload.source_id,
        shop_name=payload.shop_name,
        url=payload.url,
        price_krw=payload.price_krw,
    )
    session.add(link)
    try:
        await session.flush()
    except IntegrityError as exc:
        # 동시 요청으로 경합했을 때. UNIQUE 제약이 최종 방어선이다.
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 등록된 구매처 URL 입니다.") from exc
    return ReleaseLinkOut.model_validate(link)


@router.delete("/releases/{release_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(release_id: int, link_id: int, session: SessionDep, _: AdminDep) -> None:
    """구매처 링크를 지운다. 여러 개를 등록할 수 있으니 지우는 수단도 있어야 한다."""
    link = await session.get(ReleaseLink, link_id)
    if link is None or link.release_id != release_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "구매처를 찾을 수 없습니다.")
    await session.delete(link)
    log.info("admin.link.deleted", release_id=release_id, link_id=link_id)
