# CLAUDE.md — OROT Agent Context

This file is loaded automatically by Claude Code at the start of every session. Read it fully before acting.

---

## 1. What this project is

OROT is a **release-schedule notification service** for Korean vinyl (LP) — not a sales database.
It gathers new-release and preorder schedules into one subscribable feed and notifies collectors
**at the moment preorders open**, so limited pressings are not missed.

**Phase 1 (current): the operator enters schedules manually.** Automated harvesting is built and tested
but deliberately unwired; it gets connected in M3 when manual entry becomes the bottleneck.
See [ADR-0005](docs/adr/0005-manual-curation-first.md).

**Not core**: per-shop price comparison, artist discography, exhaustive catalog harvesting.

**Full specification: `docs/BLUEPRINT.ko.md` (authoritative) and `docs/BLUEPRINT.en.md` (mirror).**
Read the blueprint before starting any task. Current source code, migrations and runtime configuration
are authoritative for implemented behavior; correct stale documentation to match them. The Korean
blueprint governs unresolved differences between the two language editions. Planned features do not
count as implemented behavior or authorize incidental implementation.

---

## 2. Non-negotiable rules

1. **For backlog work, use the existing `T-XXX` ID** from blueprint §10 and announce it. Complete that task before taking another. Bug fixes, reviews and documentation maintenance follow the user-authorized scope; do not invent task IDs.
2. **No live network requests in tests.** Adapter tests read HTML from `apps/collector/tests/fixtures/<source_id>/`. If a fixture is missing, stop and ask — do not fetch the site to generate one silently.
3. **Never violate the crawling rules in blueprint §3.4.** Specifically: honor robots.txt, cap at 0.5 req/s per source, identify the crawler in the User-Agent, store metadata only, never rehost images, never bypass CAPTCHAs or bot protection.
4. **Never write a merge that is not reversible.** Entity resolution only mutates `listings.release_id`. Never delete a `listings` row.
5. **Never swallow a parse exception.** `parse_page()` returns an empty list on failure and logs the source and URL. The CLI reports parse failures. Parser-specific external alerts and Prometheus counters are not implemented. Scheduler errors and push retry exhaustion have Slack alerts (ADR-0008); do not describe parser logs as alert delivery.
6. **Do not create top-level directories** that are not in blueprint §6.
7. **Activate `venv/` before running Python.** All Python commands run inside the project virtualenv (`source venv/bin/activate`, 또는 `make` 타깃 사용) or the collector container.
8. **Ask before deciding anything architectural** that the blueprint leaves open. Write a draft ADR in `docs/adr/NNNN-title.md` and request confirmation.
9. **Keep `BLUEPRINT.ko.md` and `BLUEPRINT.en.md` in sync.** If a task changes the spec, update both in the same commit.
10. **Never destroy data without explicit confirmation.** 다음은 **사용자에게 먼저 확인**받는다 —
    설명 없이 실행하지 않는다. "검증용 데이터 정리" 같은 이유로도 예외를 두지 않는다.
    - `docker compose down -v` / `docker volume rm` — **볼륨이 지워져 DB 가 사라진다**
    - `colima delete`, `docker system prune`
    - `WHERE` 절 없는 `DELETE` / `TRUNCATE` / `DROP TABLE`
    - `make restore` (기존 데이터를 덮어쓴다)

    검증 데이터를 정리할 때는 **자기가 만든 행만 골라 지운다.**
    ```sql
    -- Prefer an isolated schema and transaction rollback for tests.
    -- Shared-DB cleanup must use the exact IDs created by this test.
    -- Never select cleanup targets by title or a guessed ID range.
    -- SQL LIKE '__%' matches almost every title: underscores are wildcards.
    ```
    파괴적 작업 전에는 `make backup` 을 먼저 실행하는 편이 안전하다.

    > 이 규칙은 실제 사고에서 나왔다. 2026-08-20 검증 중 `docker compose down -v` 와
    > 전체 `DELETE` 를 반복 실행해 **사용자가 등록한 일정을 지웠고 복구할 수 없었다.**

---

## 3. Commands

