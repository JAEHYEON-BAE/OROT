"""운영자 알림 (T-116).

**로그는 아무도 보지 않는다.** 발송이 조용히 실패하면 사용자는 알림이 안 오는 줄도
모르고, 운영자는 컨테이너 로그를 뒤져야 안다. 이 제품의 유일한 약속이 "놓치지 않게"
이므로, 그 약속이 깨진 것을 **밖으로 밀어내는 경로**가 하나는 있어야 한다.

발송(`PushSender`)과 같은 구조를 쓴다 — 프로토콜은 여기 두고 실제 HTTP 는 collector 가
구현한다. `packages/core` 는 collector 를 임포트할 수 없다 (의존 방향).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol

import structlog

log = structlog.get_logger(__name__)

# 같은 종류의 알림을 다시 보내기까지 기다리는 시간. `None` 이면 **다시 보내지 않는다.**
#
# 스케줄러는 60초마다 돈다. 억제가 없으면 한 번 고장난 것이 **분당 한 통**씩 나가
# 채널이 묻히고, 그러면 사람이 알림을 꺼 버린다 — 알림이 없는 것과 같아진다.
#
# 기본값이 `None` 인 이유: Slack 메시지는 지워지지 않고 쌓이므로, 같은 문제를 다시
# 알려도 새로운 정보가 없다. **감수하는 것** — 문제가 해결됐다가 나중에 다시
# 생겨도 (프로세스가 살아 있는 한) 알리지 않는다. 그게 신경 쓰이면
# `timedelta(hours=24)` 처럼 긴 값을 주면 된다.
ALERT_COOLDOWN: Final[timedelta | None] = None


@dataclass(frozen=True, slots=True)
class Alert:
    """운영자에게 보낼 한 건."""

    key: str
    """같은 종류를 묶는 식별자. 쿨다운은 이 값 기준으로 적용된다."""
    title: str
    detail: str


class AlertSender(Protocol):
    """실제 전송 수단. Slack 구현은 collector 에 있다."""

    async def send(self, alert: Alert) -> bool: ...


class NullAlertSender:
    """알림 채널이 설정되지 않았을 때.

    **오류가 아니다.** 채널이 없어도 나머지는 정상 동작해야 한다 —
    푸시 키가 없을 때 푸시만 꺼지는 것과 같은 판단이다.
    """

    async def send(self, alert: Alert) -> bool:
        log.info("alert.dropped", key=alert.key, title=alert.title)
        return False


class ThrottledAlerts:
    """같은 `key` 의 알림을 한 번만 내보낸다 (쿨다운이 있으면 그 간격으로).

    상태는 프로세스 메모리에 있다. 스케줄러가 재기동하면 억제가 풀려 한 번 더 나가는데,
    **그 편이 낫다** — 재기동 직후는 무언가 잘못됐을 가능성이 높은 시점이다.
    다만 크래시 루프에서는 재기동마다 나가므로, 그것이 문제가 되면 억제 기록을
    DB 로 옮겨야 한다 (다중 인스턴스에서도 같은 문제가 생긴다).
    """

    def __init__(self, sender: AlertSender, *, cooldown: timedelta | None = ALERT_COOLDOWN) -> None:
        self._sender = sender
        self._cooldown = cooldown
        self._last: dict[str, datetime] = {}

    async def send(self, alert: Alert, *, now: datetime | None = None) -> bool:
        moment = now or datetime.now(UTC)
        previous = self._last.get(alert.key)
        if previous is not None and (self._cooldown is None or moment - previous < self._cooldown):
            return False

        try:
            delivered = await self._sender.send(alert)
        except Exception as exc:
            # **알림 전송 실패가 스케줄러를 멈추면 안 된다.** 여기서 터지면
            # 알림을 못 보내는 데 그치지 않고 발송 자체가 죽는다.
            log.warning("alert.send_failed", key=alert.key, error=type(exc).__name__)
            return False

        if delivered:
            self._last[alert.key] = moment
        return delivered
