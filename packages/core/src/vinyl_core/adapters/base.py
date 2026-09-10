"""어댑터 인터페이스 (블루프린트 §3.1).

**새 소스를 추가할 때 이 파일과 `adapters/<source_id>.py` 외의 코드는 바뀌지 않아야 한다.**
등록은 `registry.py` 가 자동으로 처리한다.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, HttpUrl, field_validator

# 블루프린트 §3.1 / §3.4: 소스별 크롤 주기 최소값.
MIN_CRAWL_INTERVAL_SECONDS = 300


class StockStatus(StrEnum):
    """재고 상태.

    > ⚠️ `PREORDER` 의 취급은 보류 중이다 — `docs/adr/0001-preorder-open-detection.md` (Deferred).
    > 조사 결과 국내 소스들은 예약 여부와 재고를 **별개 신호**로 제공하며
    > "예약판매인데 품절"이 실재하지만, 현 단계에서는 블루프린트 §3.1 원안을 그대로 유지한다.
    > 어댑터는 당분간 예약 마커를 판정에 쓰지 않고 `title_raw` 에 원문으로만 보존한다.
    """

    IN_STOCK = "IN_STOCK"  # 재고 있음
    SOLD_OUT = "SOLD_OUT"  # 품절
    PREORDER = "PREORDER"  # 예약판매 중
    COMING_SOON = "COMING_SOON"  # 입고 예정 (구매 불가)
    UNKNOWN = "UNKNOWN"


class RawItem(BaseModel):
    """어댑터가 반환하는 원시 항목. 정규화 전 상태를 그대로 보존한다.

    `*_raw` 필드는 소스 표기 그대로다. **절대 제자리에서 가공하지 않는다** (CLAUDE.md §4).
    정규화된 값은 `normalize()` 를 거쳐 별도 필드에 담긴다.
    """

    source_id: str
    source_item_id: str
    url: HttpUrl
    title_raw: str
    artist_raw: str | None = None
    label_raw: str | None = None
    price_krw: Decimal | None = None
    stock_status: StockStatus
    format_raw: str | None = None
    release_date_raw: str | None = None
    thumbnail_url: HttpUrl | None = None  # 저장만 하고 재호스팅하지 않는다 (§3.4)
    extra: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("price_krw")
    @classmethod
    def _won_has_no_minor_unit(cls, v: Decimal | None) -> Decimal | None:
        """원화는 소수 단위가 없다 (CLAUDE.md §6).

        float 나 소수점 값이 들어오면 가격 비교와 `PRICE_DROP` 판정이 미묘하게 틀어진다.
        컬럼이 `NUMERIC(12,0)` 이므로 여기서 막지 않으면 조용히 반올림된다.
        """
        if v is None:
            return None
        if v != v.to_integral_value():
            msg = f"price_krw 에는 소수점이 올 수 없습니다: {v}"
            raise ValueError(msg)
        if v < 0:
            msg = f"price_krw 는 음수일 수 없습니다: {v}"
            raise ValueError(msg)
        return v

    @field_validator("fetched_at")
    @classmethod
    def _must_be_timezone_aware(cls, v: datetime) -> datetime:
        """타임스탬프는 항상 tz-aware 여야 한다 (CLAUDE.md §6).

        소스 사이트는 KST 로 표기한다. **변환은 파싱 시점에 한다** — DB 나 표시 계층이 아니다.
        naive datetime 을 허용하면 그 규칙이 조용히 무너진다.
        """
        if v.tzinfo is None:
            msg = "fetched_at 은 tz-aware 여야 합니다 (KST→UTC 변환은 파싱 시점에)."
            raise ValueError(msg)
        return v.astimezone(UTC)


class PageFetcher(Protocol):
    """어댑터가 목록 페이지를 가져올 때 쓰는 최소 인터페이스.

    > 블루프린트 §3.1 의 `discover()` 는 목록 페이지를 순회해야 하지만 인자를 받지 않는다.
    > 실제 수집기(`vinyl_collector.fetcher.Fetcher`)는 `apps/collector` 에 있고
    > `packages/core` 는 그쪽을 임포트할 수 없으므로(의존 방향), 여기에 최소 프로토콜만 둔다.
    > 실제 주입은 파이프라인(T-009)이 담당한다.
    """

    async def fetch_text(self, url: str) -> str | None:
        """URL 의 본문을 반환한다. 가져올 수 없으면 `None`."""
        ...


@runtime_checkable
class SourceAdapter(Protocol):
    """모든 소스가 구현하는 프로토콜."""

    source_id: str
    display_name: str
    base_url: str
    crawl_interval_seconds: int  # 최소 300
    requires_javascript: bool

    def discover(self) -> AsyncIterator[str]:
        """**수집 대상 페이지** URL 을 순회 반환한다.

        목록 페이지일 수도 상세 페이지일 수도 있다 — 소스에 따라 다르다 (ADR-0004).
        목록 하나로 여러 상품을 얻을 수 있으면 목록 URL 을 내보내는 편이 요청 수가 크게 준다.
        """
        ...

    async def parse_page(self, url: str, html: str) -> list[RawItem]:
        """페이지 HTML 에서 `RawItem` 을 **모두** 뽑는다.

        목록 페이지면 여러 건, 상세 페이지면 1건, 아무것도 못 뽑으면 빈 목록이다.

        파싱 실패 시 빈 목록을 반환하고 **반드시 로그를 남긴다.**
        예외를 삼키지 않는다 (CLAUDE.md §2 규칙 5) — 조용한 0건 수집이 최악의 실패 모드다.
        """
        ...
