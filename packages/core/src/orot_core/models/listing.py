"""판매처별 상품과 상태 변화 이벤트 (블루프린트 §4.2)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, REAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orot_core.enums import EventType
from orot_core.models.base import Base
from orot_core.models.release import Release


class Listing(Base):
    """특정 판매처의 특정 상품 페이지 하나.

    **불변식 (CLAUDE.md §2 규칙 4)**: 이 테이블의 행은 **삭제하지 않는다.**
    개체 병합은 `release_id` 만 바꾼다. 그래야 병합을 되돌릴 수 있다.

    `*_raw` 컬럼은 소스 표기를 그대로 담는다. 절대 제자리에서 정규화하지 않는다.
    """

    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "source_item_id", name="uq_listings_source_id_source_item_id"
        ),
        Index("ix_listings_release_id", "release_id"),
        Index("ix_listings_first_seen_at", text("first_seen_at DESC")),
        # 구매 가능한 상품만 걸러 보는 조회가 압도적으로 많으므로 부분 인덱스로 좁힌다.
        Index(
            "ix_listings_stock_status",
            "stock_status",
            postgresql_where=text("stock_status IN ('PREORDER','IN_STOCK')"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(Text, ForeignKey("sources.id"), nullable=False)
    source_item_id: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # 병합 전에는 NULL. 신뢰도 0.70~0.90 구간은 NULL 로 두고 merge_candidates 로 보낸다(§4.4 S4).
    release_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("releases.id"))

    title_raw: Mapped[str] = mapped_column(Text, nullable=False)
    artist_raw: Mapped[str | None] = mapped_column(Text)
    label_raw: Mapped[str | None] = mapped_column(Text)
    # 원화는 소수 단위가 없다. NUMERIC(12,0) — float 를 절대 개입시키지 않는다.
    price_krw: Mapped[Decimal | None] = mapped_column(Numeric(12, 0))
    stock_status: Mapped[str] = mapped_column(Text, nullable=False)
    format_raw: Mapped[str | None] = mapped_column(Text)
    release_date_raw: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    # 소스 고유 필드. 스키마 변경 없이 원본 정보를 보존한다.
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ListingEvent(Base):
    """상태 변화 이벤트. 모든 알림의 원천 (블루프린트 §4.5)."""

    __tablename__ = "listing_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'SCHEDULE_ADDED','SCHEDULE_CHANGED','PREORDER_OPENS_SOON','PREORDER_OPEN',"
            "'RELEASED',"
            "'NEW_LISTING','RESTOCK','SOLD_OUT','PRICE_DROP','PRICE_RISE','DELISTED')",
            name="event_type_valid",
        ),
        # 수동 등록 일정에서 나온 이벤트는 listing 이 없다 (ADR-0005).
        # 둘 다 NULL 이면 어디에 붙은 이벤트인지 알 수 없으므로 최소 하나는 있어야 한다.
        CheckConstraint(
            "listing_id IS NOT NULL OR release_id IS NOT NULL",
            name="anchor_required",
        ),
        Index("ix_listing_events_occurred_at", text("occurred_at DESC")),
        Index("ix_listing_events_release_id_occurred_at", "release_id", text("occurred_at DESC")),
        # 피드와 멱등성 판정이 모두 "무효화되지 않은 것"만 본다.
        Index(
            "ix_listing_events_live",
            "release_id",
            text("occurred_at DESC"),
            postgresql_where=text("superseded_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 수동 등록 일정 이벤트는 listing 이 없다 — release_id 가 주 앵커다 (ADR-0005).
    listing_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE")
    )
    release_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("releases.id"))
    event_type: Mapped[EventType] = mapped_column(Text, nullable=False)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # 일정이 바뀌어 **역할을 잃은** 이벤트에 표시한다 (T-119).
    #
    # 지우지 않는 이유: 이 행은 "구독자에게 실제로 보냈다"는 기록이고,
    # `notification_deliveries` 가 참조한다. 보낸 사실은 취소되지 않는다.
    # 대신 표시해 두고 **피드에서 감추고, 다시 발생할 수 있게** 한다 —
    # 예약 시각이 미뤄지면 새 시각에 '예약 시작'이 다시 나가야 하기 때문이다.
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    release: Mapped["Release | None"] = relationship(lazy="selectin")


class MergeCandidate(Base):
    """병합 보류 큐 (블루프린트 §4.4 S4).

    재현율보다 정밀도를 우선한다 — 확신이 없으면 병합하지 않고 여기에 쌓는다.
    """

    __tablename__ = "merge_candidates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 수동 등록 일정 이벤트는 listing 이 없다 — release_id 가 주 앵커다 (ADR-0005).
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    release_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("releases.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(REAL, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    resolution: Mapped[str | None] = mapped_column(Text)  # 'ACCEPTED' | 'REJECTED'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
