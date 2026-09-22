"""정규화된 발매(판)와 아티스트 연결 (블루프린트 §4.2)."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orot_core.enums import Curation
from orot_core.models.base import Base

if TYPE_CHECKING:
    from orot_core.models.artist import Artist


class Release(Base):
    """물리적 실체로서의 한 판(edition).

    **주의 (블루프린트 §4.1, CLAUDE.md §6)**: `variant` 가 다르면 서로 다른 행이다.
    클리어반과 블랙반은 수집가에게 다른 상품이므로 절대 병합하지 않는다.
    """

    __tablename__ = "releases"
    __table_args__ = (
        CheckConstraint("curation IN ('MANUAL','CRAWLED')", name="curation_valid"),
        CheckConstraint(
            "schedule_status IN ('SCHEDULED','TBA','ON_SALE')", name="schedule_status_valid"
        ),
        CheckConstraint(
            "schedule_status != 'TBA' OR (preorder_opens_at IS NULL "
            "AND preorder_closes_at IS NULL AND release_date IS NULL AND NOT until_sold_out)",
            name="tba_dates_empty",
        ),
        CheckConstraint(
            "schedule_status != 'ON_SALE' OR preorder_opens_at IS NULL", name="on_sale_start_empty"
        ),
        CheckConstraint(
            "NOT until_sold_out OR preorder_closes_at IS NULL", name="until_sold_out_end_empty"
        ),
        # barcode 는 최우선 병합 키(§4.4 S1). NULL 은 중복을 허용해야 하므로 부분 유니크.
        Index(
            "uq_releases_barcode",
            "barcode",
            unique=True,
            postgresql_where=text("barcode IS NOT NULL"),
        ),
        Index(
            "ix_releases_title_norm_trgm",
            "title_norm",
            postgresql_using="gin",
            postgresql_ops={"title_norm": "gin_trgm_ops"},
        ),
        # DDL 은 `release_date DESC NULLS LAST` — 최신 발매 우선 조회(§5.2)를 위한 정렬 인덱스.
        Index("ix_releases_release_date", text("release_date DESC NULLS LAST")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_norm: Mapped[str] = mapped_column(Text, nullable=False)
    primary_artist_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("artists.id"))
    label: Mapped[str | None] = mapped_column(Text)
    catalog_no: Mapped[str | None] = mapped_column(Text)
    barcode: Mapped[str | None] = mapped_column(Text)
    format: Mapped[str | None] = mapped_column(Text)  # 'LP','2LP','7INCH','BOXSET'
    variant: Mapped[str | None] = mapped_column(Text)  # 'Clear Vinyl','Limited 300'
    is_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    release_date: Mapped[date | None] = mapped_column(Date)

    # ─── 일정 알림용 (ADR-0005) ──────────────────────────────
    # 예약 시작. **알림의 트리거**이므로 이 값이 곧 제품의 중심이다.
    preorder_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 예약 마감. 어느 소스도 노출하지 않아 **수동 등록만 채울 수 있다** (ADR-0005 §3).
    preorder_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schedule_status: Mapped[Literal["SCHEDULED", "TBA", "ON_SALE"]] = mapped_column(
        Text, nullable=False, server_default="SCHEDULED"
    )
    until_sold_out: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    curation: Mapped[Curation] = mapped_column(Text, nullable=False, server_default="MANUAL")
    # 초안은 공개 API 에 노출하지 않는다 — 새어 나가면 미공지 발매가 유출된다.
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text)  # 운영자 메모 (비공개)
    # ─────────────────────────────────────────────────────────

    country: Mapped[str | None] = mapped_column(Text)
    discogs_id: Mapped[int | None] = mapped_column(BigInteger)
    cover_url: Mapped[str | None] = mapped_column(Text)
    # v1.1 확장용 자기참조. 동일 앨범의 여러 판을 묶는 상위 개념(§4.1 master).
    master_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("releases.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    primary_artist: Mapped["Artist | None"] = relationship(
        foreign_keys=[primary_artist_id], lazy="selectin"
    )

    links: Mapped[list["ReleaseLink"]] = relationship(
        back_populates="release", cascade="all, delete-orphan", lazy="selectin"
    )


class ReleaseArtist(Base):
    """발매 ↔ 아티스트 다대다. 컴필레이션처럼 여러 아티스트가 얽힌 경우를 위한 것."""

    __tablename__ = "release_artists"

    release_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("releases.id", ondelete="CASCADE"), primary_key=True
    )
    artist_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False, server_default="primary"
    )


class ReleaseLink(Base):
    """구매 링크 (ADR-0005).

    `listings` 를 재활용하지 않는다 — 그쪽은 `source_item_id` 와 `content_hash` 가 `NOT NULL`
    이며 수동 등록에는 존재하지 않는 값이다. 제약을 느슨하게 만들면 크롤 경로의 불변식이 약해진다.
    """

    __tablename__ = "release_links"
    __table_args__ = (
        UniqueConstraint("release_id", "url", name="uq_release_links_release_id_url"),
        Index("ix_release_links_release_id", "release_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    release_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("releases.id", ondelete="CASCADE"), nullable=False
    )
    # 등록된 소스면 연결하고, 아니면 NULL 로 두고 shop_name 만 쓴다.
    source_id: Mapped[str | None] = mapped_column(Text, ForeignKey("sources.id"))
    shop_name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    price_krw: Mapped[Decimal | None] = mapped_column(Numeric(12, 0))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    release: Mapped[Release] = relationship(back_populates="links")
