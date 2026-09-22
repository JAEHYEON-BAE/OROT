# 즉시 수정 대상 점검 — 2026-09-15 14:58 KST

작업 트리 `ac9272e` (2026-09-15) 기준으로 코드·테스트·CI·호스트 운영 상태를 점검했다.
**자동 수집(M3)은 이번 범위에서 제외한다** — 착수를 미루기로 했으므로, M3 착수 조건은
[블루프린트 §10](BLUEPRINT.ko.md)과 [ADR-0005](adr/0005-manual-curation-first.md)를 그대로 둔다.

선행 점검 문서와의 관계: [실행 점검(2026-09-10)](runtime-review.md)과
[보안 점검(2026-09-10)](security-review.md)은 **코드 경로의 버그**를 다뤘고 그 항목들은
수정되어 있다. 이 문서는 그 이후 드러난 **운영·검증 체계의 구멍**을 다룬다.

> 이 점검에서 컨테이너를 기동하거나 DB를 변경하거나 알림을 발송하지 않았다.
> `.env` 와 평문 `original.env` 는 열지 않았고 파일 시각만 확인했다.

---

## 우선순위 요약

| # | 문제 | 심각도 | 지금 손해 | 규모가 커지면 |
|---|---|---|---|---|
| 1 | 스택이 중단됐고 아무도 모른다 | **P0** | 알림 전면 중단 | 48시간 넘으면 영구 누락 |
| 2 | 자동 백업이 3일째 산출물 없음 | **P0** | 복구 지점 없음 | VAPID 분실 = 전 구독 무효 |
| 3 | 평문 `.env` 사본이 디스크에 남아 있음 | **P0** | 암호화 정책 무력화 | — |
| 4 | 발송 루프가 단일 트랜잭션 안 순차 HTTP | P1 | 없음 | 구독 200명부터 tick 초과 |
| 5 | production API 가 `--reload` + 소스 마운트 | P1 | 사고 유발 가능 | 무중단 배포 불가 |
| 6 | 테스트가 실제 DB 를 쓰지 않음 | P2 | 수동 검증 의존 | 마이그레이션 드리프트 무음 |
| 7 | CI 에 모바일 검사 없음 | P2 | 회귀 수동 발견 | — |
| 8 | 아티스트 조회 N+1 | P2 | 무시 가능 | 피드 1회당 +50 쿼리 |
| 9 | 커밋 규약 미준수 | P3 | 이력 추적 불가 | — |
| 10 | 저장소 위생·문서 드리프트 | P3 | 혼선 | — |

---

## P0-1. 스택이 중단됐고 그 사실을 알리는 경로가 없다

### 현상

```
$ colima status
FATA[0000] colima is not running
```

[`backups/launchd-stack.log`](../backups/launchd-stack.log) 마지막 기록:

```
[2026-09-15 10:39:43] healthz 200 — 기동 완료
[2026-09-15 11:30:40] colima 가 꺼져 있습니다 — 기동합니다
level=fatal msg="errors inspecting instance: [vz driver is running but host agent is not]"
level=fatal msg="error starting vm: error at 'starting': exit status 1"
```

`launchctl list` 기준 `com.orot.stack` 의 마지막 종료 상태는 `1` 이다.
10:39 에 정상 기동했다가 11:30 에 재기동을 시도해 실패했고, 그 뒤로 3시간 넘게 내려가 있다.

### 왜 아무도 몰랐나

세 겹이 동시에 비어 있다.

1. `com.orot.stack.plist` 가 `KeepAlive false` — **한 번 실패하면 재시도하지 않는다.**
   `RunAtLoad` 뿐이라 다음 로그인/부팅까지 기다린다
2. `restart: unless-stopped` 는 colima 가 살아 있을 때만 의미가 있다.
   VM 자체가 죽으면 compose 의 재시작 정책이 닿지 않는다 —
   [`infra/orot-start.sh`](../infra/orot-start.sh) 주석이 이미 그렇게 적어 뒀다
3. **Slack 운영자 알림(T-116)은 스케줄러 tick 안에서 나간다.**
   collector 가 안 돌면 알림도 안 나간다. 알림 체계가 자기 자신의 죽음은 알릴 수 없다

