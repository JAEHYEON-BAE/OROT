"""알림 발송 계획과 페이로드 (T-115, ADR-0006).

**멱등성은 코드가 아니라 제약이 보장한다.** `notification_deliveries` 의
`UNIQUE (event_id, device_token_id)` 가 같은 알림을 두 번 만들지 못하게 한다.
스케줄러가 재기동해도, 두 프로세스가 겹쳐 돌아도 결과가 같다.

실제 발송(HTTP)은 `PushSender` 프로토콜 뒤에 둔다 — `pywebpush` 는 collector 의
의존성이고 `packages/core` 는 그쪽을 임포트할 수 없다 (의존 방향).
"""

import asyncio
import time
from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final, Protocol
from urllib.parse import urlparse

import structlog
from sqlalchemy import Select, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from orot_core.enums import DeliveryStatus, DevicePlatform, EventType
from orot_core.models import DeviceToken, ListingEvent, NotificationDelivery, Release

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
MAX_ATTEMPTS: Final = 3
SEND_CONCURRENCY: Final = 5
DISPATCH_SECONDS: Final = 45.0
# Retry windows are measured from delivery creation; each scheduler tick sends once.
RETRY_DELAYS: Final = (timedelta(minutes=1), timedelta(minutes=5))

_EVENT_LABEL: Final = {
    EventType.SCHEDULE_ADDED.value: "새 일정",
    EventType.SCHEDULE_CHANGED.value: "일정 변동",
    EventType.PREORDER_OPENS_SOON.value: "예약 임박",
    EventType.PREORDER_OPEN.value: "예약 시작",
    EventType.RELEASED.value: "발매",
}


# ─── 구독 엔드포인트 허용 목록 (T-130) ──────────────────────────
#
# **이것이 없으면 SSRF 다.** 구독 등록에는 인증이 없고(ADR-0006), `endpoint` 는
# 클라이언트가 주는 URL 이다. 검증하지 않으면 인터넷의 누구나 임의 주소를 등록해
# 이 서버가 그쪽으로 POST 를 보내게 만들 수 있다 — `http://127.0.0.1:8000/admin`,
# `http://192.168.0.1/` 처럼 **밖에서는 닿지 못하게 막아 둔 내부망**이 포함된다.
#
# 브라우저 푸시 서비스는 종류가 정해져 있으므로 목록으로 막는 것이 정확하다.
ALLOWED_PUSH_HOSTS: Final = frozenset(
    {
        "web.push.apple.com",  # Safari / iOS
        "push.apple.com",  # 애플의 지역별 하위 도메인 대비
        "fcm.googleapis.com",  # Chrome / Edge
        "android.googleapis.com",  # 구형 FCM
        "push.services.mozilla.com",  # Firefox
        "notify.windows.com",  # Windows (WNS)
    }
)

# 엔드포인트 길이 상한. 실제 값은 200자 안팎이다.
# 8KB 를 넘기면 `device_tokens.token` 의 UNIQUE 인덱스가 터져 500 이 난다 —
# 인증 없이 누구나 서버 오류를 만들 수 있는 경로였다 (T-130).
MAX_ENDPOINT_LENGTH: Final = 2048

# 브라우저가 주는 암호화 키 길이 상한 (RFC 8291). p256dh 는 65바이트, auth 는 16바이트를
# base64url 로 담은 값이라 넉넉히 잡아도 이보다 짧다.
MAX_PUSH_KEY_LENGTH: Final = 256