```bash
make up          # start the local stack (postgres, api, collector, web)
make down
make migrate     # alembic upgrade head (production runs the image's copy — see below)
make seed        # seed sources only; artist aliases remain planned
make test        # pytest across packages/core, apps/api, apps/collector
make lint        # ruff check + ruff format --check + mypy
make openapi     # regenerate docs/api/openapi.json

# 백업 (파괴적 작업 전에 실행할 것)
make backup                            # backups/ 에 타임스탬프 덤프
make backups                           # 백업 목록
make restore FILE=backups/xxx.sql.gz   # 복구 — 기존 데이터를 덮어쓴다 (확인 프롬프트 있음)

# Collector CLI: dry-run makes live website requests; do not run it as an offline test.
docker compose exec collector collector run --source gimbab --dry-run --limit 5

# 운영자 알림 진단 — Slack 채널이 닿는지 확인 (DB 는 바꾸지 않는다)
docker compose exec collector collector test-alert

# 푸시 진단 — 실제 발송은 사용자 승인 범위에서만 실행 (DB 는 바꾸지 않는다)
docker compose exec collector collector test-push
docker compose exec collector collector test-push --dry-run   # 대상·페이로드만 출력

# 상시 운영 (웹 production 빌드 + ENVIRONMENT=production)
make prod                              # 재부팅 후 복구도 이 두 줄: colima start && make prod
make prod-down
make prod-logs

# .env 암호화 백업 — VAPID 키를 잃으면 **기존 구독이 전부 무효**가 된다
make backup-env-setup                  # 최초 1회, 암호를 키체인에 저장
make backup-env
make backups-env
make restore-env FILE=...

# 공개 테스트 주소: 아래 명령으로 현재 Funnel 설정 확인 (호스트 설정은 저장소 밖)
tailscale funnel status                # https://jaehyeonui-macmini.tail598a5f.ts.net
# PUBLIC_WEB_URL 은 api/collector/web 에 전달된다. .env 변경은 restart 가 아니라
# compose up -d 로 컨테이너를 재생성해야 반영된다.
```

For implementation changes, run `make lint && make test`. For web changes also run
`npm run lint`, `node --test tests/*.test.mjs`, and `npm run build` in `apps/web`.
For documentation-only changes, verify commands, paths, API contracts and both language editions;
do not start/rebuild services or send notifications just to validate prose.

---

## 4. Conventions

### Python
- Python 3.12, `ruff` for lint and format, `mypy --strict` on `packages/core`.
- Type hints on every public function. Pydantic v2 for boundary models, SQLAlchemy 2.0 (typed `Mapped[...]`) for ORM.
- Async by default in the collector and API. No blocking I/O inside async functions.
- Blueprint §6 distinguishes the current tree from reserved future paths. Verify actual files before citing a module.

### Naming
- Service/project name: **OROT**. Tool identifiers: `orot`; Python packages: `orot_*`.
- Feed UID/GUID namespace is `OROT` (owner-approved prelaunch change, 2026-09-12). Keep it stable going forward; active DB/backup identities were migrated to orot on 2026-09-12; retain rollback archives.
- `source_id` values are lowercase ASCII slugs: `gimbab`, `secondtrack`, `poclanos`.
- Database and JSON fields are `snake_case`. The current web client manually types the API subset it uses in `apps/web/lib/api.ts`. Keep those types aligned with API schemas; no Swift client exists yet.
- Fields suffixed `_raw` hold source text verbatim. **Never normalize in place;** normalized values live in `_norm` fields.