### 영향

`MAX_NOTIFY_AGE = 48시간` ([`notifications.py`](../packages/core/src/orot_core/notifications.py)).
스택이 이틀 넘게 꺼져 있으면 그 사이 발생했어야 할 이벤트는 다시 켜도 `EXPIRED` 로
만료되어 **영영 발송되지 않는다.** `MAX_BACKFILL = 7일` 은 이벤트 *생성* 상한이지
발송 상한이 아니다.

"예약 시작을 놓치지 않게 한다"가 이 제품의 유일한 약속인데, 그 약속을 깨는 경로가
호스트 VM 한 줄짜리 오류라는 점이 구조적 문제다.

### 수정

1. **복구** — `colima start && make prod`. `vz driver is running but host agent is not` 이
   반복되면 colima 인스턴스 재생성이 필요할 수 있는데, **`colima delete` 는 볼륨이
   걸린 동작이므로 `make backup` 이 성공한 뒤에만** 판단한다 (CLAUDE.md §2 규칙 10)
2. **재시도** — `com.orot.stack.plist` 에 `KeepAlive` 를 조건부로 준다.
   `SuccessfulExit false` 로 두면 실패 시에만 재시작하고, `ThrottleInterval` 로 간격을 둔다.
   지금처럼 성공 후에도 계속 재실행되면 안 되므로 `KeepAlive true` 는 쓰지 않는다
3. **감시** — 스택 *바깥*에서 `http://127.0.0.1:8000/healthz` 를 주기적으로 확인하고
   실패 시 Slack 으로 미는 launchd 잡 하나. 스택 안에 두면 같이 죽어 무의미하다.
   **알림 경로를 새로 만드는 것이 아니라 [`slack_alerter.py`](../apps/collector/src/orot_collector/slack_alerter.py)
   를 재사용**하되, collector 프로세스에 의존하지 않는 위치에 둔다

> 감수 — 감시 잡도 같은 맥에서 돈다. 맥 자체가 꺼지면 이것도 같이 꺼진다.
> 그 경우까지 덮으려면 외부 uptime 감시가 필요하고, 그건 이 단계에서 과설계다.
> **여기서 막으려는 것은 "맥은 켜져 있는데 스택만 죽은" 경우**이며, 오늘 일어난 것이 그것이다.

---

## P0-2. 자동 백업이 3일째 산출물을 남기지 못했다

### 현상

| 항목 | 마지막 산출물 | 경과 |
|---|---|---|
| DB 덤프 | `vinyl_radar-20260912-113331.sql.gz` (09-12 11:33) | **3일** |
| `.env` 암호화 백업 | `env-20260910-120640.env.enc` (09-10 12:06) | **5일** |
| 자동 백업 로그 | 09-10 11:40 두 줄 | **5일** |

결정적인 근거: `make backup` 은 덤프 파일 이름을 `$(POSTGRES_DB)-<타임스탬프>.sql.gz`
로 짓는다. 2026-09-12 의 rename 이후 DB 이름은 `orot` 이므로 성공한 백업은
`orot-*.sql.gz` 여야 하는데, **`backups/` 에 그 이름의 파일이 0개다.**
즉 rename 이후 성공한 DB 백업이 한 건도 없다.

`.env` 는 09-12 18:03 에 수정됐고 암호화 백업은 09-10 것이다. **현재 `.env` 는
어디에도 백업되어 있지 않다.**

### 왜 조용했나

[`infra/orot-backup.sh`](../infra/orot-backup.sh) 의 첫 가드가 이렇다.

```bash
if ! docker compose ps --status running --services 2>/dev/null | grep -qx postgres; then
  log "postgres 가 떠 있지 않습니다 — 백업을 건너뜁니다"
  exit 0
fi
```

**건너뛰기가 `exit 0`** 이라 launchd 에게는 성공으로 보인다.
`launchctl list` 의 `com.orot.backup` 종료 상태도 `0` 이다.

다만 이 경로를 탔다면 로그에 건너뛰기 줄이 남아야 하는데 남아 있지 않다. 두 가능성이 있다.

- 04:00 에 맥이 꺼져 있거나 잠들어 있어 **잡이 실행되지 않았다**
- 실행됐으나 `docker compose` 자체가 없어 다른 지점에서 조용히 끝났다

