"""ORM → 공개 응답 변환.

`notes` 는 운영자 메모이므로 **공개 응답에 절대 넣지 않는다.**
"""

from orot_core.models import Release
from sqlalchemy.ext.asyncio import AsyncSession

from orot_api.schemas.release import ReleaseLinkOut, ReleaseOut


async def release_to_out(session: AsyncSession, release: Release) -> ReleaseOut:
    """`Release` 를 공개 응답으로 바꾼다."""
    artist = release.primary_artist
    artist_name = artist.name_display if artist else None
    return ReleaseOut(
        id=release.id,
        title=release.title,
        artist_name=artist_name,
        label=release.label,
        format=release.format,
        variant=release.variant,
        is_limited=release.is_limited,
        schedule_status=release.schedule_status or "SCHEDULED",
        until_sold_out=release.until_sold_out or False,
        release_date=release.release_date,
        preorder_opens_at=release.preorder_opens_at,
        preorder_closes_at=release.preorder_closes_at,
        cover_url=release.cover_url,
        curation=release.curation,
        is_published=release.is_published,
        links=[ReleaseLinkOut.model_validate(link) for link in release.links],
    )