### Commits
```
<type>(<scope>): <T-ID> <summary>

feat(collector): T-014 implement Secondtrack adapter
fix(core): T-020 prevent merge across differing variants
docs(blueprint): T-006 record Gimbab robots.txt and selectors
```
Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`. Scopes: `core`, `collector`, `api`, `web`, `mobile`, `ios`, `infra`, `blueprint`.
Use an existing task ID for backlog work; maintenance commits may omit it. Do not rewrite past history merely to rename commit subjects.

### Generated code
- `make openapi` generates `docs/api/openapi.json` from FastAPI. Mobile generates types with `npm run generate:api` using openapi-typescript; HTTP calls and runtime validation are handwritten. Web types remain handwritten; CI checks generated mobile types and OpenAPI drift. Swift clients are not implemented.

---

## 5. Adding a new source (checklist)

Do these in order. Each step is part of the same task.

1. Write `docs/adapters/<source_id>.md` containing: robots.txt verbatim, relevant ToS clauses with your reading of them, listing URL and pagination pattern, whether JS rendering is required, a selector table for all eight fields, and whether JSON-LD / OpenGraph structured data is available.
2. Save ≥ 3 HTML fixtures under `apps/collector/tests/fixtures/<source_id>/` — one in-stock, one sold-out, one preorder.
3. Implement `packages/core/src/orot_core/adapters/<source_id>.py` against the `SourceAdapter` protocol. **Prefer structured data over CSS selectors when available.**
4. Write golden tests asserting every `RawItem` field for each fixture.
5. Add a row to the `sources` seed data.
6. A parser canary remains planned; `.github/workflows/parser-canary.yml` does not exist. Do not claim a new adapter is monitored automatically.

If the site requires login, blocks bots, or its ToS prohibits automated access: **stop, document the finding, and exclude the source.** Do not attempt to work around it.

---

## 6. Things that are easy to get wrong here

- **Variants are not duplicates.** A clear-vinyl pressing and a black pressing of the same album are different `release` rows. Merging them is a correctness bug, not a nicety.
- **Precision over recall in resolution.** When confidence is between 0.70 and 0.90, queue into `merge_candidates` and leave `release_id` NULL. Do not guess.
- **`PREORDER_OPEN` is time-critical as a product goal.** Current delivery uses the shared 60-second scheduler and a 500-item batch; there is no separate priority queue or daily digest.
- **`price_krw` is `NUMERIC(12,0)`.** Korean won has no minor unit; never introduce floats into price handling.
- **Timestamps are `TIMESTAMPTZ` and stored in UTC.** Source sites publish in KST; convert at parse time, never at display time in the database.
- **Fetcher validators are cached in process memory; content hashes are computed but not persisted or compared for skipping by the current CLI.** The live `--dry-run` path uses the fetcher; it bypasses DB writes, not network requests or crawling restrictions.

---

## 7. Current state

Reviewed against the working tree on **2026-09-15**. This describes implementation, not a guarantee
that host services are currently running. See [runtime review](docs/runtime-review.md) for the dated
2026-09-10 validation and [documentation review](docs/documentation-review.md) for reconciliation.

- **Schedule modes and mobile theme:** explicit TBA/ON_SALE/until-sold-out modes and `apps/mobile/theme.ts` are implemented. See the blueprints and `apps/mobile/THEME.md`.
- **M1 is implemented; M2 is active.** Operator-entered schedules, unified feed, calendar, RSS,
  iCalendar and anonymous Web Push are available. Automatic harvesting remains unwired until M3.
- **Public testing uses the Mac mini and Tailscale Funnel** at
  `https://jaehyeonui-macmini.tail598a5f.ts.net`. EC2/GHCR/SSH deployment is not implemented.
  The configured public URL comes from `PUBLIC_WEB_URL`; host tunnel/startup registrations must
  be verified separately rather than inferred from this file.
- **Execution:** `make up` starts development web; `make prod` overlays a built production web.
  Both bind API, web and PostgreSQL to loopback. Production API, collector and web use image
  source without mounts/reload; code changes require rebuild. Development retains source mounts.
  Environment changes require recreation.
- **Feed:** one row per published release; `recent` means `updated_at` descending (최근 변경순),
  `imminent` means future starts first, past starts next, unknown last (발매 임박순).
  The web displays preorder opening time, falling back to release date, and computes status from
  the current time. RSS contains the latest non-superseded event per published release instead.
- **Admin:** key-validated login UI; schedule and full link-list updates are atomic. Unpublished
  releases can be deleted even after prior publication, unless linked listings or other references
  block deletion. Release events and their deliveries are removed with an authorized deletion.
- **Notifications:** 60-second tick, session advisory lock across collectors, at most 500
  deliveries per dispatch, five concurrent sends, 45-second admission budget and three attempts per delivery.
  Planning and individual results commit separately; HTTP holds no DB transaction. Failed retries become eligible one and
  five minutes after creation. Cancelled, superseded, inactive or stale deliveries expire before send.
  Release dates use KST midnight. Tags are `release-<id>-<event_type>`.
- **T-116 완료:** 재시도 3회(1·5분), 404/410 시 구독 자동 비활성화, 그리고
  **Slack 운영자 알림**. 배송은 여전히 크래시 전후로 exactly-once 가 아니다.
- **Tests:** Python pytest + Ruff + source/test mypy + core strict; web Node tests + ESLint + Next build. Optional
  `apps/api/tests/integration_runtime.py` migrates its own PostgreSQL schema and rolls it back,
  using a fake sender. T-012 `.github/workflows/ci.yml` runs Python checks, disposable PostgreSQL
  migration/integration and drift checks, web checks and mobile checks on PR/main push/manual dispatch. No testcontainers
  dependency exists. GitHub run results and required-check settings are verified separately.
- **Preserve existing test/demo records and subscriptions.** Do not infer active counts, cleanup
  targets or deletion permission from old IDs in a document. Real `collector test-push` requires
  user authorization; `--dry-run` only reads targets and prints payloads.
- **Known deferred work:** normalization/aliases/resolution and crawl persistence; search,
  accounts/watchlists/native push and mobile distribution; parser canary, Prometheus/Sentry and external host/process outage monitoring.
