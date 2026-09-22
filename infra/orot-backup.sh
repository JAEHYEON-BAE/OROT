#!/bin/bash
# DB and env backups report independent success; no silent skip or pruning.
set -euo pipefail
umask 077
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$PROJECT_DIR"
mkdir -p backups/status
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
result=0
if make backup; then
  date +%s > backups/status/db.ok.tmp
  mv backups/status/db.ok.tmp backups/status/db.ok
else
  log "DB 백업 실패 — 마지막 성공 시각을 유지합니다"
  result=1
fi
if infra/env-backup.sh; then
  shasum -a 256 .env | awk '{print $1}' > backups/status/env.sha256.tmp
  mv backups/status/env.sha256.tmp backups/status/env.sha256
  date +%s > backups/status/env.ok.tmp
  mv backups/status/env.ok.tmp backups/status/env.ok
else
  log "환경 백업 실패 — 키체인 접근과 목적지를 확인하십시오"
  result=1
fi
exit "$result"
