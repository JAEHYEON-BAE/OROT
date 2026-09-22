"""Run host scripts against disposable files and fake host commands only."""

import os
import shutil
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]


def command(path: Path, script: str):
    path.write_text("#!/bin/bash\n" + script)
    path.chmod(0o700)


def test_start_success_and_health_failure(tmp_path: Path):
    infra = tmp_path / "infra"
    infra.mkdir()
    binaries = tmp_path / "bin"
    binaries.mkdir()
    source = (PROJECT / "infra/orot-start.sh").read_text()
    source = source.replace(
        'export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"',
        f'export PATH="{binaries}:/usr/bin:/bin"',
    )
    script = infra / "orot-start.sh"
    script.write_text(source)
    for name in ("colima", "docker", "sleep"):
        command(binaries / name, "exit 0\n")
    command(binaries / "curl", "exit 0\n")
    assert subprocess.run(["bash", str(script)], capture_output=True).returncode == 0
    command(binaries / "curl", "exit 1\n")
    assert subprocess.run(["bash", str(script)], capture_output=True).returncode == 1


def test_db_failure_still_attempts_env_and_does_not_advance_db_marker(tmp_path: Path):
    infra = tmp_path / "infra"
    infra.mkdir()
    binaries = tmp_path / "bin"
    binaries.mkdir()
    source = (
        (PROJECT / "infra/orot-backup.sh")
        .read_text()
        .replace(
            'export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"',
            f'export PATH="{binaries}:/usr/bin:/bin"',
        )
    )
    script = infra / "orot-backup.sh"
    script.write_text(source)
    command(binaries / "make", "exit 1\n")
    command(infra / "env-backup.sh", "exit 0\n")
    (tmp_path / ".env").write_text("DATABASE_URL=synthetic-test-only\n")
    status = tmp_path / "backups/status"
    status.mkdir(parents=True)
    (status / "db.ok").write_text("1")
    assert subprocess.run(["bash", str(script)], capture_output=True).returncode == 1
    assert (status / "db.ok").read_text() == "1"
    assert int((status / "env.ok").read_text()) > 1


def test_encrypted_backup_verifies_contents_not_mtime(tmp_path: Path):
    infra = tmp_path / "infra"
    infra.mkdir()
    script = infra / "env-backup.sh"
    shutil.copyfile(PROJECT / "infra/env-backup.sh", script)
    source = tmp_path / ".env"
    source.write_text("DATABASE_URL=first-test-value\n")
    dest = tmp_path / "encrypted"
    env = {
        **os.environ,
        "ENV_FILE": str(source),
        "ENV_BACKUP_DIR": str(dest),
        "ENV_BACKUP_PASSPHRASE": "synthetic-test-only",
        "ENV_BACKUP_KEYCHAIN_SERVICE": "unused-test-only",
    }
    for _ in range(2):
        result = subprocess.run(["bash", str(script)], env=env, capture_output=True)
        assert result.returncode == 0, result.stderr.decode()
    assert len(list(dest.glob("*.env.enc"))) == 1
    source.write_text("DATABASE_URL=changed-test-value\n")
    os.utime(source, (1, 1))  # Old mtime must not hide changed content.
    assert subprocess.run(["bash", str(script)], env=env, capture_output=True).returncode == 0
    assert len(list(dest.glob("*.env.enc"))) == 2