- **Crawler limitations:** `urllib.robotparser` RFC 9309 gaps remain captured by two expected
  failures (ADR-0003); validators live only in memory; preorder/stock ambiguity is deferred
  (ADR-0001). Review these before wiring M3. Fixture/source findings are dated observations,
  not proof of current third-party site behavior.

- **Mobile T-033 (2026-09-13):** `apps/mobile` uses Expo SDK 55 and TypeScript
  with live feed/detail/settings, generated API types and fixed GET proxies through
  `/api/mobile/v1/*`. Funnel deployment and Simulator reads are verified. Physical
  iPhone, native push and distribution remain pending. See
  `docs/mobile-validation/T-033-live-api.ko.md`.

Update this section when implementation changes. Keep volatile DB state and host-specific registrations
out of enduring rules.

### 결정 기록

> 주제별로 묶은 요약이다. 각 결정의 **근거와 실측 데이터**는 해당 ADR 과
> 코드 주석에 있다 — 여기서는 "무엇을 왜 그렇게 했는가"만 남긴다.

#### 제품 방향

- **일정 알림 앱이지 판매 DB 가 아니다** ([ADR-0005](docs/adr/0005-manual-curation-first.md)).
  가격 비교·디스코그래피·카탈로그 전수 수집은 핵심이 아니다.
  **1단계는 운영자 수동 등록**, 자동 수집은 M3
- **자동 수집으로는 캘린더를 못 채운다**: 세 소스 모두 발매일을 구조적 필드로 주지 않고,
  **예약 마감 시각은 어느 소스도 노출하지 않는다.** 이것이 수동 우선의 실질적 이유다
- **알림은 시각 기반**이라 diff 엔진이 없다. 발송 누락은 추정 오류가 아니라 **버그**(목표 99%)
- **알림 채널은 Web Push 우선** ([ADR-0006](docs/adr/0006-web-push-first.md)).
  이메일은 만들지 않는다. APNs 는 폐기가 아니라 iOS 앱 배포 시점으로 미룸.
  감수 — **iOS 는 홈 화면 추가를 해야 알림 권한을 요청할 수 있다**
- **캘린더 구독과 푸시는 보완재**: 캘린더는 갱신 주기를 통제할 수 없어(구글 12~24시간)
  **당일 급히 등록된 일정과 시각 변경을 놓친다.** 그 공백이 이 제품이 놓치면 안 되는 경우다
- **인증 없는 배송 경로를 먼저 만든다** (RSS·iCalendar·Web Push).
  계정(M4)·푸시 인프라 없이 핵심 약속을 배송할 수 있다

#### 데이터 모델

- **수동 등록은 `releases` + `release_links`**. `listings` 는 크롤 산출물 전용 —
  `source_item_id`/`content_hash` 가 `NOT NULL` 이라 제약을 풀면 크롤 경로 불변식이 약해진다
- **`price_krw` 는 API 에서 `int`** — `NUMERIC(12,0)` 을 그대로 직렬화하면 Postgres 가
  `Decimal('5E+4')` 를 돌려주어 `"5E+4"` 가 응답에 나갔다
- **`event_type` 은 문자열로 다룬다** — 컬럼이 `Text` 라 ORM 이 `str` 로 준다.
  `EventType` 으로 가정하고 `.value` 를 부르면 런타임에 깨진다
- **푸시 구독에 계정이 필요 없다** (`device_tokens.user_id` NULL 허용).
  `token` 은 플랫폼마다 의미가 다르다 — `WEB` 이면 엔드포인트 URL, `IOS` 면 APNs 토큰
- **`UNIQUE (event_id, device_token_id)` 는 배송 행 중복을 막는다.**
  스케줄러 DB 잠금과 SENT 재처리 제외가 정상 실행의 중복을 줄인다. 외부 전송 성공과 DB 커밋
  사이의 중단/응답 유실은 재전송을 일으킬 수 있다. SENT 는 서비스 수락이지 기기 표시 확인이 아니다
- **다운그레이드에서 확장(pg_trgm 등)을 삭제하지 않는다** — DB 전역 객체다
- **Alembic 은 CHECK 제약의 *내용* 변경을 감지하지 못한다.** `event_type` 목록 확장은
  `drop_constraint` + `create_check_constraint` 를 직접 써야 했다.
  이때 이름은 명명 규칙이 접두사를 붙이므로 **짧은 이름**을 넘긴다

#### 불변식 (깨지면 correctness 버그)

- **`pywebpush` 는 동기 라이브러리다** — `asyncio.to_thread` 로 감싸지 않으면 스케줄러
  이벤트 루프를 막는다
