"""수동 등록 스키마 계약 (T-101, ADR-0005).

DB 연결 없이 `Base.metadata` 만 검사한다.
"""

from orot_core.enums import Curation, EventType
from orot_core.models import Base, ListingEvent, MergeCandidate, Release, ReleaseLink


def test_release_has_schedule_fields() -> None:
    """예약창과 공개 여부가 있어야 일정 알림이 가능하다."""
    columns = Release.__table__.c
    assert columns.preorder_opens_at.type.timezone is True
    assert columns.preorder_closes_at.type.timezone is True
    assert columns.is_published.nullable is False
    assert columns.curation.nullable is False


def test_release_links_table_exists() -> None:
    """수동 등록 구매 링크는 `listings` 가 아니라 여기 들어간다."""
    assert "release_links" in Base.metadata.tables
    columns = ReleaseLink.__table__.c
    # 소스 미등록 판매처도 넣을 수 있어야 한다.
    assert columns.source_id.nullable is True
    assert columns.shop_name.nullable is False
    assert columns.price_krw.type.scale == 0


def test_listings_stays_crawl_only() -> None:
    """`listings` 의 크롤 불변식은 그대로여야 한다 (ADR-0005 §5).

    수동 등록을 위해 이 제약을 풀면 크롤 경로가 조용히 약해진다.
    """
    columns = Base.metadata.tables["listings"].c
    assert columns.source_item_id.nullable is False
    assert columns.content_hash.nullable is False


def test_manual_events_need_no_listing() -> None:
    """수동 일정 이벤트에는 listing 이 없다."""
    assert ListingEvent.__table__.c.listing_id.nullable is True
    # merge_candidates 는 크롤 전용이므로 여전히 필수다.
    assert MergeCandidate.__table__.c.listing_id.nullable is False


def test_event_anchor_constraint_exists() -> None:
    """listing_id 와 release_id 가 둘 다 NULL 이면 어디 붙은 이벤트인지 알 수 없다."""
    names = {c.name for c in ListingEvent.__table__.constraints if c.name}
    assert "ck_listing_events_anchor_required" in names


def test_time_driven_event_types_exist() -> None:
    """시각 기반 알림 3종 (ADR-0005 §4.2)."""
    assert EventType.SCHEDULE_ADDED
    assert EventType.PREORDER_OPENS_SOON
    assert EventType.RELEASED


def test_curation_distinguishes_manual_from_crawled() -> None:
    assert {c.value for c in Curation} == {"MANUAL", "CRAWLED"}


# ─── 푸시 구독·발송 (T-114, ADR-0006) ────────────────────────────


def test_push_subscription_needs_no_account() -> None:
    """Web Push 는 구독 자체가 식별자다 — 계정 시스템(M4) 전에도 구독할 수 있어야 한다."""
    from orot_core.models import DeviceToken

    assert DeviceToken.__table__.c.user_id.nullable is True


def test_web_push_keys_are_stored() -> None:
    """RFC 8291 암호화에 `p256dh` 와 `auth` 가 필요하다. IOS 에는 없으므로 NULL 허용."""
    from orot_core.models import DeviceToken

    columns = DeviceToken.__table__.c
    assert columns.p256dh.nullable is True
    assert columns.auth.nullable is True


def test_subscription_is_unique_per_platform_and_token() -> None:
    """같은 엔드포인트로 두 번 구독하면 알림이 두 번 간다."""
    from orot_core.models import DeviceToken

    uniques = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in DeviceToken.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("platform", "token") in uniques


def test_delivery_is_unique_per_event_and_device() -> None:
    """**발송 멱등성의 근거다** (ADR-0006 §5.2).

    이 제약 하나가 스케줄러 재기동·중복 실행에도 재발송을 막는다.
    """
    from orot_core.models import NotificationDelivery

    uniques = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in NotificationDelivery.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("device_token_id", "event_id") in uniques


def test_delivery_status_values() -> None:
    """`EXPIRED` 는 구독 만료(404/410)다 — 재시도하지 않고 구독을 끈다."""
    from orot_core.enums import DeliveryStatus

    assert {s.value for s in DeliveryStatus} == {"PENDING", "SENT", "FAILED", "EXPIRED"}
