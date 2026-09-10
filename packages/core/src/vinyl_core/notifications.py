"""알림 발송 계획과 페이로드 (T-115, ADR-0006).

**멱등성은 코드가 아니라 제약이 보장한다.** `notification_deliveries` 의
`UNIQUE (event_id, device_token_id)` 가 같은 알림을 두 번 만들지 못하게 한다.
스케줄러가 재기동해도, 두 프로세스가 겹쳐 돌아도 결과가 같다.

실제 발송(HTTP)은 `PushSender` 프로토콜 뒤에 둔다 — `pywebpush` 는 collector 의
의존성이고 `packages/core` 는 그쪽을 임포트할 수 없다 (의존 방향).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final, Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vinyl_core.enums import DeliveryStatus, DevicePlatform, EventType
from vinyl_core.models import Artist, DeviceToken, ListingEvent, NotificationDelivery, Release

log = structlog.get_logger(__name__)

# 알림을 보낼 이벤트 종류. 나머지(크롤 diff 계열)는 M3 에서 판단한다.
NOTIFIABLE: Final = frozenset(
    {
        EventType.SCHEDULE_ADDED,
        EventType.SCHEDULE_CHANGED,
        EventType.PREORDER_OPENS_SOON,
        EventType.PREORDER_OPEN,
        EventType.RELEASED,
    }
)

# 이보다 오래된 이벤트는 보내지 않는다.
# 발송기가 며칠 멈춰 있었다고 해서 지난 알림을 한꺼번에 쏟아내면 안 된다.
MAX_NOTIFY_AGE: Final = timedelta(hours=48)

# 한 번의 실행에서 만들 최대 배송 수. 폭주를 막는 안전장치.
MAX_BATCH: Final = 500

_EVENT_LABEL: Final = {
    EventType.SCHEDULE_ADDED.value: "새 일정",
    EventType.SCHEDULE_CHANGED.value: "일정 변동",
    EventType.PREORDER_OPENS_SOON.value: "예약 임박",
    EventType.PREORDER_OPEN.value: "예약 시작",
    EventType.RELEASED.value: "발매",
}


class SendOutcome(StrEnum):
    """발송 시도 결과."""

    SENT = "SENT"
    # 구독이 만료됨 (404/410). 재시도하지 않고 구독을 끈다.
    GONE = "GONE"
    # 일시적 실패. 다음 주기에 다시 시도한다.
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class SendResult:
    outcome: SendOutcome
    error: str | None = None


class PushSender(Protocol):
    """실제 HTTP 발송. 구현은 collector 에 있다."""

    async def send(self, subscription: DeviceToken, payload: dict[str, object]) -> SendResult: ...


@dataclass(frozen=True, slots=True)
class DispatchResult:
    planned: int = 0
    sent: int = 0
    failed: int = 0
    expired: int = 0


def _one_line(text: str) -> str:
    """알림에 넣을 한 줄 텍스트로 만든다.

    **알림 제목·본문은 한 줄 영역이다.** 개행이 그대로 들어가면 브라우저마다
    다르게 처리한다 — 크롬은 공백으로 접고, 일부 안드로이드 런처는 거기서
    잘라 버려 뒷부분이 사라진다. 서버에서 한 번 정리해 모든 클라이언트가
    같은 것을 보도록 한다 (iOS 네이티브가 붙어도 마찬가지다).
    """
    return " ".join(text.split())


def build_payload(
    event: ListingEvent, release: Release, artist_name: str | None, base_url: str
) -> dict[str, object]:
    """브라우저 알림에 표시될 내용.

    여기서 만든 키는 서비스워커(`apps/web/public/sw.js`)가 그대로 읽는다.
    이름을 바꾸면 알림이 조용히 기본 문구로 바뀌므로
    `test_edge_cases.py` 의 계약 시험이 양쪽을 맞춰 둔다.
    """
    label = f"{artist_name} — {release.title}" if artist_name else release.title
    action = _EVENT_LABEL.get(str(event.event_type), str(event.event_type))

    details: list[str] = []
    if release.format:
        details.append(release.format)
    if release.is_limited:
        details.append("한정반")
    if release.variant:
        details.append(release.variant)

    return {
        "title": _one_line(f"[{action}] {label}"),
        "body": _one_line(" · ".join(details)) or "자세히 보려면 눌러 주세요",
        "url": f"{base_url}/releases/{release.id}",
        # 같은 발매의 알림이 여러 개 쌓이지 않도록 브라우저가 묶는다.
        # 묶으면 **뒤에 온 알림이 앞의 것을 조용히 대체**하므로, 서비스워커는
        # renotify 를 켜서 '예약 임박' 뒤에 온 '예약 시작'을 놓치지 않게 한다.
        "tag": f"release-{release.id}",
        "event_type": str(event.event_type),
    }


async def plan_deliveries(
    session: AsyncSession, *, now: datetime | None = None
) -> list[NotificationDelivery]:
    """보내야 할 (이벤트 x 구독) 조합에 `PENDING` 배송을 만든다.

    **구독 이전에 일어난 이벤트는 보내지 않는다.** 새 구독자에게 지난 알림이
    한꺼번에 가면 곧바로 구독을 끊는다. "구독한 뒤에 생긴 일"만 받는 것이 자연스럽다.
    """
    moment = now or datetime.now(UTC)
    horizon = moment - MAX_NOTIFY_AGE

    events = list(
        await session.scalars(
            select(ListingEvent)
            .where(
                ListingEvent.event_type.in_([e.value for e in NOTIFIABLE]),
                ListingEvent.occurred_at >= horizon,
                ListingEvent.release_id.is_not(None),
            )
            .order_by(ListingEvent.occurred_at.asc())
        )
    )
    if not events:
        return []

    subscriptions = list(
        await session.scalars(
            select(DeviceToken).where(
                DeviceToken.is_active.is_(True),
                DeviceToken.platform == DevicePlatform.WEB.value,
            )
        )
    )
    if not subscriptions:
        return []

    # 이미 만들어진 조합은 건너뛴다. UNIQUE 제약이 최종 방어선이지만,
    # 미리 걸러야 매 주기 같은 INSERT 를 시도해 오류 로그가 쌓이지 않는다.
    existing = {
        (event_id, token_id)
        for event_id, token_id in (
            await session.execute(
                select(NotificationDelivery.event_id, NotificationDelivery.device_token_id).where(
                    NotificationDelivery.event_id.in_([e.id for e in events])
                )
            )
        ).all()
    }

    created: list[NotificationDelivery] = []
    for event in events:
        for subscription in subscriptions:
            if (event.id, subscription.id) in existing:
                continue
            # 구독보다 앞선 이벤트는 보내지 않는다.
            if event.occurred_at < subscription.created_at:
                continue
            delivery = NotificationDelivery(
                event_id=event.id,
                device_token_id=subscription.id,
                status=DeliveryStatus.PENDING,
            )
            session.add(delivery)
            created.append(delivery)
            if len(created) >= MAX_BATCH:
                break
        if len(created) >= MAX_BATCH:
            log.warning("notifications.batch_capped", cap=MAX_BATCH)
            break

    await session.flush()
    return created


async def dispatch_pending(
    session: AsyncSession, sender: PushSender, *, base_url: str, now: datetime | None = None
) -> DispatchResult:
    """`PENDING` 배송을 실제로 보낸다."""
    moment = now or datetime.now(UTC)
    planned = len(await plan_deliveries(session, now=moment))

    pending = list(
        await session.scalars(
            select(NotificationDelivery)
            .where(NotificationDelivery.status == DeliveryStatus.PENDING.value)
            .order_by(NotificationDelivery.created_at.asc())
            .limit(MAX_BATCH)
        )
    )

    sent = failed = expired = 0
    for delivery in pending:
        event = await session.get(
            ListingEvent, delivery.event_id, options=[selectinload(ListingEvent.release)]
        )
        subscription = await session.get(DeviceToken, delivery.device_token_id)
        if event is None or subscription is None or event.release is None:
            delivery.status = DeliveryStatus.FAILED
            delivery.last_error = "이벤트 또는 구독을 찾을 수 없음"
            failed += 1
            continue

        artist_name = None
        if event.release.primary_artist_id is not None:
            artist = await session.get(Artist, event.release.primary_artist_id)
            artist_name = artist.name_display if artist else None

        payload = build_payload(event, event.release, artist_name, base_url)
        delivery.attempts += 1
        send_result = await sender.send(subscription, payload)

        if send_result.outcome is SendOutcome.SENT:
            delivery.status = DeliveryStatus.SENT
            delivery.sent_at = moment
            delivery.last_error = None
            subscription.last_success_at = moment
            subscription.failure_count = 0
            sent += 1
        elif send_result.outcome is SendOutcome.GONE:
            # 구독이 사라졌다. 재시도해도 소용없으므로 구독을 끈다.
            delivery.status = DeliveryStatus.EXPIRED
            delivery.last_error = send_result.error
            subscription.is_active = False
            expired += 1
            log.info("push.subscription.expired", subscription_id=subscription.id)
        else:
            delivery.status = DeliveryStatus.FAILED
            delivery.last_error = send_result.error
            subscription.failure_count += 1
            failed += 1

    await session.flush()
    result = DispatchResult(planned=planned, sent=sent, failed=failed, expired=expired)
    if planned or sent or failed or expired:
        log.info(
            "notifications.dispatched",
            planned=planned,
            sent=sent,
            failed=failed,
            expired=expired,
        )
    return result
