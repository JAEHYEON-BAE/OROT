#!/bin/bash
# 암호화된 .env 백업을 복구한다 (T-120).
#
# **기존 .env 를 덮어쓴다** (CLAUDE.md §2 규칙 10). 그래서 세 가지를 지킨다.
#   1) 먼저 임시 파일로 풀어 본다 — 암호가 틀리면 기존 파일을 건드리지 않는다
#   2) 덮어쓰기 전에 현재 .env 를 .env.bak-<시각> 으로 남긴다
#   3) 확인을 받는다 (FORCE=1 로 건너뛸 수 있다)
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# An existing installation may retain its original keychain identity.
KEYCHAIN_SERVICE="${ENV_BACKUP_KEYCHAIN_SERVICE:-$(sed -n 's/^ENV_BACKUP_KEYCHAIN_SERVICE=//p' .env 2>/dev/null | tail -1)}"
KEYCHAIN_SERVICE="${KEYCHAIN_SERVICE:-orot-env-backup}"
TARGET="${ENV_FILE:-.env}"
FILE="${1:-}"

die() { echo "!! $*" >&2; exit 1; }

[ -n "$FILE" ] || die "사용법: infra/env-restore.sh <백업파일.env.enc>"
[ -f "$FILE" ] || die "$FILE 을 찾을 수 없습니다."

resolve_passphrase() {
  if [ -n "${ENV_BACKUP_PASSPHRASE:-}" ]; then printf '%s' "$ENV_BACKUP_PASSPHRASE"; return 0; fi
  security find-generic-password -s "$KEYCHAIN_SERVICE" -w 2>/dev/null && return 0
  die "암호를 찾지 못했습니다. 키체인에 없다면 ENV_BACKUP_PASSPHRASE 로 넘기십시오."
}

tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
# 먼저 풀어 본다. 암호가 틀리면 여기서 끝나고 기존 .env 는 그대로다.
resolve_passphrase | openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -md sha512 \
  -in "$FILE" -out "$tmp" -pass fd:0 2>/dev/null \
  || die "복호화에 실패했습니다 (암호가 다르거나 파일이 손상되었습니다). $TARGET 은 그대로입니다."

grep -q "^DATABASE_URL=" "$tmp" || die "복호화 결과가 .env 형식이 아닙니다. $TARGET 은 그대로입니다."

echo "복구 대상 : $TARGET"
echo "백업 파일 : $FILE"
echo "포함된 키 : $(grep -cE '^[A-Z_]+=' "$tmp")개"
if [ "${FORCE:-0}" != "1" ]; then
  printf "기존 %s 를 덮어씁니다. 계속하시겠습니까? [y/N] " "$TARGET"
  read -r answer
  case "$answer" in [yY]*) ;; *) echo "취소했습니다."; exit 1 ;; esac
fi

if [ -f "$TARGET" ]; then
  keep="$TARGET.bak-$(date +%Y%m%d-%H%M%S)"
  cp "$TARGET" "$keep"; chmod 600 "$keep"
  echo "기존 파일 보관: $keep"
fi

cp "$tmp" "$TARGET"; chmod 600 "$TARGET"
echo "복구 완료: $TARGET"
echo "컨테이너에 반영하려면 'make prod' (또는 'make up') 를 다시 실행하십시오."
