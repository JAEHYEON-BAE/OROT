#!/bin/bash
# .env 암호화 백업 (T-120).
#
# **왜 필요한가.** `make backup` 은 DB 만 덤프한다. 그런데 그 DB 를 쓸모 있게 만드는
# 것은 `.env` 안의 VAPID 개인키다 — 디스크가 죽어 이 키를 잃으면 **이미 등록된 푸시
# 구독이 전부 무효**가 된다. 구독은 키 쌍에 묶여 있어 새 키로는 발송되지 않고,
# 사용자는 알림이 끊긴 것을 알아채지 못한 채 다시 구독하지도 않는다.
#
# **왜 암호화하는가.** 이 파일은 디스크 밖(iCloud·외장 디스크)에 두어야 의미가 있고,
# 그러면 평문으로 둘 수 없다. AES-256 + PBKDF2 로 감싼다.
#
# **암호는 어디에 있는가.** 자동 실행을 위해 맥 키체인에서 읽는다. 다만 키체인도
# 같은 디스크에 있으므로, **복구용 암호는 반드시 비밀번호 관리자에도 따로** 두어야
# 한다. 키체인은 무인 실행을 위한 것이지 복구 수단이 아니다.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# An existing installation may retain its original keychain identity.
KEYCHAIN_SERVICE="${ENV_BACKUP_KEYCHAIN_SERVICE:-$(sed -n 's/^ENV_BACKUP_KEYCHAIN_SERVICE=//p' .env 2>/dev/null | tail -1)}"
KEYCHAIN_SERVICE="${KEYCHAIN_SERVICE:-orot-env-backup}"
SOURCE="${ENV_FILE:-.env}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { echo "!! $*" >&2; exit 1; }

[ -f "$SOURCE" ] || die "$SOURCE 가 없습니다."

# .env 에서 값 하나를 읽는다.
#
# **`source .env` 를 쓰지 않는다.** compose 형식의 .env 는 따옴표 없이 공백을 담을 수
# 있고(iCloud 경로의 "Mobile Documents"), 셸로 해석하면 그 자리에서 깨진다.
# 첫 '=' 뒤를 끝까지 값으로 본다.
env_value() {
  sed -n "s/^$1=//p" "$SOURCE" | tail -1 | sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
}

# 셸 환경변수가 .env 보다 우선한다 — 시험이나 일회성 덮어쓰기를 위해서다.
DEST="${ENV_BACKUP_DIR:-$(env_value ENV_BACKUP_DIR)}"
DEST="${DEST:-backups/env}"
KEEP="${ENV_BACKUP_KEEP:-$(env_value ENV_BACKUP_KEEP)}"
KEEP="${KEEP:-10}"

# `~/...` 로 적었을 때도 동작하게 한다. .env 는 셸이 해석하지 않으므로 직접 편다.
case "$DEST" in "~/"*) DEST="$HOME/${DEST#\~/}" ;; esac

# 암호 해결 순서: 환경변수(시험용) → 키체인 → 실패
resolve_passphrase() {
  if [ -n "${ENV_BACKUP_PASSPHRASE:-}" ]; then
    printf '%s' "$ENV_BACKUP_PASSPHRASE"; return 0
  fi
  security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null && return 0
  die "암호를 찾지 못했습니다. 'make backup-env-setup' 을 먼저 실행하십시오."
}

# 다른 곳(Makefile 등)이 같은 규칙으로 경로를 다시 구현하지 않도록,
# 해석 결과를 물어볼 수 있게 한다.
if [ "${1:-}" = "--where" ]; then
  printf '%s\n' "$DEST"; exit 0
fi

mkdir -p "$DEST"

# 같은 디스크에 두면 디스크 고장에 대비가 되지 않는다. 동작은 시키되 분명히 알린다.
case "$(cd "$DEST" && pwd)" in
  "$PROJECT_DIR"/*|"$PROJECT_DIR")
    log "경고: 백업 위치가 프로젝트 안($DEST)입니다 — 디스크가 죽으면 함께 사라집니다."
    log "      .env 의 ENV_BACKUP_DIR 을 iCloud Drive 등 디스크 밖으로 지정하십시오."
    ;;
esac

newest="$(ls -1t "$DEST"/*.env.enc 2>/dev/null | head -1 || true)"
if [ -n "$newest" ] && [ ! "$SOURCE" -nt "$newest" ]; then
  log "$SOURCE 가 마지막 백업 이후 바뀌지 않았습니다 — 건너뜁니다 ($(basename "$newest"))"
  exit 0
fi

out="$DEST/env-$(date +%Y%m%d-%H%M%S).env.enc"
# -pass fd:3 — 명령행이나 환경변수로 넘기면 프로세스 목록에 노출될 수 있다.
if ! resolve_passphrase | openssl enc -aes-256-cbc -pbkdf2 -iter 600000 -md sha512 \
       -salt -in "$SOURCE" -out "$out" -pass fd:0; then
  rm -f "$out"; die "암호화에 실패했습니다."
fi
chmod 600 "$out"
[ -s "$out" ] || { rm -f "$out"; die "백업이 비어 있습니다."; }

log "저장됨: $out ($(du -h "$out" | cut -f1))"

# 오래된 것 정리. 작은 파일이라 넉넉히 남긴다.
ls -1t "$DEST"/*.env.enc 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r f; do
  log "삭제: $(basename "$f")"; rm -f "$f"
done
