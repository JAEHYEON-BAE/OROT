"""사용자·워치리스트·디바이스 토큰 (블루프린트 §4.2).

M4(계정) / M6(푸시) 에서 실제로 쓰이지만, 스키마는 초기 마이그레이션에 함께 만든다.
"""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from orot_core.enums import DeliveryStatus, DevicePlatform, WatchTargetType
from orot_core.models.base import Base


class User(Base):
    """사용자. Sign in with Apple 을 1순위 인증 수단으로 삼는다(§8)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    apple_sub: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WatchlistItem(Base):
    """워치리스트 항목.

    `target_ref` 는 `target_type` 에 따라 의미가 달라진다 —
    artist_id / 레이블명 / release_id / 키워드 문자열.
    """

    __tablename__ = "watchlist_items"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('ARTIST','LABEL','RELEASE','KEYWORD')",
            name="target_type_valid",
        ),
        UniqueConstraint(
            "user_id", "target_type", "target_ref", name="uq_watchlist_items_user_target"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[WatchTargetType] = mapped_column(Text, nullable=False)
    target_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DeviceToken(Base):
    """푸시 구독 (ADR-0006).

    `token` 은 플랫폼마다 의미가 다르다 — `WEB` 이면 푸시 엔드포인트 URL,
    `IOS` 면 APNs 디바이스 토큰. `UNIQUE (platform, token)` 이 중복 구독을 막는다.
    """

    __tablename__ = "device_tokens"
    __table_args__ = (
        CheckConstraint("platform IN ('IOS','WEB')", name="platform_valid"),
        UniqueConstraint("platform", "token", name="uq_device_tokens_platform_token"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Web Push 는 구독 자체가 식별자라 계정이 필요 없다 (계정 시스템은 M4).
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )
    platform: Mapped[DevicePlatform] = mapped_column(Text, nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    # Web Push 암호화(RFC 8291)에 필요. IOS 에는 NULL.
    p256dh: Mapped[str | None] = mapped_column(Text)
    auth: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class NotificationDelivery(Base):
    """발송 기록. **재발송을 구조적으로 막는 장치다** (ADR-0006 §5.2).

    `UNIQUE (event_id, device_token_id)` 하나가 멱등성을 보장한다 —
    스케줄러가 재기동해도, 두 프로세스가 겹쳐 돌아도 같은 알림이 두 번 나가지 않는다.
    """

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','SENT','FAILED','EXPIRED')", name="status_valid"),
        UniqueConstraint("event_id", "device_token_id", name="uq_deliveries_event_device"),
        Index("ix_notification_deliveries_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listing_events.id", ondelete="CASCADE"), nullable=False
    )
    device_token_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("device_tokens.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        Text, nullable=False, server_default=DeliveryStatus.PENDING.value
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