- **404/410 은 실패가 아니라 "구독이 사라졌다"** — `GONE` 으로 구분해 구독을 끈다.
  죽은 구독에 매 주기 요청을 보내면 푸시 서비스가 우리를 차단할 수 있다

- **공개 API 의 최우선 필터는 `is_published`** — 초안이 새면 미공지 발매가 유출된다.
  상세는 404 로 응답한다(403 은 존재를 알려 준다)
- **공개·발송 멱등성은 `is_published` 가 아니라 이벤트 존재 여부로 판단한다.**
  공개 → 취소 → 재공개 시 같은 알림이 두 번 나갔다
- **삭제는 초안만. 공개 중이면 공개 취소를 먼저 거치게 한다** (T-133).
  원래는 "한 번도 공개된 적 없는" 것만 지울 수 있었다 — 발송 이력을 지키려는 규칙이었지만,
  그 결과 **운영자에게 남은 방법이 SQL 뿐**이 되었다. 여러 테이블을 손으로 순서대로 지우는
  쪽이 훨씬 위험하다(한 줄 틀리면 남의 데이터까지 지운다). **감수하는 것 — 그 발매에 대해
  무엇을 언제 보냈는지 기록이 사라진다.** `notification_deliveries` 는 `event_id` CASCADE 로 따라온다
- **`listing_events.release_id` 에는 CASCADE 가 없다** — 삭제 시 직접 지워야 한다.
  빠뜨리면 FK 위반으로 삭제 트랜잭션이 실패한다.
  `listings` 가 가리키고 있으면 삭제를 거절한다 (규칙 4 — listings 는 지우지 않는다)
- **세션은 응답 전에 커밋한다** (`Depends(get_session, scope="function")`, FastAPI ≥0.121).
  쓰기 경로는 `flush()` 로 오류를 조기에 확인하고, 커밋 실패도 성공으로 응답하지 않는다.
- **시드는 운영 상태를 덮어쓰지 않는다** (`is_enabled`/`disabled_reason`/`last_crawled_at`).
  차단 대응이 끈 소스를 `make seed` 가 다시 켜면 차단된 사이트를 계속 두드린다
- **백필 상한**: 이벤트 생성 7일, 발송 48시간. 서버가 오래 꺼져 있었다고 지난 알림을 쏟아내면 안 된다
- **구독 이전 이벤트는 보내지 않는다** — 새 구독자가 지난 알림을 한꺼번에 받으면 곧바로 끊는다

#### 수집 (M3 까지 잠들어 있음)

- **목록 페이지에서 수집한다** ([ADR-0004](docs/adr/0004-list-page-collection.md)).
  gimbab 은 목록이 `RawItem` 전 필드를 담아 **9,072회(5시간) → 756회(25분)**.
  프로토콜은 `parse_page(url, html) -> list[RawItem]`
- **속도 제한 완화는 하지 않는다** (§3.4 0.5 req/s). 유일하게 상대 서버에 비용을 떠넘기는 선택지다.
  **지터는 더하기만** 한다 — 빼면 순간 속도가 상한을 넘는다
- **robots.txt 조회 실패는 '금지'로 다룬다.** 네트워크 오류로 규칙이 조용히 사라지는 것이
  가장 위험하다. 404(robots 없음)만 무제한으로 해석
- **robots 파서는 `urllib.robotparser` 유지** ([ADR-0003](docs/adr/0003-robots-parser-library.md)).
  RFC 9309 미준수 공백은 감수하고 `xfail(strict=True)` 2건으로 코드에 고정
- **포크라노스는 상세 페이지 SSR + `product_id` 열거** ([ADR-0002](docs/adr/0002-poclanos-collection-method.md)).
  헤드리스·내부 API 모두 불필요. `PHYSICAL` 만 수집, `artist_raw` 는 항상 `None`
- **조사 시 목록·상세를 각각 확인할 것.** JS 렌더링 필요 여부는 사이트가 아니라 **페이지 종류 단위**다
- **잘못된 어댑터는 임포트 시점에 실패시킨다** — 조용히 0건 수집하는 것보다 기동 실패가 낫다
- **과거 gimbab 조사에서는 목록 해시만 안정적**이었다 (상세의 `qrcode_class` 난수).
  현재 Fetcher는 해시를 계산만 하며 비교 생략은 미구현이다. 외부 사이트 상태는 M3 착수 시 재확인한다
- **예약(PREORDER) 취급은 보류** ([ADR-0001](docs/adr/0001-preorder-open-detection.md) Deferred).
  `StockStatus` 는 §3.1 원안 유지

#### 구현 관례

