"""모델 스키마 계약 테스트 (T-002).

블루프린트 §4.2 의 DDL 과 ORM 정의가 어긋나면 여기서 잡는다.
DB 연결이 필요 없다 — `Base.metadata` 만 검사한다.
실 PostgreSQL 대상 검증은 §9.3 에 따라 T-010 에서 testcontainers 로 추가한다.
"""

from decimal import Decimal

import pytest
from sqlalchemy import Numeric

from orot_core.enums import DevicePlatform, EventType, SourceKind, WatchTargetType
from orot_core.models import Base, Listing

# 블루프린트 §4.2 가 정의한 테이블 전부.
EXPECTED_TABLES = {
    "sources",
    "raw_snapshots",
    "artists",
    "releases",
    "release_artists",
    "release_links",
    "listings",
    "listing_events",
    "merge_candidates",
    "users",
    "watchlist_items",
    "device_tokens",
    "notification_deliveries",
}


def test_all_blueprint_tables_are_defined() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_price_krw_is_integral_numeric_not_float() -> None:
    """원화에는 소수 단위가 없다 (CLAUDE.md §6).

    float 가 섞이면 가격 비교와 PRICE_DROP 판정이 미묘하게 틀어진다.
    """
    column = Listing.__table__.c.price_krw
    assert isinstance(column.type, Numeric)
    assert column.type.scale == 0
    assert column.type.precision == 12
    assert column.type.asdecimal is True
    assert column.type.python_type is Decimal


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("listings", "first_seen_at"),
        ("listings", "last_seen_at"),
        ("listing_events", "occurred_at"),
        ("raw_snapshots", "fetched_at"),
        ("releases", "created_at"),
        ("releases", "updated_at"),
        ("users", "created_at"),
    ],
)
def test_timestamps_are_timezone_aware(table: str, column: str) -> None:
    """모든 타임스탬프는 TIMESTAMPTZ 다 (CLAUDE.md §6).

    소스는 KST 로 발행하지만 DB 에는 UTC 로 들어간다. naive 컬럼이 하나라도 있으면
    변환 시점이 흐려져 발매일·이벤트 시각이 어긋난다.
    """
    assert Base.metadata.tables[table].c[column].type.timezone is True


def test_listing_release_id_is_nullable() -> None:
    """병합 전에는 NULL 이어야 한다 (블루프린트 §4.4 S4).

    신뢰도 0.70~0.90 구간에서 추측 병합을 하지 않고 보류하려면 NULL 이 허용되어야 한다.
    """
    assert Listing.__table__.c.release_id.nullable is True


def test_listing_source_item_is_unique_per_source() -> None:
    """같은 소스의 같은 상품이 두 행으로 늘어나면 이벤트가 중복 발생한다."""
    uniques = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in Listing.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("source_id", "source_item_id") in uniques


def test_enum_values_match_ddl_check_constraints() -> None:
    """열거형 값과 DDL CHECK 목록은 항상 같아야 한다."""
    assert {e.value for e in SourceKind} == {"shop", "label", "distributor"}
    assert {e.value for e in EventType} == {
        # 시각 기반 (수동 등록, ADR-0005)
        "SCHEDULE_ADDED",
        "SCHEDULE_CHANGED",
        "PREORDER_OPENS_SOON",
        "PREORDER_OPEN",
        "RELEASED",
        # diff 기반 (자동 수집, M3)
        "NEW_LISTING",
        "RESTOCK",
        "SOLD_OUT",
        "PRICE_DROP",
        "PRICE_RISE",
        "DELISTED",
    }
    assert {e.value for e in WatchTargetType} == {"ARTIST", "LABEL", "RELEASE", "KEYWORD"}
    assert {e.value for e in DevicePlatform} == {"IOS", "WEB"}
