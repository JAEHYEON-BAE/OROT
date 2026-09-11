"""운영자 알림 (T-116).

로그는 아무도 보지 않는다. 여기서 고정하는 것은 **알림이 쓸모를 잃지 않는 조건**이다 —
너무 자주 오면 사람이 꺼 버리고, 전송이 실패하면 발송까지 멈춰서는 안 된다.
"""

from datetime import UTC, datetime, timedelta

import pytest

from vinyl_core.alerts import ALERT_COOLDOWN, Alert, NullAlertSender, ThrottledAlerts

NOW = datetime(2026, 10, 1, 5, 0, tzinfo=UTC)


class _Recorder:
    def __init__(self, *, ok: bool = True) -> None:
        self.sent: list[Alert] = []
        self._ok = ok

    async def send(self, alert: Alert) -> bool:
        self.sent.append(alert)
        return self._ok


class _Exploding:
    async def send(self, alert: Alert) -> bool:
        raise RuntimeError("웹훅이 죽었다")


def _alert(key: str = "k") -> Alert:
    return Alert(key=key, title="제목", detail="내용")


@pytest.mark.asyncio
async def test_same_alert_is_suppressed_during_cooldown() -> None:
    """스케줄러는 60초마다 돈다.

    억제가 없으면 한 번 고장난 것이 **분당 한 통**씩 나가 채널이 묻히고,
    그러면 사람이 알림을 꺼 버린다 — 알림이 없는 것과 같아진다.
    """
    recorder = _Recorder()
    alerts = ThrottledAlerts(recorder)

    assert await alerts.send(_alert(), now=NOW)
    assert not await alerts.send(_alert(), now=NOW + timedelta(seconds=60))
    assert len(recorder.sent) == 1


@pytest.mark.asyncio
async def test_alert_resumes_after_cooldown() -> None:
    """영영 막으면 고장이 계속되는데도 조용해진다."""
    recorder = _Recorder()
    alerts = ThrottledAlerts(recorder)

    await alerts.send(_alert(), now=NOW)
    assert await alerts.send(_alert(), now=NOW + ALERT_COOLDOWN)
    assert len(recorder.sent) == 2


@pytest.mark.asyncio
async def test_different_keys_do_not_suppress_each_other() -> None:
    """스케줄러 실패와 재시도 소진은 다른 문제다. 하나가 다른 하나를 가리면 안 된다."""
    recorder = _Recorder()
    alerts = ThrottledAlerts(recorder)

    assert await alerts.send(_alert("scheduler.tick_failed"), now=NOW)
    assert await alerts.send(_alert("push.retry_exhausted"), now=NOW)
    assert len(recorder.sent) == 2


@pytest.mark.asyncio
async def test_failed_send_does_not_start_the_cooldown() -> None:
    """보내지 못한 것을 '보냈다'로 세면 그 문제는 쿨다운 동안 영영 묻힌다."""
    recorder = _Recorder(ok=False)
    alerts = ThrottledAlerts(recorder)

    assert not await alerts.send(_alert(), now=NOW)
    assert not await alerts.send(_alert(), now=NOW + timedelta(seconds=1))
    # 두 번 다 시도는 했다 — 억제된 것이 아니라 전송이 실패한 것이다.
    assert len(recorder.sent) == 2


@pytest.mark.asyncio
async def test_exploding_sender_never_reaches_the_caller() -> None:
    """**알림 전송 실패가 스케줄러를 멈추면 안 된다.**

    여기서 예외가 새면 알림을 못 보내는 데 그치지 않고 발송 자체가 죽는다.
    """
    alerts = ThrottledAlerts(_Exploding())
    assert not await alerts.send(_alert(), now=NOW)


@pytest.mark.asyncio
async def test_null_sender_is_not_an_error() -> None:
    """채널이 없어도 나머지는 정상 동작해야 한다 (푸시 키가 없을 때와 같은 판단)."""
    alerts = ThrottledAlerts(NullAlertSender())
    assert not await alerts.send(_alert(), now=NOW)
