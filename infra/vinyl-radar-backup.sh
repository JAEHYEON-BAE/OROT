#!/bin/bash
# 자동 백업 (T-120). launchd 가 하루 한 번 부른다.
#
# **볼륨은 실수 삭제만 막는다** — 디스크 고장이나 잘못된 마이그레이션은 막지 못한다.
# 그래서 덤프를 따로 남긴다. 오래된 것은 30개만 유지한다.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$PROJECT_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

if ! docker compose ps --status running --services 2>/dev/null | grep -qx postgres; then
  log "postgres 가 떠 있지 않습니다 — 백업을 건너뜁니다"
  exit 0
fi

make backup
make backup-prune