**어느 쪽이든 결과는 같다** — 3~5일간 백업이 없고, 그 사실을 알려 주는 것이 없다.
`make backup` 자체는 pipefail 로 실패를 잡도록 잘 만들어져 있지만
(빈 파일을 남기지 않는다), **"실행되지 않음"은 실패로 세지 않는다.**

### 수정

1. **지금 당장** — 스택 복구 후 `make backup` 과 `make backup-env` 를 수동 실행한다.
   `make backup-env` 는 내용이 안 바뀌었으면 건너뛰므로, `.env` 가 바뀐 지금은 새 파일이 생긴다
2. **건너뛰기를 성공으로 세지 않는다** — 스크립트에 "마지막 성공 시각"을 파일로 남기고,
   그 값이 N시간을 넘으면 Slack 으로 민다. 넘어가는 것 자체는 정당하지만
   (스택이 내려간 동안 백업을 시도할 이유가 없다), **넘어간 채로 며칠이 지나는 것**은 다르다
3. **디스크 밖으로** — 현재 모든 백업이 `backups/` 에 있다. DB 와 같은 디스크다.
   T-120 의 완료 조건 "`.env` 암호화 백업이 디스크 밖에" 는 충족되지 않았다.
   최소한 `.env.enc` 한 부는 외부 저장소에 둔다

> `make backup-env-setup` 이 이미 경고한 그대로다 — **키체인도 이 디스크에 있다.**
> 디스크가 죽으면 암호도 함께 사라지므로 암호는 비밀번호 관리자에도 있어야 한다.

---

## P0-3. 평문 `.env` 사본이 디스크에 남아 있다

### 현상

```
backups/orot-env-migration-20260912-175532/
  database.dump       49004  (09-12 17:55)
  original.env         2932  (09-12 17:55)   ← 평문
  verification.json      693
```

09-12 rename 마이그레이션의 롤백용 산출물이다. 권한은 `600` 이고 `backups/` 는
`.gitignore` 에 있어 **커밋되지는 않았다.** 하지만 `.env` 를 암호화해 백업하는
정책을 둔 이유가 "이 디스크를 누가 복사해 가도 안전하도록" 인데, 같은 디렉터리에
평문 사본이 있으면 그 정책이 상쇄된다.

내용에는 운영자 키·VAPID 개인키·DB 암호·Slack 웹훅이 들어 있다 (열어 보지 않았고,
`.env` 의 구조로 판단한 것이다). CLAUDE.md 가 기록해 둔 대로 **웹훅 URL 자체가 비밀**이고,
VAPID 개인키가 새면 제3자가 우리 구독자에게 알림을 보낼 수 있다.

### 수정

순서를 지킨다.

1. `make backup-env` — 현재 `.env` 를 암호화해 백업한다 (P0-2 와 같은 동작)
2. `make backups-env` 로 새 `.env.enc` 가 생겼는지 확인한다
3. 그 다음에 `original.env` 를 지운다. rename 롤백이 아직 필요하다면
   `database.dump` 는 남기고 `original.env` 만 지운다 —
   **롤백에 필요한 것은 DB 이지 평문 키가 아니다**

> 되돌릴 수 없는 삭제이므로 1·2 를 건너뛰지 않는다.

---

## P1-4. 발송 루프가 단일 트랜잭션 안에서 순차 HTTP 를 돈다

### 현상

[`scheduler.py`](../apps/collector/src/orot_collector/scheduler.py) 의 `tick()` 은
하나의 `session_scope()` 안에서 advisory lock 을 잡고 `dispatch_pending()` 을 호출한다.
[`notifications.py`](../packages/core/src/orot_core/notifications.py) 의 발송 루프는
최대 `MAX_BATCH = 500` 건을 **순차로** `await sender.send(...)` 한다
(`REQUEST_TIMEOUT = 10초`).

### 영향

