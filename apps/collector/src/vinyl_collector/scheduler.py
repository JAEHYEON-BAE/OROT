"""상주 스케줄러 (T-111, 블루프린트 §2.1).

지금 하는 일은 하나다 — **1분마다 `preorder_opens_at` 을 살펴 이벤트를 만든다.**
자동 수집(M3)이 붙으면 소스별 크롤 잡이 여기에 추가된다.

> 주기를 1분으로 잡은 이유: §1.3 의 "알림 발송 시각 오차 ±1분" 을 만족하려면
> 그보다 촘촘할 이유도, 느슨할 여지도 없다. 일정 수가 적어 부하는 무시할 만하다.
"""

import asyncio
import signal
from datetime import UTC, datetime
from typing import Final

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text
from vinyl_core.alerts import Alert, AlertSender, NullAlertSender, ThrottledAlerts
from vinyl_core.db import get_engine, session_scope
from vinyl_core.logging import configure_logging
from vinyl_core.notifications import (
    MAX_ATTEMPTS,
    DispatchResult,
    PushSender,
    dispatch_pending,
)
from vinyl_core.schedule_events import generate_due_events
from vinyl_core.settings import get_settings

from vinyl_collector.push_sender import WebPushSender
from vinyl_collector.slack_alerter import SlackAlerter

log = structlog.get_logger(__name__)

# §1.3 의 "알림 발송 시각 오차 ±1분" 을 만족시키는 최소 해상도.
TICK_SECONDS: Final = 60

# 두 번이 겹쳐 돌면 같은 이벤트를 두 번 만들 수 있다.
# 생성 로직 자체가 멱등하긴 하지만, 겹치지 않게 두는 편이 로그가 읽기 쉽다.
MAX_INSTANCES: Final = 1

# 억제 상태는 주기 간에 유지되어야 한다 — 매번 새로 만들면 억제가 동작하지 않는다.
_alerts: ThrottledAlerts | None = None


async def tick(sender: PushSender | None = None, alerts: ThrottledAlerts | None = None) -> None:
    """한 번의 검사. 실패해도 스케줄러를 멈추지 않는다.

    두 단계다 — **이벤트를 만들고, 만들어진 것을 보낸다.**
    두 단계 모두 멱등하므로 중간에 죽어도 다음 주기가 이어받는다.
    """
    started = datetime.now(UTC)
    settings = get_settings()
    push = sender if sender is not None else WebPushSender()
    alerter = alerts if alerts is not None else _default_alerts()

    try:
        async with session_scope() as session:
            # Serialize overlapping collector processes, not just jobs in one process.
            if not await session.scalar(text("SELECT pg_try_advisory_xact_lock(86170421)")):
                log.info("scheduler.already_running")
                return
            events = await generate_due_events(session, now=started)
            dispatch = await dispatch_pending(
                session, push, base_url=settings.public_web_url, now=started
            )
    except Exception as exc:
        # 예외를 삼키지 않는다 (CLAUDE.md §2 규칙 5). 다만 여기서 죽으면
        # 이후 모든 알림이 멈추므로, 로그를 남기고 다음 주기를 기다린다.
        #
        # **여기가 가장 위험한 실패다** (T-116). 알림이 통째로 멈추는데
        # 사용자도 운영자도 알 방법이 없다 — 그래서 반드시 밖으로 밀어낸다.
        log.exception("scheduler.tick_failed")
        await alerter.send(
            Alert(
                key="scheduler.tick_failed",
                title="스케줄러 주기가 실패했습니다",
                detail=(
                    f"예외: `{type(exc).__name__}`\n"
                    "이 상태가 계속되면 *모든 알림이 멈춥니다.* "
                    "`docker compose logs collector` 를 확인하십시오."
                ),
            ),
            now=started,
        )
        return

    elapsed = (datetime.now(UTC) - started).total_seconds()
    log.info(
        "scheduler.tick",
        created=events.total,
        soon=events.preorder_opens_soon,
        opened=events.preorder_open,
        released=events.released,
        sent=dispatch.sent,
        failed=dispatch.failed,
        expired=dispatch.expired,
        exhausted=dispatch.exhausted,
        deactivated=dispatch.deactivated,
        elapsed_ms=round(elapsed * 1000),
    )
    await _report(alerter, dispatch, now=started)


def _default_alerts() -> ThrottledAlerts:
    """억제 상태를 주기 간에 유지하려면 한 번만 만들어 재사용해야 한다."""
    global _alerts
    if _alerts is None:
        settings = get_settings()
        sender: AlertSender = SlackAlerter() if settings.alerts_enabled else NullAlertSender()
        _alerts = ThrottledAlerts(sender)
    return _alerts


async def _report(alerts: ThrottledAlerts, dispatch: DispatchResult, *, now: datetime) -> None:
    """주기 결과에서 **사람이 손대야 하는 것만** 골라 알린다 (T-116).

    실패(`failed`)는 알리지 않는다 — 다음 주기에 다시 시도하므로 대개 저절로 낫는다.
    매번 알리면 채널이 묻히고, 그러면 사람이 알림을 꺼 버린다. 알림이 없는 것과 같아진다.
    """
    if dispatch.exhausted:
        await alerts.send(
            Alert(
                key="push.retry_exhausted",
                title=f"알림 {dispatch.exhausted}건이 끝내 전달되지 않았습니다",
                detail=(
                    f"재시도 {MAX_ATTEMPTS}회를 모두 쓰고 실패했습니다. "
                    "해당 구독자는 이 알림을 받지 못합니다.\n"
                    "`notification_deliveries` 에서 `status='FAILED'` 인 행의 "
                    "`last_error` 를 확인하십시오."
                ),
            ),
            now=now,
        )

    if dispatch.deactivated:
        # 정상적인 이탈이다. 다만 한꺼번에 많이 꺼지면 우리 쪽 설정 문제일 수 있다.
        await alerts.send(
            Alert(
                key="push.subscriptions_deactivated",
                title=f"구독 {dispatch.deactivated}건이 만료되어 해제되었습니다",
                detail=(
                    "푸시 서비스가 404/410 을 돌려준 구독입니다. "
                    "사용자가 앱을 지웠거나 알림을 껐을 때 정상적으로 일어납니다.\n"
                    "한 번에 여러 건이 꺼졌다면 VAPID 키나 발송 설정을 확인하십시오."
                ),
            ),
            now=now,
        )


async def run() -> None:
    """스케줄러를 띄우고 종료 신호를 받을 때까지 기다린다."""
    configure_logging()
    settings = get_settings()

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        tick,
        trigger=IntervalTrigger(seconds=TICK_SECONDS),
        id="schedule_events",
        max_instances=MAX_INSTANCES,
        coalesce=True,  # 밀린 실행은 하나로 합친다 — 따라잡기는 tick 안에서 한다
        # 기동 직후 한 번 돌려, 꺼져 있는 동안 지난 일정을 즉시 따라잡는다.
        next_run_time=datetime.now(UTC),
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    scheduler.start()
    log.info(
        "scheduler.started",
        environment=settings.environment,
        tick_seconds=TICK_SECONDS,
    )
    try:
        await stop.wait()
    finally:
        scheduler.shutdown(wait=True)
        await get_engine().dispose()
        log.info("scheduler.stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
