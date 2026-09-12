"""소스 마스터 및 원본 스냅샷 (블루프린트 §4.2)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from orot_core.enums import SourceKind
from orot_core.models.base import Base

# 블루프린트 §3.4 / §3.1: 크롤 주기는 300초 미만이 될 수 없다.
MIN_CRAWL_INTERVAL_SEC = 300


class Source(Base):
    """수집 대상 사이트. `id` 는 `gimbab` 처럼 소문자 ASCII 슬러그."""

    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('shop','label','distributor')",
            name="kind_valid",
        ),
        CheckConstraint(
            f"crawl_interval_sec >= {MIN_CRAWL_INTERVAL_SEC}",
            name="crawl_interval_min",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[SourceKind] = mapped_column(Text, nullable=False)
    crawl_interval_sec: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1800")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    disabled_reason: Mapped[str | None] = mapped_column(Text)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RawSnapshot(Base):
    """가져온 응답의 메타데이터.

    **본문은 DB 에 저장하지 않는다** — `body_path` 로 외부 저장소를 가리킨다.
    블루프린트 §3.4 의 "저작물 재사용 최소화" 원칙과, DB 비대화 방지를 위한 것이다.
    """

    __tablename__ = "raw_snapshots"
    __table_args__ = (
        Index("ix_raw_snapshots_source_id_fetched_at", "source_id", text("fetched_at DESC")),
        Index("ix_raw_snapshots_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(Text, ForeignKey("sources.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)  # sha256(body)
    body_path: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
