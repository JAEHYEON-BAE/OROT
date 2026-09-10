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
from vinyl_core.db import get_engine, session_scope
from vinyl_core.logging import configure_logging
from vinyl_core.notifications import PushSender, dispatch_pending
from vinyl_core.schedule_events import generate_due_events
from vinyl_core.settings import get_settings

from vinyl_collector.push_sender import WebPushSender

log = structlog.get_logger(__name__)

# §1.3 의 "알림 발송 시각 오차 ±1분" 을 만족시키는 최소 해상도.
TICK_SECONDS: Final = 60

# 두 번이 겹쳐 돌면 같은 이벤트를 두 번 만들 수 있다.
# 생성 로직 자체가 멱등하긴 하지만, 겹치지 않게 두는 편이 로그가 읽기 쉽다.
MAX_INSTANCES: Final = 1


async def tick(sender: PushSender | None = None) -> None:
    """한 번의 검사. 실패해도 스케줄러를 멈추지 않는다.

    두 단계다 — **이벤트를 만들고, 만들어진 것을 보낸다.**
    두 단계 모두 멱등하므로 중간에 죽어도 다음 주기가 이어받는다.
    """
    started = datetime.now(UTC)
    settings = get_settings()
    push = sender if sender is not None else WebPushSender()

    try:
        async with session_scope() as session:
            events = await generate_due_events(session, now=started)
            dispatch = await dispatch_pending(
                session, push, base_url=settings.public_web_url, now=started
            )
    except Exception:
        # 예외를 삼키지 않는다 (CLAUDE.md §2 규칙 5). 다만 여기서 죽으면
        # 이후 모든 알림이 멈추므로, 로그를 남기고 다음 주기를 기다린다.
        log.exception("scheduler.tick_failed")
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
        elapsed_ms=round(elapsed * 1000),
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
