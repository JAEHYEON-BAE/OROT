#!/bin/bash
# 재부팅 후 스택을 되살린다 (T-120).
#
# colima 는 사용자 세션에서 도는 VM 이라 systemd 같은 게 없다. 그래서
#   1) colima 가 떠 있는지 확인하고, 없으면 띄운다
#   2) 그 위에 compose 스택을 상시 운영 모드로 올린다
# 두 단계를 순서대로 한다. compose 의 `restart: unless-stopped` 는 **colima 가
# 살아 있을 때만** 동작하므로, colima 자체를 되살리는 것이 이 스크립트의 핵심이다.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$PROJECT_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

if ! colima status >/dev/null 2>&1; then
  log "colima 가 꺼져 있습니다 — 기동합니다"
  colima start
else
  log "colima 는 이미 떠 있습니다"
fi

log "스택을 상시 운영 모드로 올립니다"
docker compose -f compose.yaml -f compose.prod.yaml up -d

# 헬스체크가 통과할 때까지 기다린다. 실패해도 launchd 를 죽이지 않는다 —
# 여기서 비정상 종료하면 launchd 가 반복 재시작을 시도해 로그만 쌓인다.
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${API_HOST_PORT:-8000}/healthz"; then
    log "healthz 200 — 기동 완료"
    exit 0
  fi
  sleep 2
done
log "healthz 가 200 을 반환하지 않았습니다 (컨테이너는 계속 재시도합니다)"
