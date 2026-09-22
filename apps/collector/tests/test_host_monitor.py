import json
from pathlib import Path

import pytest
from orot_core.alerts import Alert

from orot_collector.host_monitor import MAX_BACKUP_AGE, backup_issues, report_incidents, stale


class Sender:
    def __init__(self, success=True):
        self.keys = []
        self.success = success

    async def send(self, alert: Alert) -> bool:
        self.keys.append(alert.key)
        return self.success


def test_stale_missing_invalid_and_future(tmp_path: Path):
    marker = tmp_path / "db.ok"
    assert stale(marker, 100)
    for value in ("bad", "101", str(-MAX_BACKUP_AGE)):
        marker.write_text(value)
        assert stale(marker, 100)
    marker.write_text("99")
    assert not stale(marker, 100)


def test_missing_artifacts_are_not_success(tmp_path: Path):
    (tmp_path / ".env").write_text("POSTGRES_DB=orot\n")
    status = tmp_path / "backups/status"
    status.mkdir(parents=True)
    for kind in ("db", "env"):
        (status / f"{kind}.ok").write_text("99")
    assert backup_issues(tmp_path, 100) == {"host.backup_db_stale", "host.backup_env_stale"}


@pytest.mark.asyncio
async def test_incident_suppression_recovery_and_failed_send(tmp_path: Path):
    state = tmp_path / "incidents.json"
    sender = Sender()
    await report_incidents({"host.api_down"}, state, sender)
    await report_incidents({"host.api_down"}, state, sender)
    assert len(sender.keys) == 1
    await report_incidents(set(), state, sender)
    await report_incidents({"host.api_down"}, state, sender)
    assert len(sender.keys) == 2
    failed = Sender(False)
    await report_incidents({"host.web_down"}, state, failed)
    assert json.loads(state.read_text()) == []
    await report_incidents({"host.web_down"}, state, failed)
    assert len(failed.keys) == 2
