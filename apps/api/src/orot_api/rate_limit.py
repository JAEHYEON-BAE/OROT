"""쓰기 경로 속도 제한 (T-130).

**클라이언트 IP 로 셀 수 없다.** Tailscale Funnel 은 원 IP 를 보존하지 않아 모든
요청이 로컬 프록시에서 온 것으로 보인다. 그래서 IP 별이 아니라 **전역**으로 센다.
정밀하지는 않지만 막으려는 것은 "한 명이 수만 건을 밀어 넣는 것"이므로 충분하다.

상태를 프로세스 안에만 둔다. API 컨테이너가 하나인 지금은 정확하고, 여러 개로
늘리면 공유 저장소가 필요해진다 — **그 시점에 이 주석이 근거가 된다.**
"""

import time
from typing import Final

# 분당 새 구독 등록 상한. 기기 하나가 평생 몇 번 부르는 요청이라 넉넉한 값이다.
SUBSCRIBE_PER_MINUTE: Final = 60

# 활성 구독 총량 상한. 넘으면 새 구독을 받지 않는다 —
# **기존 구독자의 알림은 계속 나간다.** 폭주가 서비스 자체를 멈추면 안 된다.
MAX_ACTIVE_SUBSCRIPTIONS: Final = 10_000

WINDOW_SECONDS: Final = 60.0


class FixedWindowLimiter:
    """고정 창 카운터.

    토큰 버킷보다 거칠어서 창 경계에서 최대 2배까지 통과할 수 있다.
    여기서 필요한 정밀도는 그 정도로 충분하고, 대신 상태가 정수 둘뿐이다.
    """

    def __init__(self, limit: int, window_seconds: float = WINDOW_SECONDS) -> None:
        self._limit = limit
        self._window = window_seconds
        self._started = time.monotonic()
        self._count = 0

    def allow(self) -> bool:
        """한 건을 허용할 수 있으면 세고 True 를 돌려준다."""
        now = time.monotonic()
        if now - self._started >= self._window:
            self._started = now
            self._count = 0
        if self._count >= self._limit:
            return False
        self._count += 1
        return True

    @property
    def retry_after(self) -> int:
        """다음 창까지 남은 초. `Retry-After` 헤더에 넣는다."""
        remaining = self._window - (time.monotonic() - self._started)
        return max(1, int(remaining) + 1)


subscribe_limiter = FixedWindowLimiter(SUBSCRIBE_PER_MINUTE)