- **일정이 바뀌면 그 일정에서 나온 이벤트는 무효화한다** (`superseded_at`, §4.5.2).
  안 하면 두 가지가 동시에 깨진다 — 피드에 옛 시각과 새 시각이 함께 남고,
  멱등성 판정이 "이미 보냈다"로 세어 **새 시각에 예약 시작 알림이 안 나간다**.
  **영향받는 이벤트만** 무효화한다 (예약 마감만 고쳤는데 예약 시작을 무효화하면 중복 발송)
- **일정 변경은 이벤트를 지우지 않고 무효화한다.** 운영자가 비공개 발매 자체를 삭제하는
  경우에는 예외로 그 발매의 이벤트·배송 기록도 삭제된다 (T-133).
- **피드는 발매당 한 줄** (`orot_api/feed_query.py` + `routers/feed.py`).
  `/v1/feed` 는 공개 음반을 먼저 정렬·제한한 뒤 최신 이벤트를 붙인다. RSS 는
  `latest_event_per_release()` 로 이벤트가 있는 음반만 고른다. 최신 이벤트 선택 도우미만 공유한다
- **기기 알림은 반대로 묶지 않는다** (T-131). `tag = release-<id>-<event_type>`.
  발매 단위로 묶으면 '예약 임박'이 '예약 시작'에 덮여 **목록에서 사라진다**.
  **피드는 지금 상태를 보는 화면이고, 알림 목록은 지나간 일의 기록**이라 규칙이 다르다
- **이벤트 종류는 네 곳에 흩어져 있다** — enum · DB CHECK 제약 · 알림 라벨 · 화면 라벨.
  enum 에만 더하면 INSERT 가 런타임에 죽고, 라벨을 빠뜨리면 사용자에게 원문이 보인다.
  `packages/core/tests/test_event_types.py` 가 넷을 묶어 둔다
- **익명 쓰기 경로에는 별도 방어가 필요하다** (T-130). 구독 등록에 인증이 없어서
  `endpoint` 를 검증하지 않으면 **인증 없는 SSRF** 가 된다 — 내부망(`127.0.0.1`,
  `192.168.x`)은 포트를 막아 둬도 이 경로로 닿는다. 허용 목록·본문 상한·속도 제한·CSRF 차단이
  한 벌이다. `endswith` 로 호스트를 비교하면 `evilpush.apple.com` 이 통과하므로 **점 경계**를 본다
- **입력 검증과 발송 직전 검증을 둘 다 한다.** 허용 목록이 생기기 전에 저장된 행이 DB 에
  남아 있고, 실제로 요청을 보내는 것은 발송기다
- **본문 상한은 파서보다 앞에 둔다** (ASGI 미들웨어). 필드 `max_length` 는 FastAPI 가
  JSON 을 전부 메모리에 올린 **뒤**에 걸린다. `Content-Length` 가 거짓일 수 있으니 바이트를 센다
- **예외 문자열을 저장·기록하지 않는다.** 푸시 라이브러리 예외에 엔드포인트나 키가 섞인다 —
  HTTP 상태나 예외 클래스명만 남긴다
- **문자열로 HTML 을 만들면 반드시 이스케이프한다.** 관리 UI 의 운영자 키가 `sessionStorage`
  에 있어, 거기서의 XSS 는 곧 운영자 권한 탈취다
- **엣지 케이스는 한 카탈로그에 모은다** (`orot_core/testing.py`). 경로마다 따로 만들면
  한쪽만 고쳐지고 다른 쪽이 조용히 깨진다. 검증은 격리 스키마/트랜잭션을 우선하며,
  공유 DB 정리는 해당 실행에서 생성한 정확한 ID 로만 한다. 제목 접두사를 삭제 권한으로 삼지 않는다
- **필드 간 관계 검증은 `@model_validator` 로** — 별도 메서드는 새 엔드포인트에서 빠뜨릴 수 있다.
  단, 부분 수정(PATCH)처럼 기존 DB 값과 합쳐야 하는 검증은 라우터에 남는다
- **0원은 유효하다.** 운영자 링크 입력은 0~999999999999 의 유한 정수만 허용한다

- **`PUBLIC_WEB_URL` 은 컨테이너에 전달되어야 한다.** 설정만 있고 compose 에 없으면
  기본값 localhost 가 쓰여 **발송은 성공하는데 알림 링크만 죽는다** — 발송 로그로는 안 보인다
- **로그는 아무도 보지 않는다** (T-116). 발송이 조용히 실패하면 사용자는 알림이 안 오는
  줄도 모르고, 운영자는 컨테이너 로그를 뒤져야 안다. 그래서 **밖으로 밀어내는 경로**를 둔다