| 상황 | 결과 |
|---|---|
| 구독 200명 × 건당 300ms | 60초 tick 초과 → 다음 tick 은 advisory lock 에 막혀 skip |
| 전원 타임아웃 (500건 × 10초) | **트랜잭션이 80분 열린 채** 유지 |
| 루프 중간 프로세스 종료 | 이미 성공한 `SENT` 기록까지 전부 롤백 → 다음 주기에 **배치 전체 중복 발송** |
| 정원(`MAX_ACTIVE_SUBSCRIPTIONS = 10,000`) 도달 | 이벤트 1건 배포에 20 tick = **20분** |

세 번째가 특히 중요하다. 기존 문서는 "exactly-once 를 보장하지 않는다"고 적어 뒀는데,
**그 중복 규모가 1~2건이 아니라 배치 전체**라는 점은 어디에도 적혀 있지 않다.

네 번째는 `PREORDER_OPEN` 이 시각 민감하다는 제품 목표와 정면으로 충돌한다.

### 수정

지금 구독자 수에서는 아무 문제가 없다. **공개를 넓히기 전에** 손본다.

1. **발송을 트랜잭션 밖으로** — 보낼 대상을 뽑아 커밋하고, 전송 후 결과를 건별(또는 소배치)로
   커밋한다. 중단 시 롤백 범위가 1건으로 줄어든다
2. **제한적 병렬화** — `asyncio.Semaphore` 로 동시 실행을 묶어 `gather`.
   푸시 서비스별 상한을 넘지 않는 선에서
3. **시각 민감 이벤트 우선** — 현재 `plan_deliveries` 는 `occurred_at` 오름차순이라
   밀린 과거 이벤트가 방금 열린 예약보다 먼저 배치를 차지한다

> 어느 것도 `UNIQUE (event_id, device_token_id)` 불변식을 건드리지 않는다.
> 그 제약이 멱등성의 근거이므로 유지한다.

---

## P1-5. production API 가 `--reload` 와 소스 마운트를 유지한다

[`compose.prod.yaml`](../compose.prod.yaml) 은 `api` 서비스의 `ENVIRONMENT` 만 바꾼다.
`compose.yaml` 의 `command` 에 있는 `--reload` 와 소스 볼륨 마운트는 그대로 남고,
`WATCHFILES_FORCE_POLLING=true` 기본값 때문에 상시 폴링이 돈다.

결과: **호스트에서 `.py` 파일 하나를 저장하면 운영 중인 API 가 즉시 재시작된다.**
편집 중인 반쪽짜리 코드가 그대로 반영될 수 있다.

웹은 `volumes: !reset []` 로 정확히 이 문제를 막아 뒀는데 API 만 예외다.
[보안 점검 문서](security-review.md)도 이 점을 "남은 한계"로 적어 뒀다.

### 수정

`compose.prod.yaml` 의 `api` 에 `command` 오버라이드(`--reload` 없이)와
`volumes: !reset []` 를 추가한다. 웹과 같은 모양이 된다.

> 감수 — 그 뒤로는 API 수정도 `make prod` 재빌드가 필요하다.
> 지금은 collector 만 재기동이 필요하고 API 는 자동 반영되는데, **그 편의가
> 곧 위험의 원인**이므로 일관되게 맞추는 편이 낫다.

---

## P2-6. 테스트 467개가 실제 DB 를 한 번도 쓰지 않는다

Python 427개가 **1.03초**에 끝난다. API 테스트는 `SimpleNamespace` 와 `AsyncMock` 으로
세션을 흉내 낸다. [`test_unified_feed.py`](../apps/api/tests/test_unified_feed.py) 의
한 테스트는 생성된 **SQL 문자열을 `assert`** 한다.

실제 PostgreSQL 을 쓰는 것은 [`integration_runtime.py`](../apps/api/tests/integration_runtime.py)
하나뿐이고, 이것은 `Base.metadata` 로 **자기 스키마를 직접 만든다** — 마이그레이션이
만든 스키마를 검증하지 않는다.

### 못 잡는 것

- **마이그레이션 ↔ ORM 드리프트.** CI 는 `alembic upgrade head` 가 에러 없이 끝나는지만 본다.
  모델에만 컬럼을 추가하면 **CI 는 통과하고 운영에서만 깨진다**
- CHECK 제약의 실제 동작, `listing_events` 삭제 시 CASCADE 경로, keyset 커서,
  `DISTINCT ON`, `with_for_update(skip_locked=True)` 경합

