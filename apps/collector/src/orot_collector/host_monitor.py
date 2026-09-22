"""Host-side checks independent of Docker; notification requires explicit --notify.

Only fixed loopback health endpoints are requested. State contains incident keys,
never settings, endpoints, credentials or exception text.
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from orot_core.alerts import Alert, AlertSender

from orot_collector.slack_alerter import SlackAlerter

MAX_BACKUP_AGE = 36 * 3600
PROJECT = Path(__file__).resolve().parents[4]


def stale(path: Path, now: float) -> bool:
    try:
        stamp = float(path.read_text().strip())
    except (OSError, ValueError):
        return True
    return not 0 <= now - stamp <= MAX_BACKUP_AGE


def backup_issues(project: Path, now: float) -> set[str]:
    issues: set[str] = set()
    values = dotenv_values(project / ".env")
    status = project / "backups/status"
    db_name = values.get("POSTGRES_DB") or "orot"
    dumps = list((project / "backups").glob(f"{db_name}-*.sql.gz"))
    if stale(status / "db.ok", now) or not any(p.stat().st_size > 0 for p in dumps):
        issues.add("host.backup_db_stale")
    env_dest = Path(values.get("ENV_BACKUP_DIR") or "backups/env").expanduser()
    if not env_dest.is_absolute():
        env_dest = project / env_dest
    copies = list(env_dest.glob("*.env.enc"))
    env_file = project / ".env"
    try:
        verified_hash = (status / "env.sha256").read_text().strip()
        matches = verified_hash == hashlib.sha256(env_file.read_bytes()).hexdigest()
    except OSError:
        matches = False
    if (
        stale(status / "env.ok", now)
        or not matches
        or not any(p.stat().st_size > 0 for p in copies)
    ):
        issues.add("host.backup_env_stale")
    return issues


async def health_issues(project: Path) -> set[str]:
    issues: set[str] = set()
    values = dotenv_values(project / ".env")
    async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
        for name, key, default, suffix in (
            ("api", "API_HOST_PORT", "8000", "/healthz"),
            ("web", "WEB_HOST_PORT", "3000", "/api/mobile/v1/feed"),
        ):
            try:
                port = int(values.get(key) or default)
                response = await client.get(f"http://127.0.0.1:{port}{suffix}")
                if response.status_code != 200:
                    issues.add(f"host.{name}_down")
            except (httpx.HTTPError, ValueError):
                issues.add(f"host.{name}_down")
    try:
        check = await asyncio.to_thread(
            subprocess.run,
            ["docker", "inspect", "--format", "{{.State.Running}}", "orot-collector-1"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if check.returncode or check.stdout.strip() != b"true":
            issues.add("host.collector_down")
    except (OSError, subprocess.TimeoutExpired):
        issues.add("host.collector_down")
    return issues


async def report_incidents(issues: set[str], state_file: Path, sender: AlertSender) -> None:
    """Persist only successfully sent incidents; clear recovered ones for recurrence."""
    try:
        saved = json.loads(await asyncio.to_thread(state_file.read_text))
        previous = set(saved) if isinstance(saved, list) else set()
    except (OSError, ValueError):
        previous = set()
    active = previous & issues
    for key in sorted(issues - previous):
        if await sender.send(
            Alert(
                key=key,
                title="호스트 상태 확인 필요",
                detail=f"`{key}` 감지. 서비스 상태와 `backups/launchd-*.log`를 확인하십시오.",
            )
        ):
            active.add(key)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(sorted(active)))
    temporary.chmod(0o600)
    temporary.replace(state_file)


async def check(*, notify: bool) -> int:
    now = time.time()
    issues = backup_issues(PROJECT, now) | await health_issues(PROJECT)
    print(json.dumps({"issues": sorted(issues), "notify": notify}))
    if notify:
        await report_incidents(issues, PROJECT / "backups/status/incidents.json", SlackAlerter())
    return int(bool(issues))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--notify", action="store_true", help="Send incident alerts to configured Slack"
    )
    args = parser.parse_args()
    os.chdir(PROJECT)
    raise SystemExit(asyncio.run(check(notify=args.notify)))


if __name__ == "__main__":
    main()
