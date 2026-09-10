"""SQLAlchemy ORM 모델 (블루프린트 §4.2).

Alembic 이 `Base.metadata` 로 전체 스키마를 보려면 모든 모델이 임포트되어야 하므로,
여기서 한 번에 재노출한다.
"""

from vinyl_core.models.artist import Artist
from vinyl_core.models.base import Base
from vinyl_core.models.listing import Listing, ListingEvent, MergeCandidate
from vinyl_core.models.release import Release, ReleaseArtist, ReleaseLink
from vinyl_core.models.source import RawSnapshot, Source
from vinyl_core.models.user import (
    DeviceToken,
    NotificationDelivery,
    User,
    WatchlistItem,
)

__all__ = [
    "Artist",
    "Base",
    "DeviceToken",
    "Listing",
    "ListingEvent",
    "MergeCandidate",
    "NotificationDelivery",
    "RawSnapshot",
    "Release",
    "ReleaseArtist",
    "ReleaseLink",
    "Source",
    "User",
    "WatchlistItem",
]