def is_allowed_push_endpoint(endpoint: str) -> bool:
    """알려진 푸시 서비스로 가는 https 주소인가."""
    if (
        not endpoint
        or len(endpoint) > MAX_ENDPOINT_LENGTH
        or not endpoint.isascii()
        or any(ord(c) <= 32 or ord(c) == 127 for c in endpoint)
        or "\\" in endpoint
    ):
        return False
    try:
        parsed = urlparse(endpoint)
        if parsed.port not in {None, 443} or parsed.username or parsed.password or parsed.fragment:
            return False
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False

    host = (parsed.hostname or "").lower()
    # **`endswith(host)` 만 쓰면 안 된다** — `evilpush.apple.com` 이
    # `push.apple.com` 으로 끝나서 통과한다. 점 경계를 반드시 확인한다.
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in ALLOWED_PUSH_HOSTS)


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
    exhausted: int = 0
    """재시도를 다 쓰고 **영영 실패한** 배송 수 (T-116).

    이것이 0 이 아니면 구독자가 알림을 못 받았다는 뜻이다 —
    스케줄러가 이 값을 보고 운영자에게 알린다. 실패(`failed`)와 구분해야 한다:
    실패는 다음 주기에 다시 시도하지만, 소진은 더 이상 시도하지 않는다.
    """
    deactivated: int = 0
    """만료(404/410)로 이번에 꺼진 구독 수."""


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
        "url": f"{base_url.rstrip('/')}/releases/{release.id}",
        # 브라우저는 같은 `tag` 의 알림을 **하나로 묶어 뒤엣것이 앞엣것을 대체**한다.
        #
        # 그래서 발매 단위가 아니라 **이벤트 단위**로 묶는다 (T-131).
        # 발매 단위로 묶으면 '예약 임박'이 '예약 시작'에 덮여 사라지는데,
        # 알림 목록은 상태가 아니라 **기록**이다 — 놓친 알림을 나중에 돌아보는 곳이라
        # 지워 버리면 "예약이 언제 시작한다고 했더라"를 확인할 방법이 없다.
        # (피드는 반대로 발매당 하나만 보여 준다. 그쪽은 지금 상태를 보는 화면이다.)
        #
        # 이벤트 단위로 묶어도 필요한 대체는 그대로 일어난다 — 일정이 바뀌어
        # 옛 '예약 시작'이 무효화되고(T-119) 새 시각으로 다시 발생하면, tag 가 같아
        # **틀린 시각을 말하던 알림이 새것으로 교체된다.** 그때 소리가 나도록
        # 서비스워커가 renotify 를 켠다.
        "tag": f"release-{release.id}-{event.event_type}",
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
            .join(Release, ListingEvent.release_id == Release.id)
            .where(
                ListingEvent.event_type.in_([e.value for e in NOTIFIABLE]),
                ListingEvent.occurred_at >= horizon,
                ListingEvent.occurred_at <= moment,
                ListingEvent.superseded_at.is_(None),
                Release.is_published.is_(True),
                ListingEvent.release_id.is_not(None),
            )
            .order_by(
                case((ListingEvent.event_type == EventType.PREORDER_OPEN.value, 0), else_=1),
                ListingEvent.occurred_at.asc(),
                ListingEvent.id.asc(),
            )
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

    pending = list(await session.scalars(_pending_query(moment)))
    results = [DispatchResult(planned=planned)]
    for delivery in pending:
        results.append(await _send_one(session, sender, delivery, base_url=base_url, moment=moment))
    await session.flush()
    return _sum_results(results)


def _pending_query(moment: datetime) -> Select[tuple[NotificationDelivery]]:
    return (
        select(NotificationDelivery)
        .join(ListingEvent, NotificationDelivery.event_id == ListingEvent.id)
        .where(
            or_(
                NotificationDelivery.status == DeliveryStatus.PENDING.value,
                (NotificationDelivery.status == DeliveryStatus.FAILED.value)
                & (NotificationDelivery.attempts < MAX_ATTEMPTS)
                & (
                    NotificationDelivery.created_at
                    <= case(
                        (NotificationDelivery.attempts <= 1, moment - RETRY_DELAYS[0]),
                        else_=moment - RETRY_DELAYS[1],
                    )
                ),
            )
        )
        .order_by(
            case((NotificationDelivery.status == DeliveryStatus.PENDING.value, 0), else_=1),
            case((ListingEvent.event_type == EventType.PREORDER_OPEN.value, 0), else_=1),
            NotificationDelivery.created_at.asc(),
            NotificationDelivery.id.asc(),
        )
        .with_for_update(skip_locked=True, of=NotificationDelivery)
        .limit(MAX_BATCH)
    )


def _sum_results(results: list[DispatchResult]) -> DispatchResult:
    return DispatchResult(
        **{
            field.name: sum(getattr(r, field.name) for r in results)
            for field in fields(DispatchResult)
        }
    )