지금은 새 필드를 추가할 때마다 사람이 격리 스키마 검증을 돌려 메우고 있다
([일정 모드 검증 기록](admin-schedule-modes.ko.md)이 그 예다). **사람이 기억해야 하는 방식**이다.

### 수정

가장 싼 것부터.

1. **`alembic check` 를 CI 에 추가** — 마이그레이션 적용 후 autogenerate 차이가 0인지 본다.
   한 줄이고, 드리프트를 전부 잡는다
2. `integration_runtime.py` 를 **마이그레이션이 만든 스키마 위에서** 돌리도록 바꾼다
   (지금은 롤백을 위해 자체 스키마를 쓰는데, 트랜잭션 롤백만으로도 격리는 유지된다)
3. SQL 문자열을 `assert` 하는 테스트는 실제 정렬 결과를 보는 쪽으로 옮긴다

---

## P2-7. CI 에 모바일 검사가 없다

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) 에는 `python` 과 `web` 두 잡뿐이다.
`apps/mobile` 에는 `npm run check`(lint + typecheck + jest)가 있고 실제로 통과한다
(5 suites / 16 tests). 블루프린트는 "T-012 에 모바일 검사를 확장한다"를 계획으로만 적어 뒀다.

**특히 위험한 지점**: 모바일 타입은 `docs/api/openapi.json` 에서 생성된다.
API 스키마를 바꾸고 `make openapi` 를 빠뜨리면 모바일이 조용히 낡은 타입을 쓴다.
CI 가 `npm run generate:api` 후 diff 가 없는지 확인하면 이것도 함께 잡힌다.

---

## P2-8. 아티스트 조회 N+1

[`serializers.py`](../apps/api/src/orot_api/serializers.py) 의 `release_to_out()` 이
발매 1건마다 `session.get(Artist, ...)` 를 호출한다. `Release` 에 `primary_artist`
relationship 이 없어 `selectinload` 를 쓸 수 없다.

피드 50건이면 최대 50회 추가 쿼리다. 같은 세션의 identity map 덕분에 아티스트가
겹치면 재사용되므로 실제 부담은 더 적다. **현재 규모에서는 무해**하지만,
relationship 하나 추가하고 `selectinload` 를 붙이면 끝나는 일이다.

같은 경로가 [`admin.py`](../apps/api/src/orot_api/routers/admin.py) 의 `_to_out()` 에도 있다.

---

## P3-9. 커밋 규약이 지켜지지 않고 있다

CLAUDE.md §4 는 `<type>(<scope>): <T-ID> <summary>` 를 요구한다.
**9개 커밋 중 이 형식을 따른 것이 0개다.**

```
ac9272e mobile app UI theme (260915_1441)
ca7a982 Mobile App with Mock Data (260913_1728)
c4aa5b2 260913_1318
```

실무적 손해가 이미 났다. **일정 모드(`schedule_status`/`until_sold_out`) 작업 전체가
"mobile app UI theme" 커밋 안에 묻혀 있다.** 나중에 "이 CHECK 제약이 왜 생겼는지"를
`git log` 로 추적할 방법이 없고, 되돌릴 단위도 하루 전체다.

수정: 앞으로의 커밋부터 규약을 따른다. 과거 이력은 건드리지 않는다
(되쓰기가 주는 이득보다 위험이 크다).

---

## P3-10. 저장소 위생과 문서 드리프트

### 커밋된 잡동사니

```
._CLAUDE.md, docs/._BLUEPRINT.ko.md, docs/._.mv_preview.html   (macOS AppleDouble)
.mv_preview.html (87KB), docs/.mv_preview.html
.playwright-mcp/*.yml  (8개, 2026-09-10 브라우저 검증 산출물)
```

`.gitignore` 에 `._*`, `.mv_preview.html`, `.playwright-mcp/` 를 추가하고
`git rm --cached` 한다.

### 문서가 코드보다 뒤처진 지점

