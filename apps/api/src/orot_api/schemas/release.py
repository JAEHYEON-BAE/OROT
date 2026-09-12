"""발매 일정 요청·응답 모델 (ADR-0005)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from urllib.parse import urlparse

from orot_core.enums import Curation
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
    model_validator,
)


class ReleaseLinkIn(BaseModel):
    """구매 링크 입력."""

    shop_name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2048)
    source_id: str | None = None
    price_krw: Decimal | None = None

    @field_validator("url")
    @classmethod
    def _http_scheme_only(cls, v: str) -> str:
        """`http`/`https` 만 받는다 (T-130).

        이 값은 공개 화면에서 `<a href>` 로 그대로 쓰인다. `javascript:` 를
        저장할 수 있으면 **저장형 XSS** 가 된다 — 지금은 운영자만 등록하지만,
        운영자 키가 새는 순간 방문자 전원에게 실행된다.
        """
        if any(ord(c) < 32 for c in v):
            raise ValueError("URL 에 제어 문자를 사용할 수 없습니다.")
        TypeAdapter(HttpUrl).validate_python(v)
        scheme = urlparse(v).scheme.lower()
        if scheme not in {"http", "https"}:
            msg = "url 은 http 또는 https 여야 합니다."
            raise ValueError(msg)
        return v

    @field_validator("price_krw")
    @classmethod
    def _integral_won(cls, v: Decimal | None) -> Decimal | None:
        """원화는 소수 단위가 없다 (CLAUDE.md §6)."""
        if v is None:
            return None
        if not v.is_finite() or v != v.to_integral_value() or not 0 <= v <= 999999999999:
            msg = f"price_krw 는 0부터 999999999999 사이의 정수여야 합니다: {v}"
            raise ValueError(msg)
        return v


class ReleaseLinkOut(BaseModel):
    """구매 링크 응답.

    `price_krw` 를 `int` 로 내보낸다. `NUMERIC(12,0)` 을 그대로 직렬화하면
    Postgres 가 `Decimal('5E+4')` 로 돌려주어 `"5E+4"` 라는 값이 API 에 나간다.
    원화에는 소수 단위가 없으므로 정수가 정직한 타입이다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_name: str
    url: str
    source_id: str | None = None
    price_krw: int | None = None

    @field_validator("price_krw", mode="before")
    @classmethod
    def _decimal_to_int(cls, v: object) -> object:
        if isinstance(v, Decimal):
            return int(v)
        return v


class ReleaseIn(BaseModel):
    """일정 등록 입력.

    운영자가 채우는 값이다. `title` 외에는 전부 선택이며,
    **알림의 트리거는 `preorder_opens_at`** 이다.
    """

    title: str = Field(min_length=1)
    artist_name: str | None = None
    label: str | None = None
    format: str | None = None
    variant: str | None = None
    is_limited: bool = False
    release_date: date | None = None
    preorder_opens_at: datetime | None = None
    preorder_closes_at: datetime | None = None
    cover_url: str | None = None
    notes: str | None = None
    links: list[ReleaseLinkIn] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def _nonempty_title(cls, value: str) -> str:
        if value is None or not value.strip():
            raise ValueError("제목은 비어 있을 수 없습니다.")
        return value.strip()

    @field_validator("preorder_opens_at", "preorder_closes_at")
    @classmethod
    def _timezone_aware(cls, v: datetime | None) -> datetime | None:
        """KST 로 받아 UTC 로 저장한다 (CLAUDE.md §6).

        naive datetime 을 허용하면 운영자가 입력한 시각이 몇 시인지 알 수 없어지고,
        알림이 9시간 어긋난다.
        """
        if v is None:
            return None
        if v.tzinfo is None:
            msg = "시각에는 타임존이 필요합니다 (예: 2026-08-25T14:00:00+09:00)."
            raise ValueError(msg)
        return v.astimezone(UTC)

    @model_validator(mode="after")
    def _check_window(self) -> "ReleaseIn":
        """예약 마감이 시작보다 빠를 수 없다.

        **모델 검증기로 둔다.** 별도 메서드로 두면 새 엔드포인트에서 호출을 빠뜨릴 수 있고,
        그러면 구간이 음수인 일정이 조용히 저장된다.
        검증기는 `model_validate` 를 거치는 모든 경로에서 자동으로 돈다.
        """
        if (
            self.preorder_opens_at is not None
            and self.preorder_closes_at is not None
            and self.preorder_closes_at <= self.preorder_opens_at
        ):
            msg = "preorder_closes_at 은 preorder_opens_at 보다 뒤여야 합니다."
            raise ValueError(msg)
        return self


class ReleaseUpdate(BaseModel):
    """부분 수정. 보낸 필드만 바뀐다."""

    title: str | None = Field(default=None, min_length=1)
    artist_name: str | None = None
    label: str | None = None
    format: str | None = None
    variant: str | None = None
    is_limited: bool | None = None
    release_date: date | None = None
    preorder_opens_at: datetime | None = None
    preorder_closes_at: datetime | None = None
    cover_url: str | None = None
    notes: str | None = None
    links: list[ReleaseLinkIn] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def _nonempty_title(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("제목은 비어 있을 수 없습니다.")
        return value.strip()

    @field_validator("is_limited")
    @classmethod
    def _nonnull_limited(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("is_limited 는 null 일 수 없습니다.")
        return value

    @field_validator("preorder_opens_at", "preorder_closes_at")
    @classmethod
    def _timezone_aware(cls, v: datetime | None) -> datetime | None:
        """`ReleaseIn` 과 같은 규칙 — naive datetime 을 거부하고 UTC 로 변환한다."""
        if v is None:
            return None
        if v.tzinfo is None:
            msg = "시각에는 타임존이 필요합니다 (예: 2026-08-25T14:00:00+09:00)."
            raise ValueError(msg)
        return v.astimezone(UTC)


class ReleaseOut(BaseModel):
    """공개 응답. `notes` 는 운영자 메모라 노출하지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist_name: str | None = None
    label: str | None = None
    format: str | None = None
    variant: str | None = None
    is_limited: bool
    release_date: date | None = None
    preorder_opens_at: datetime | None = None
    preorder_closes_at: datetime | None = None
    cover_url: str | None = None
    curation: Curation
    is_published: bool
    links: list[ReleaseLinkOut] = Field(default_factory=list)


class ReleaseAdminOut(ReleaseOut):
    """운영자 응답. 메모까지 포함한다."""

    notes: str | None = None
    can_delete: bool = Field(
        default=False,
        description="비공개이며 연결된 수집 상품이 없어 삭제 가능한가",
    )