- **같은 알림은 다시 보내지 않는다** (`ALERT_COOLDOWN = None`). 스케줄러가 60초마다
  도는데 억제가 없으면 분당 한 통씩 나가 채널이 묻히고, **사람이 알림을 꺼 버린다**.
  Slack 메시지는 쌓여 남으므로 다시 알려도 새 정보가 없다. 억제는 `key` 단위라
  다른 종류가 서로를 가리지 않는다. 반복이 필요하면 `cooldown=timedelta(...)` 를 준다.
  **감수 — 문제가 해결됐다 재발해도 (프로세스가 사는 한) 알리지 않는다**
- **정상적인 이탈은 알리지 않는다.** 구독 해제(404/410)는 사용자가 앱을 지우거나
  알림을 끈 것이라 운영자가 할 일이 없고 **사용자가 늘수록 늘어나기만 한다**.
  VAPID 키 불일치 같은 진짜 사고는 푸시 서비스가 **403** 을 주는데, 403 은
  `GONE`(404/410)이 아니라 `FAILED` 라서 `exhausted` 알림이 이미 담당한다.
  **알림을 넣을 때는 "이걸 보고 무엇을 할 것인가"를 먼저 답해야 한다**
- **알림 문구는 `scheduler.py` 상단 상수에 모아 둔다.** 문구를 고치려고 로직을
  건드리지 않도록. `{이름}` 자리표시자를 지우면 **알림이 필요한 순간에 `KeyError`** 가
  나므로 `test_alerts.py` 가 미리 잡는다
- **전송 실패를 '보냈다'로 세지 않는다.** 세면 그 문제가 쿨다운 동안 영영 묻힌다
- **알림 전송 실패가 스케줄러를 멈추면 안 된다.** 여기서 예외가 새면 알림을 못 보내는 데
  그치지 않고 **발송 자체가 죽는다**
- **실패(`failed`)는 알리지 않는다** — 다음 주기에 다시 시도하므로 대개 저절로 낫는다.
  알리는 것은 **재시도 소진**과 **스케줄러 주기 실패**뿐이다
- **비밀은 `repr` 에 남기지 않는다** (`Field(repr=False)`). 트레이스백 렌더러가 지역
  변수를 `repr()` 로 찍어서, `settings` 를 들고 있는 함수가 예외를 던지면 **운영자 키·
  VAPID 개인키·DB 암호·웹훅 URL 이 통째로 로그에 박힌다.** 실제로 그렇게 나갔다.
  로그를 수집하는 환경(CloudWatch 등)으로 옮기면 그대로 사고가 된다
- **웹훅 URL 자체가 비밀이다.** 아는 사람은 누구나 그 채널에 글을 쓸 수 있어
  로그·오류 문자열에 남기지 않는다 (예외는 클래스명만)
- **알림 제목·본문은 서버에서 한 줄로 정리한다** (`_one_line`). 개행을 넘기면 크롬은
  공백으로 접고 일부 안드로이드 런처는 **거기서 잘라** 뒷부분이 사라진다
- **`tag` 로 묶은 알림은 `renotify` 없이는 소리 없이 교체된다.**
  '예약 임박' 위에 '예약 시작'이 조용히 덮이면 이 제품이 유일하게 놓치면 안 되는 순간을 놓친다
- **서비스워커는 푸시를 받으면 무조건 알림을 띄운다.** `userVisibleOnly` 로 구독했으므로
  안 띄우면 브라우저가 대체 알림을 대신 띄우고 **반복되면 푸시 권한을 회수한다**.
  페이로드 파싱 실패는 로그만 남기고 기본 문구로 넘어간다
- **`pushsubscriptionchange` 를 처리하지 않으면 구독이 조용히 죽는다** — 사용자는
  구독 중이라고 믿는데 알림만 오지 않고, 알아챌 방법이 없다
- **서비스워커는 캐시하지 않는다** (`Cache-Control: no-store`, `updateViaCache: "none"`).
  낡은 워커가 남으면 알림 로직 수정이 며칠씩 반영되지 않는다
- **관리 화면은 템플릿 엔진 없이 문자열 HTML**, `include_in_schema=False`.
  운영자 인증은 `X-Admin-Key` 헤더 하나 — 사용자 1명 단계에서 OAuth 는 과설계
- **관리 화면은 로그인 형태다** (T-134). 키 칸이 페이지마다 떠 있으면 매번 다시 넣어야
  하는 것처럼 보이고, 빈 채로 눌러 401 을 받는 일이 반복된다.
  **저장된 키도 그대로 믿지 않는다** — 진입 시 서버에 한 번 확인한다.
  아니면 화면은 열리는데 모든 동작이 401 로 실패한다. 401 을 받으면 로그인 화면으로 되돌린다
