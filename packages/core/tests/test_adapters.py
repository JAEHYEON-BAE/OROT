"""어댑터 프로토콜과 레지스트리 (T-004).

어댑터가 하나도 구현되지 않은 상태에서도 전부 통과해야 한다.
"""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from vinyl_core.adapters import registry as registry_module
from vinyl_core.adapters.base import (
    MIN_CRAWL_INTERVAL_SECONDS,
    RawItem,
    SourceAdapter,
    StockStatus,
)
from vinyl_core.adapters.registry import (
    AdapterRegistrationError,
    available_source_ids,
    get_adapter,
    register,
)

KST = timezone(timedelta(hours=9))


@pytest.fixture
def clean_registry() -> Iterator[None]:
    registry_module._reset_for_testing()
    yield
    registry_module._reset_for_testing()


def _make_adapter(source_id: str = "dummy", interval: int = 1800) -> type:
    class DummyAdapter:
        pass

    DummyAdapter.source_id = source_id  # type: ignore[attr-defined]
    DummyAdapter.display_name = "더미"  # type: ignore[attr-defined]
    DummyAdapter.base_url = "https://example.com"  # type: ignore[attr-defined]
    DummyAdapter.crawl_interval_seconds = interval  # type: ignore[attr-defined]
    DummyAdapter.requires_javascript = False  # type: ignore[attr-defined]

    def discover(self: object) -> AsyncIterator[str]:  # pragma: no cover - 표면만 필요
        raise NotImplementedError

    async def parse_page(self: object, url: str, html: str) -> list[RawItem]:
        return []

    DummyAdapter.discover = discover  # type: ignore[attr-defined]
    DummyAdapter.parse_page = parse_page  # type: ignore[attr-defined]
    return DummyAdapter


# ─── 인수 조건 ──────────────────────────────────────────────────


def test_registry_imports_with_no_adapters_implemented(clean_registry: None) -> None:
    """T-004 인수 조건: 어댑터 미구현 상태에서 registry 임포트가 성공한다."""
    assert available_source_ids() == []


def test_unknown_source_id_raises_with_helpful_message(clean_registry: None) -> None:
    with pytest.raises(KeyError, match="등록되지 않은 source_id"):
        get_adapter("nope")


# ─── 등록 ──────────────────────────────────────────────────────


def test_registered_adapter_is_retrievable(clean_registry: None) -> None:
    register(_make_adapter("gimbab"))
    registry_module._loaded = True  # 자동 임포트를 건너뛴다

    assert available_source_ids() == ["gimbab"]
    assert get_adapter("gimbab").source_id == "gimbab"


def test_duplicate_source_id_is_rejected(clean_registry: None) -> None:
    """중복 등록을 허용하면 한 소스가 다른 소스를 조용히 가린다."""
    register(_make_adapter("gimbab"))
    with pytest.raises(AdapterRegistrationError, match="중복"):
        register(_make_adapter("gimbab"))


@pytest.mark.parametrize("bad_id", ["Gimbab", "gimbab-records", "김밥"])
def test_source_id_must_be_lowercase_ascii_slug(clean_registry: None, bad_id: str) -> None:
    with pytest.raises(AdapterRegistrationError, match="슬러그"):
        register(_make_adapter(bad_id))


@pytest.mark.parametrize("interval", [0, 60, 299])
def test_crawl_interval_below_blueprint_minimum_is_rejected(
    clean_registry: None, interval: int
) -> None:
    """블루프린트 §3.4 의 예의 있는 크롤 규칙을 등록 시점에 강제한다."""
    with pytest.raises(AdapterRegistrationError, match=str(MIN_CRAWL_INTERVAL_SECONDS)):
        register(_make_adapter("slow", interval=interval))


def test_adapter_satisfies_protocol(clean_registry: None) -> None:
    adapter = _make_adapter("gimbab")()
    assert isinstance(adapter, SourceAdapter)


# ─── RawItem ───────────────────────────────────────────────────


def _raw(**overrides: object) -> RawItem:
    base: dict[str, object] = {
        "source_id": "gimbab",
        "source_item_id": "32562",
        "url": "https://gimbabrecords.com/product/detail.html?product_no=32562",
        "title_raw": "나플라 Nafla / instinct (Grey Marbled Vinyl, 2LP)",
        "stock_status": StockStatus.IN_STOCK,
    }
    return RawItem.model_validate(base | overrides)


def test_raw_item_defaults_are_none_not_empty_string() -> None:
    """빈 문자열과 '값 없음'은 다르다. 정규화 단계에서 구분되어야 한다."""
    item = _raw()
    assert item.artist_raw is None
    assert item.label_raw is None
    assert item.price_krw is None
    assert item.extra == {}


def test_price_krw_rejects_fractional_values() -> None:
    """원화에는 소수 단위가 없다 (CLAUDE.md §6). NUMERIC(12,0) 이 조용히 반올림하기 전에 막는다."""
    with pytest.raises(ValidationError, match="소수점"):
        _raw(price_krw=Decimal("52000.5"))


def test_price_krw_rejects_negative() -> None:
    with pytest.raises(ValidationError, match="음수"):
        _raw(price_krw=Decimal("-1"))


def test_price_krw_accepts_integral_decimal() -> None:
    assert _raw(price_krw=Decimal("52000")).price_krw == Decimal("52000")


def test_fetched_at_rejects_naive_datetime() -> None:
    """KST→UTC 변환은 파싱 시점에 한다 (CLAUDE.md §6)."""
    with pytest.raises(ValidationError, match="tz-aware"):
        _raw(fetched_at=datetime(2026, 8, 20, 14, 0, 0))


def test_fetched_at_converts_kst_to_utc() -> None:
    item = _raw(fetched_at=datetime(2026, 8, 20, 14, 0, 0, tzinfo=KST))
    assert item.fetched_at == datetime(2026, 8, 20, 5, 0, 0, tzinfo=UTC)
    assert item.fetched_at.tzinfo is UTC


def test_fetched_at_defaults_to_aware_utc_now() -> None:
    assert _raw().fetched_at.tzinfo is UTC


def test_stock_status_members_match_blueprint() -> None:
    """§3.1 원안 유지 — PREORDER 취급은 ADR-0001 에서 보류 중이다."""
    assert {s.value for s in StockStatus} == {
        "IN_STOCK",
        "SOLD_OUT",
        "PREORDER",
        "COMING_SOON",
        "UNKNOWN",
    }


# ─── 시드와의 정합성 ─────────────────────────────────────────────


def test_every_registered_adapter_has_a_seeded_source() -> None:
    """어댑터의 `source_id` 는 `sources.yaml` 에 반드시 있어야 한다.

    없으면 수집 시 `listings.source_id` 외래키가 깨진다.
    어댑터가 아직 없는 지금은 공집합이라 자동 통과하지만,
    T-007 이후 어댑터를 추가하면서 시드를 빠뜨리면 여기서 잡힌다.
    """
    from vinyl_core.seed import load_source_seeds

    seeded = {s.id for s in load_source_seeds()}
    registered = set(available_source_ids())
    assert registered <= seeded, f"시드에 없는 어댑터: {sorted(registered - seeded)}"
