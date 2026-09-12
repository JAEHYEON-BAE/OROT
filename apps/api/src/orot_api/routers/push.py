"""Web Push 구독 (T-114, ADR-0006).

**인증이 없다.** Web Push 구독은 그 자체가 식별자라 계정이 필요 없다 —
RSS·iCalendar 를 계정 없이 구독하게 한 것과 같은 이유다.
"""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, status
from orot_core.enums import DevicePlatform
from orot_core.models import DeviceToken
from orot_core.settings import get_settings
from sqlalchemy import func, select, text

from orot_api.deps import SessionDep
from orot_api.rate_limit import MAX_ACTIVE_SUBSCRIPTIONS, subscribe_limiter
from orot_api.schemas.push import (
    PushPublicKeyOut,
    PushSubscriptionIn,
    PushSubscriptionOut,
    PushUnsubscribeIn,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/push", tags=["push"])


@router.get("/public-key", response_model=PushPublicKeyOut)
async def public_key() -> PushPublicKeyOut:
    """브라우저가 구독할 때 필요한 VAPID 공개키.

    키가 없으면 `enabled=false` 를 돌려준다 — 클라이언트가 구독 버튼을 감출 수 있도록.
    오류로 다루지 않는 이유는 푸시가 없어도 나머지 기능은 멀쩡하기 때문이다.
    """
    settings = get_settings()
    return PushPublicKeyOut(public_key=settings.vapid_public_key, enabled=settings.push_enabled)


@router.post("/subscribe", response_model=PushSubscriptionOut, status_code=status.HTTP_201_CREATED)
async def subscribe(payload: PushSubscriptionIn, session: SessionDep) -> PushSubscriptionOut:
    """구독을 등록한다.

    같은 엔드포인트로 다시 구독하면 **오류가 아니라 갱신**이다. 브라우저는 권한을
    다시 물을 때마다 같은 구독을 돌려주므로, 중복 요청이 정상 경로다.
    """
    settings = get_settings()
    if not settings.push_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "서버에 푸시가 설정되어 있지 않습니다."
        )

    # 인증이 없는 쓰기 경로다 (ADR-0006). 상한이 없으면 인터넷의 누구나
    # `device_tokens` 를 무한히 채울 수 있고, 그 행마다 발송기가 매 주기 요청을 시도한다.
    if not subscribe_limiter.allow():
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "구독 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
            headers={"Retry-After": str(subscribe_limiter.retry_after)},
        )

    await session.execute(text("SELECT pg_advisory_xact_lock(86170422)"))
    existing = await session.scalar(
        select(DeviceToken).where(
            DeviceToken.platform == DevicePlatform.WEB.value,
            DeviceToken.token == payload.endpoint,
        )
    )

    if existing is None or not existing.is_active:
        active = await session.scalar(
            select(func.count()).select_from(DeviceToken).where(DeviceToken.is_active.is_(True))
        )
        if (active or 0) >= MAX_ACTIVE_SUBSCRIPTIONS:
            raise HTTPException(503, "구독 정원이 가득 찼습니다. 운영자에게 문의해 주세요.")

    if existing is not None:
        if not existing.is_active:
            # A new subscription period must not receive events from the disabled period.
            existing.created_at = datetime.now(UTC)
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
        existing.is_active = True
        existing.failure_count = 0
        await session.flush()
        log.info("push.subscription.refreshed", subscription_id=existing.id)
        return PushSubscriptionOut(id=existing.id, endpoint=existing.token, created=False)

    subscription = DeviceToken(
        platform=DevicePlatform.WEB,
        token=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
    )
    session.add(subscription)
    await session.flush()
    log.info("push.subscription.created", subscription_id=subscription.id)
    return PushSubscriptionOut(id=subscription.id, endpoint=subscription.token, created=True)


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(payload: PushUnsubscribeIn, session: SessionDep) -> None:
    """구독을 해지한다.

    행을 지우지 않고 **비활성화**한다 — 이미 보낸 기록(`notification_deliveries`)이
    참조하고 있고, 무엇을 언제 보냈는지는 남아야 한다.
    없는 엔드포인트를 해지해도 204 다 (멱등).
    """
    await session.execute(text("SELECT pg_advisory_xact_lock(86170422)"))
    subscription = await session.scalar(
        select(DeviceToken).where(
            DeviceToken.platform == DevicePlatform.WEB.value,
            DeviceToken.token == payload.endpoint,
        )
    )
    if subscription is None:
        return
    subscription.is_active = False
    await session.flush()
    log.info("push.subscription.deactivated", subscription_id=subscription.id)