- **`datetime-local` 은 타임존이 없다** — 폼이 `+09:00` 을 붙이고 서버는 naive 를 422 로 거부
- **캘린더 날짜는 KST 기준으로 묶는다** — UTC 를 그대로 쓰면 하루 밀린다
- **웹은 API 응답을 캐시하지 않는다** (`cache: "no-store"`). 60초 캐시가 "놓치지 않게" 와 어긋난다
- **RSS 에는 이벤트만** — 미래 시각을 섞으면 안 읽은 글이 목록 위에 계속 뜬다
- **iCalendar·RSS 는 직접 만든다.** 틀리기 쉬운 것을 테스트로 고정 —
  CRLF, **바이트 기준** 75옥텟 접기(한글 3바이트), 이스케이프 순서, RFC 822 `pubDate`, 고정 `guid`/`UID`
- **500 응답에 내부 상세를 넣지 않는다.** 스택은 로그로만, `instance` 로 요청 식별
- **커서는 keyset + base64**. `coalesce(..., 'infinity')` 로 NULL 정렬을 단순화.
  피드는 커서를 쓰지 않는다(앞부분만 보는 화면)
- **부가 정보 파싱 실패가 항목 전체를 버리지 않게 한다** (예: 썸네일)
- **스케줄러 주기 60초**, `tick` 은 실패해도 멈추지 않는다 — 여기서 죽으면 모든 알림이 멈춘다

#### 환경

- **macOS 테스트 환경은 colima + Docker Compose.** CPU/메모리/디스크와 데몬 상태는 호스트 설정이며 코드에서 보장하지 않는다
- **`pip` + `pyproject.toml`** editable 설치. 가상환경은 `venv/`
- **`PYTHONPYCACHEPREFIX=/tmp/pycache`** — 호스트 `__pycache__` 가 마운트로 들어와
  `EOFError: marshal data too short` 로 워커가 죽었다
- **개발 모드의 `WATCHFILES_FORCE_POLLING=true`** — virtiofs 는 inotify 를 전달하지 않아 `--reload` 가 안 먹는다
- **웹은 Next.js 16.** `apps/web/AGENTS.md` 가 요구하는 대로 **코드를 쓰기 전에**
  `apps/web/node_modules/next/dist/docs/` 의 해당 문서를 읽는다 — 학습 데이터와 다르다
- **개발 모드의 컬렉터는 코드를 고쳐도 재기동해야 반영된다** (`docker compose restart collector`).
  개발 API 는 `--reload` 가 있지만 상주 스케줄러는 없다. 운영 모드는 둘 다 재빌드해야 한다. `NOTIFIABLE` 에 종류를 추가했는데
  발송이 안 돼서 보니 프로세스가 **기동 시점 값**을 들고 있었다
- **개발 웹만 `app`/`lib`/`public`/`next.config.ts` 를 마운트한다.**
  `compose.prod.yaml` 은 웹 마운트를 제거하므로 production 웹은 수정 후 재빌드해야 한다
- **운영 모드에서는 마이그레이션도 이미지 내용이다.** `compose.prod.yaml` 이 api·collector 의
  소스 마운트를 걷어내면서 `./migrations` 마운트도 함께 사라진다. 그래서 두 가지가 달라진다 —
  `make migrate` 는 **마지막 `make prod` 빌드 시점까지의** 리비전만 적용하고(새 리비전은 재빌드 후),
  `make revision` 은 **생성한 파일이 컨테이너 안에만 남아** 호스트에서 보이지 않고 컨테이너를
  다시 만들면 사라진다. **리비전 생성은 개발 모드(`make up`)에서 한다.**
  둘 다 오류를 내지 않고 조용히 어긋나므로 실행 전에 어느 모드인지 확인한다
- **VAPID 키는 자체 생성** (`.env`). `VAPID_SUBJECT` 는 **요청에 함께 전송되는 값**이라
  사용자가 명시한 주소만 넣는다. 키가 없으면 푸시만 꺼지고 서버는 정상 기동
- **`make backup` / `make restore`** (블루프린트 §9.3-1). 지우고 되살리는 것까지 시험 완료.
  볼륨은 일반 `down` 후에도 유지되지만 `down -v`·SQL 삭제·디스크 고장에서는 보호되지 않는다.
  백업은 pipefail 로 실패를 감지하고, 복구는 압축 해제 성공 후 단일 SQL 트랜잭션으로 적용한다
