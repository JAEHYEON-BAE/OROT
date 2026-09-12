"""운영자 알림 (T-116).

로그는 아무도 보지 않는다. 여기서 고정하는 것은 **알림이 쓸모를 잃지 않는 조건**이다 —
너무 자주 오면 사람이 꺼 버리고, 전송이 실패하면 발송까지 멈춰서는 안 된다.
"""

import pathlib
from datetime import UTC, datetime, timedelta

import pytest

from orot_core.alerts import ALERT_COOLDOWN, Alert, NullAlertSender, ThrottledAlerts

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
    alerts = ThrottledAlerts(recorder, cooldown=timedelta(minutes=15))

    assert await alerts.send(_alert(), now=NOW)
    assert not await alerts.send(_alert(), now=NOW + timedelta(seconds=60))
    assert len(recorder.sent) == 1


@pytest.mark.asyncio
async def test_default_never_repeats_the_same_alert() -> None:
    """기본값은 **다시 보내지 않는 것**이다.

    Slack 메시지는 지워지지 않고 쌓이므로, 같은 문제를 다시 알려도 새로운 정보가 없다.
    감수하는 것 — 문제가 해결됐다가 다시 생겨도 (프로세스가 사는 한) 알리지 않는다.
    """
    assert ALERT_COOLDOWN is None

    recorder = _Recorder()
    alerts = ThrottledAlerts(recorder)

    assert await alerts.send(_alert(), now=NOW)
    assert not await alerts.send(_alert(), now=NOW + timedelta(days=30))
    assert len(recorder.sent) == 1


@pytest.mark.asyncio
async def test_cooldown_can_be_configured_to_repeat() -> None:
    """반복이 필요하면 간격을 주면 된다 — 그 경로가 살아 있어야 한다."""
    recorder = _Recorder()
    alerts = ThrottledAlerts(recorder, cooldown=timedelta(hours=24))

    await alerts.send(_alert(), now=NOW)
    assert not await alerts.send(_alert(), now=NOW + timedelta(hours=23))
    assert await alerts.send(_alert(), now=NOW + timedelta(hours=24))
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


def test_message_templates_have_the_placeholders_the_code_fills() -> None:
    """문구는 사람이 직접 고치는 곳이다 (T-116).

    `{이름}` 을 지우거나 오타를 내면 **알림이 필요한 바로 그 순간에 `KeyError`** 가 난다.
    여기서 미리 잡는다.
    """
    from orot_collector import scheduler as s

    assert s.TICK_FAILED_DETAIL.format(exception="RuntimeError")
    assert "2" in s.EXHAUSTED_TITLE.format(count=2)
    assert s.EXHAUSTED_DETAIL.format(attempts=3)


def test_routine_churn_is_not_alerted() -> None:
    """구독 해제는 알리지 않는다.

    사용자가 앱을 지우거나 알림을 끈 것이라 운영자가 할 일이 없고,
    **사용자가 늘수록 늘어나기만 한다.**

    정말 위험한 경우(VAPID 키 불일치)는 푸시 서비스가 403 을 주고, 403 은
    `GONE`(404/410)이 아니라 `FAILED` 라서 `exhausted` 알림이 담당한다.
    """
    from orot_collector import scheduler as s

    assert not hasattr(s, "DEACTIVATED_TITLE")
    source = pathlib.Path(s.__file__).read_text(encoding="utf-8")
    assert "push.subscriptions_deactivated" not in source
    # 수치 자체는 로그에 남아 있어야 한다 — 필요할 때 셀 수 있도록.
    assert "deactivated=dispatch.deactivated" in source
