"""Web Push 실제 발송 (T-115, ADR-0006).

`pywebpush` 는 동기 라이브러리(내부적으로 `requests`)라 그대로 부르면
스케줄러의 이벤트 루프를 막는다. `asyncio.to_thread` 로 감싼다.

**404/410 은 실패가 아니라 "구독이 사라졌다"는 뜻이다.** 재시도해도 소용없으므로
`GONE` 으로 구분해 호출자가 구독을 끄게 한다 — 죽은 구독에 매 주기 요청을 보내면
푸시 서비스가 우리를 차단할 수 있다.
"""

import asyncio
import json
from typing import Final

import structlog
from pywebpush import WebPushException, webpush
from vinyl_core.models import DeviceToken
from vinyl_core.notifications import SendOutcome, SendResult
from vinyl_core.settings import get_settings

log = structlog.get_logger(__name__)

# 푸시 서비스가 메시지를 보관할 시간. 이보다 오래 기기가 꺼져 있으면 버려진다.
# 예약 시작 알림은 늦게 도착하면 의미가 없으므로 길게 잡지 않는다.
TTL_SECONDS: Final = 6 * 60 * 60

# 구독이 사라졌음을 뜻하는 상태 코드 (RFC 8030 §7.3).
GONE_STATUS: Final = frozenset({404, 410})

REQUEST_TIMEOUT: Final = 10


class WebPushSender:
    """`vinyl_core.notifications.PushSender` 구현."""

    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = settings.push_enabled
        self._private_key = settings.vapid_private_key
        self._claims = {"sub": settings.vapid_subject}
        if not self._enabled:
            log.warning("push.disabled", reason="VAPID 키가 설정되지 않음")

    async def send(self, subscription: DeviceToken, payload: dict[str, object]) -> SendResult:
        if not self._enabled:
            return SendResult(SendOutcome.FAILED, "서버에 푸시가 설정되어 있지 않음")
        if not subscription.p256dh or not subscription.auth:
            # 키 없이는 암호화가 불가능하다. 재시도해도 달라지지 않는다.
            return SendResult(SendOutcome.GONE, "구독에 암호화 키가 없음")

        info = {
            "endpoint": subscription.token,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        }
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=info,
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=self._private_key,
                vapid_claims=dict(self._claims),
                ttl=TTL_SECONDS,
                timeout=REQUEST_TIMEOUT,
            )
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in GONE_STATUS:
                return SendResult(SendOutcome.GONE, f"HTTP {status}")
            log.warning(
                "push.send_failed",
                subscription_id=subscription.id,
                status=status,
                error=str(exc)[:200],
            )
            return SendResult(SendOutcome.FAILED, f"HTTP {status}: {str(exc)[:200]}")
        except Exception as exc:
            # 네트워크 오류 등. 다음 주기에 다시 시도한다.
            log.warning("push.send_error", subscription_id=subscription.id, error=str(exc)[:200])
            return SendResult(SendOutcome.FAILED, str(exc)[:200])

        return SendResult(SendOutcome.SENT)