| 위치 | 내용 |
|---|---|
| `CLAUDE.md §7` | 기준일이 2026-09-11 — 일정 모드(09-14)와 모바일 테마(09-15)가 없다 |
| [`feed_query.py`](../apps/api/src/orot_api/feed_query.py) 도입부 | `tag = release-<id>` 라고 설명한다. T-131 에서 `release-<id>-<event_type>` 로 바뀌었다 |
| [블루프린트 §10](BLUEPRINT.ko.md) | 일정 모드 작업의 태스크 행이 없다 |

두 번째가 단순 오타보다 나쁘다. 그 주석은 "폰에는 이미 마지막 하나만 남아 있으므로
피드도 하나만 보여 준다"는 **논리의 근거**로 쓰이는데, T-131 이후 그 전제가 성립하지 않는다.
결론(피드는 발매당 한 줄)은 여전히 옳지만 **이유가 틀렸다** — 다음 사람이 이 주석을 믿고
판단하면 잘못된 결론에 도달한다.

블루프린트를 고칠 때는 **ko/en 두 판을 같은 커밋에서** 갱신한다 (CLAUDE.md §2 규칙 9).

---

## 수정 순서

| 순서 | 항목 | 이유 |
|---|---|---|
| 1 | P0-1 복구 (`colima start && make prod`) | 서비스가 멈춰 있다 |
| 2 | P0-2 수동 백업 (`make backup`, `make backup-env`) | 복구 지점이 없다 |
| 3 | P0-3 평문 `.env` 정리 | 2 가 끝난 뒤에만 |
| 4 | P0-1 재시도·감시 | 같은 일이 반복된다 |
| 5 | P0-2 백업 실패 감지 + 외부 1부 | 침묵하는 실패를 없앤다 |
| 6 | P2-6 `alembic check` CI 추가 | 한 줄로 큰 구멍을 막는다 |
| 7 | P1-5 production `--reload` 제거 | 사고 경로를 닫는다 |
| 8 | P1-4 발송 루프 분리 | **공개 확대 전** |
| 9 | P2-7 / P2-8 / P3 항목 | 여유가 생길 때 |

1~3 은 한 번에 이어서 하고, 4~5 는 같은 작업으로 묶는 편이 낫다.

---

## 확인한 범위와 한계

이번 점검에서 실행한 것:

```
make lint     ruff check / format / mypy(전체) / mypy --strict(core)   전부 통과
make test     427 passed, 2 xfailed (1.03초)
apps/web      node --test tests/*.test.mjs → 24 passed, ESLint 통과
apps/mobile   jest → 5 suites / 16 tests passed
git status    clean (ac9272e)
colima status / launchctl list / 로그·파일 시각 확인 (읽기만)
```

실행하지 않은 것과 그 의미:

- **컨테이너를 기동하지 않았다.** 따라서 런타임 동작은 코드와 설정으로 판단한 것이며,
  실제 실행 결과로 확인한 것이 아니다
- **DB 를 조회하지 않았다.** 현재 등록된 일정 수, 활성 구독 수, 대기 중인 배송은 모른다.
  P0-1 의 실제 누락 규모는 스택 복구 후 `notification_deliveries` 를 봐야 알 수 있다
- **`.env` 와 `original.env` 를 열지 않았다.** P0-3 의 내용 추정은 `.env.example`
  과 `settings.py` 의 필드 구성에 근거한 것이다
- **알림을 발송하지 않았고 DB 를 변경하지 않았다**
- P1-4 의 처리량 수치는 코드의 상수(`MAX_BATCH`, `REQUEST_TIMEOUT`, `TICK_SECONDS`)에서
  계산한 것이며 **부하 측정 결과가 아니다.** 실제 건당 지연은 푸시 서비스에 달려 있다

이 목록이 "남은 문제 전부"라는 뜻은 아니다. 현재 활성 실행 경로에서 재현 가능하거나
파일로 확인 가능한 것까지를 담았다.

---

## 후속 검토

이 문서의 진단을 현재 코드·호스트 상태와 대조한 판단, 수정 사항 및 미완료 항목은
[후속 검토와 조치](issue-review-20260915-resolution.md)에 기록한다.
특히 “실제 DB 검증이 전혀 없다”, “alembic check가 모든 드리프트를 잡는다”,
“현재 환경 백업 후 과거 원본을 바로 삭제해도 된다”는 설명은 후속 문서의 정정을 따른다.
