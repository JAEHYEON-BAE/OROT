"""DB CHECK 제약과 짝을 이루는 열거형.

블루프린트 §4.2 의 DDL 은 PostgreSQL ENUM 타입이 아니라 `TEXT + CHECK` 를 쓴다.
값을 늘리는 데 마이그레이션이 필요 없고, 애플리케이션 계층에서 의미를 관리하기 쉽기 때문이다.
여기 정의된 값과 DDL 의 CHECK 목록은 **항상 일치해야 한다.**

`StockStatus` 는 여기 없다 — 블루프린트 §3.1 에 따라 `adapters/base.py` 에 정의된다 (T-004).
"""

from enum import StrEnum


class SourceKind(StrEnum):
    """소스의 성격. `sources.kind`."""

    SHOP = "shop"
    LABEL = "label"
    DISTRIBUTOR = "distributor"


class Curation(StrEnum):
    """일정의 출처. `releases.curation` (ADR-0005).

    수동 등록분과 크롤 산출물이 같은 테이블에 병존하므로 구분이 필요하다.
    """

    MANUAL = "MANUAL"
    CRAWLED = "CRAWLED"


class EventType(StrEnum):
    """이벤트 종류. `listing_events.event_type`.

    두 갈래가 있다 (ADR-0005):
    - **시각 기반** — 운영자가 입력한 일정에서 스케줄러가 생성한다. diff 가 필요 없다
    - **diff 기반** — 크롤 결과를 직전 상태와 비교해 생성한다 (M3)
    """

    # 시각 기반 (수동 등록)
    SCHEDULE_ADDED = "SCHEDULE_ADDED"
    # 운영자가 이미 공개된 일정의 시각을 바꿨다. 구독자는 옛 시각을 알고 있으므로
    # 바뀐 사실 자체가 알림 대상이다 — 이걸 안 보내면 잘못된 시각을 믿고 기다린다.
    SCHEDULE_CHANGED = "SCHEDULE_CHANGED"
    PREORDER_OPENS_SOON = "PREORDER_OPENS_SOON"
    PREORDER_OPEN = "PREORDER_OPEN"
    RELEASED = "RELEASED"

    # diff 기반 (자동 수집, M3)
    NEW_LISTING = "NEW_LISTING"
    RESTOCK = "RESTOCK"
    SOLD_OUT = "SOLD_OUT"
    PRICE_DROP = "PRICE_DROP"
    PRICE_RISE = "PRICE_RISE"
    DELISTED = "DELISTED"


class MergeResolution(StrEnum):
    """병합 검토 결과. `merge_candidates.resolution`."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class WatchTargetType(StrEnum):
    """워치리스트 대상 종류. `watchlist_items.target_type`."""

    ARTIST = "ARTIST"
    LABEL = "LABEL"
    RELEASE = "RELEASE"
    KEYWORD = "KEYWORD"


class DevicePlatform(StrEnum):
    """푸시 대상 플랫폼. `device_tokens.platform`.

    `WEB` 은 Web Push(PWA), `IOS` 는 APNs 다 (ADR-0006).
    """

    IOS = "IOS"
    WEB = "WEB"


class DeliveryStatus(StrEnum):
    """발송 상태. `notification_deliveries.status` (ADR-0006 §5.2)."""

    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    # 구독이 만료됨 (Web Push 404/410). 재시도하지 않고 구독을 비활성화한다.
    EXPIRED = "EXPIRED"