async def _send_one(
    session: AsyncSession,
    sender: PushSender,
    delivery: NotificationDelivery,
    *,
    base_url: str,
    moment: datetime,
    durable: bool = False,
) -> DispatchResult:
    sent = failed = expired = exhausted = deactivated = 0
    event = await session.get(
        ListingEvent,
        delivery.event_id,
        options=[selectinload(ListingEvent.release)],
        populate_existing=True,
    )
    subscription = await session.get(DeviceToken, delivery.device_token_id, populate_existing=True)
    if event is None or subscription is None or event.release is None:
        delivery.status = DeliveryStatus.EXPIRED
        delivery.last_error = "이벤트 또는 구독을 찾을 수 없음"
        expired += 1
        return DispatchResult(expired=1)

    if (
        event.superseded_at is not None
        or not event.release.is_published
        or not subscription.is_active
        or event.occurred_at < moment - MAX_NOTIFY_AGE
        or event.occurred_at < subscription.created_at
    ):
        delivery.status = DeliveryStatus.EXPIRED
        delivery.last_error = "일정 무효화, 공개 취소, 구독 해지 또는 발송 기한 초과"
        expired += 1
        return DispatchResult(expired=1)

    artist = event.release.primary_artist
    artist_name = artist.name_display if artist else None

    payload = build_payload(event, event.release, artist_name, base_url)
    if durable:
        # Finish all reads before HTTP. expire_on_commit=False preserves the snapshot.
        await session.commit()
    try:
        send_result = await sender.send(subscription, payload)
    except Exception as exc:
        # A broken sender must not roll back earlier successful deliveries.
        log.error("push.sender_failed", delivery_id=delivery.id, error=type(exc).__name__)
        send_result = SendResult(SendOutcome.FAILED, type(exc).__name__)

    delivery.attempts += 1
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
        if subscription.is_active:
            subscription.is_active = False
            deactivated += 1
            log.info("push.subscription.expired", subscription_id=subscription.id)
        expired += 1
    else:
        delivery.status = DeliveryStatus.FAILED
        delivery.last_error = send_result.error
        subscription.failure_count += 1
        if delivery.attempts >= MAX_ATTEMPTS:
            exhausted += 1
            log.error("push.retry_exhausted", delivery_id=delivery.id)
        failed += 1

    return DispatchResult(
        sent=sent, failed=failed, expired=expired, exhausted=exhausted, deactivated=deactivated
    )


async def dispatch_committed(
    factory: async_sessionmaker[AsyncSession],
    sender: PushSender,
    *,
    base_url: str,
    now: datetime | None = None,
) -> DispatchResult:
    """Runtime dispatch under the scheduler's session advisory lock.

    Planning and each result are committed separately. HTTP holds no transaction.
    At most five sends are in flight; start new work only within a 45-second budget.
    Each subscription is handled serially, preserving GONE and failure counters.
    A crash can still repeat in-flight accepted pushes, not the completed batch.
    """
    moment = now or datetime.now(UTC)
    deadline = time.monotonic() + DISPATCH_SECONDS
    async with factory() as session:
        planned = len(await plan_deliveries(session, now=moment))
        pending = list(await session.scalars(_pending_query(moment)))
        groups: dict[int, list[int]] = {}
        for delivery in pending:
            groups.setdefault(delivery.device_token_id, []).append(delivery.id)
        await session.commit()
    results = [DispatchResult(planned=planned)]
    semaphore = asyncio.Semaphore(SEND_CONCURRENCY)

    async def send_group(ids: list[int]) -> None:
        for delivery_id in ids:
            async with semaphore:
                if time.monotonic() >= deadline:
                    return
                async with factory() as session:
                    delivery = await session.get(NotificationDelivery, delivery_id)
                    if delivery is None or delivery.status in (
                        DeliveryStatus.SENT,
                        DeliveryStatus.EXPIRED,
                    ):
                        continue
                    result = await _send_one(
                        session,
                        sender,
                        delivery,
                        base_url=base_url,
                        moment=datetime.now(UTC),
                        durable=True,
                    )
                    await session.commit()
                    results.append(result)

    # TaskGroup waits/cancels all siblings before the scheduler can release its lock.
    async with asyncio.TaskGroup() as tasks:
        for ids in groups.values():
            tasks.create_task(send_group(ids))
    return _sum_results(results)
