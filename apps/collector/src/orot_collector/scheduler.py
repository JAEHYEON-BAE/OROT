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
from orot_core.alerts import Alert, AlertSender, NullAlertSender, ThrottledAlerts
from orot_core.db import get_engine, session_scope
from orot_core.logging import configure_logging
from orot_core.notifications import (
    MAX_ATTEMPTS,
    DispatchResult,
    PushSender,
    dispatch_pending,
)
from orot_core.schedule_events import generate_due_events
from orot_core.settings import get_settings
from sqlalchemy import text

from orot_collector.push_sender import WebPushSender
from orot_collector.slack_alerter import SlackAlerter

log = structlog.get_logger(__name__)

# §1.3 의 "알림 발송 시각 오차 ±1분" 을 만족시키는 최소 해상도.
TICK_SECONDS: Final = 60

# 두 번이 겹쳐 돌면 같은 이벤트를 두 번 만들 수 있다.
# 생성 로직 자체가 멱등하긴 하지만, 겹치지 않게 두는 편이 로그가 읽기 쉽다.
MAX_INSTANCES: Final = 1

# 억제 상태는 주기 간에 유지되어야 한다 — 매번 새로 만들면 억제가 동작하지 않는다.
_alerts: ThrottledAlerts | None = None


# ─── 알림 문구 (T-116) ──────────────────────────────────────────
#
# **문구를 바꾸려면 여기만 고치면 된다.** 로직을 건드릴 필요가 없도록 한곳에 모았다.
# `{이름}` 자리는 아래 코드가 채운다 — 이름을 바꾸거나 지우면 `KeyError` 가 난다.
# Slack 마크다운이라 `*굵게*`, `_기울임_`, `` `코드` ``, `<!channel>` 을 쓸 수 있다.
#
# 메시지를 감싸는 형식(제목 접두사, 블록 구조)은 `slack_alerter.py` 에 있다.

TICK_FAILED_TITLE = "스케줄러 주기 실패"
TICK_FAILED_DETAIL = (
    "예외: `{exception}`\n*모든 알림 중단*`docker compose logs collector` 를 확인하십시오."
)

EXHAUSTED_TITLE = "알림 {count}건이 전달 실패"
EXHAUSTED_DETAIL = (
    "재시도 {attempts}회 모두 실패.\n"
    "`notification_deliveries` 에서 `status='FAILED'` 인 행의 `last_error` 를 확인하십시오."
)


async def tick(sender: PushSender | None = None, alerts: ThrottledAlerts | None = None) -> None:
    """스케줄러 주기 검사.

    1단계: 이벤트 생성
    2단계: 이벤트 송신
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
                title=TICK_FAILED_TITLE,
                detail=TICK_FAILED_DETAIL.format(exception=type(exc).__name__),
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
    if dispatch.exhausted:
        await alerts.send(
            Alert(
                key="push.retry_exhausted",
                title=EXHAUSTED_TITLE.format(count=dispatch.exhausted),
                detail=EXHAUSTED_DETAIL.format(attempts=MAX_ATTEMPTS),
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
