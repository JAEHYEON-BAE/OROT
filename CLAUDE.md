# CLAUDE.md — Vinyl Radar Agent Context

This file is loaded automatically by Claude Code at the start of every session. Read it fully before acting.

---

## 1. What this project is

Vinyl Radar is a **release-schedule notification service** for Korean vinyl (LP) — not a sales database.
It gathers new-release and preorder schedules into one subscribable feed and notifies collectors
**at the moment preorders open**, so limited pressings are not missed.

**Phase 1 (current): the operator enters schedules manually.** Automated harvesting is built and tested
but deliberately unwired; it gets connected in M3 when manual entry becomes the bottleneck.
See [ADR-0005](docs/adr/0005-manual-curation-first.md).

**Not core**: per-shop price comparison, artist discography, exhaustive catalog harvesting.

**Full specification: `docs/BLUEPRINT.ko.md` (authoritative) and `docs/BLUEPRINT.en.md` (mirror).**
Read the blueprint before starting any task. If this file and the blueprint disagree, the blueprint wins.

---

## 2. Non-negotiable rules

1. **Work one task at a time**, identified by a `T-XXX` ID from `§10 Task Backlog` in the blueprint. Announce the ID before starting. Do not begin a second task until every acceptance criterion of the first is met.
2. **No live network requests in tests.** Adapter tests read HTML from `apps/collector/tests/fixtures/<source_id>/`. If a fixture is missing, stop and ask — do not fetch the site to generate one silently.
3. **Never violate the crawling rules in blueprint §3.4.** Specifically: honor robots.txt, cap at 0.5 req/s per source, identify the crawler in the User-Agent, store metadata only, never rehost images, never bypass CAPTCHAs or bot protection.
4. **Never write a merge that is not reversible.** Entity resolution only mutates `listings.release_id`. Never delete a `listings` row.
5. **Never swallow a parse exception.** Return `None`, log with `source_id` and `url`, and increment the error metric. A silent zero-item crawl is the single worst failure mode in this system.
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
    DELETE FROM releases;                          -- 금지: 사용자 데이터까지 지운다
    DELETE FROM releases WHERE title LIKE '__%';   -- 허용: 검증용 접두사만
    ```
    파괴적 작업 전에는 `make backup` 을 먼저 실행하는 편이 안전하다.

    > 이 규칙은 실제 사고에서 나왔다. 2026-08-20 검증 중 `docker compose down -v` 와
    > 전체 `DELETE` 를 반복 실행해 **사용자가 등록한 일정을 지웠고 복구할 수 없었다.**

---

## 3. Commands

```bash
make up          # start the local stack (postgres, api, collector, web)
make down
make migrate     # alembic upgrade head
make seed        # seed sources + artist aliases
make test        # pytest across packages/core, apps/api, apps/collector
make lint        # ruff check + ruff format --check + mypy
make openapi     # regenerate docs/api/openapi.json

# 백업 (파괴적 작업 전에 실행할 것)
make backup                            # backups/ 에 타임스탬프 덤프
make backups                           # 백업 목록
make restore FILE=backups/xxx.sql.gz   # 복구 — 기존 데이터를 덮어쓴다 (확인 프롬프트 있음)

# collector CLI
docker compose exec collector collector run --source gimbab --dry-run --limit 5
docker compose exec collector collector review-merges

# 푸시 진단 — 등록된 구독에 시험 알림을 보낸다 (DB 를 바꾸지 않는다)
docker compose exec collector collector test-push
docker compose exec collector collector test-push --dry-run   # 대상·페이로드만 출력

# 실제 기기 시험 — iOS 는 유효한 HTTPS 없이는 서비스워커를 등록하지 않는다
cloudflared tunnel --url http://localhost:3000   # https://<무작위>.trycloudflare.com
# 그 주소를 .env 의 PUBLIC_WEB_URL 에 넣고 `docker compose up -d web collector`.
# 안 바꾸면 발송은 성공하는데 **알림을 눌러도 아무 데도 못 간다.**
```

Always run `make lint && make test` before declaring a task complete.

---

## 4. Conventions

### Python
- Python 3.12, `ruff` for lint and format, `mypy --strict` on `packages/core`.
- Type hints on every public function. Pydantic v2 for boundary models, SQLAlchemy 2.0 (typed `Mapped[...]`) for ORM.
- Async by default in the collector and API. No blocking I/O inside async functions.
- Module layout follows blueprint §6 exactly.

### Naming
- `source_id` values are lowercase ASCII slugs: `gimbab`, `secondtrack`, `poclanos`.
- Database and JSON fields are `snake_case`. Swift and TypeScript surfaces map from generated clients — do not hand-rename.
- Fields suffixed `_raw` hold source text verbatim. **Never normalize in place;** normalized values live in `_norm` fields.

### Commits
```
<type>(<scope>): <T-ID> <summary>

feat(collector): T-014 implement Secondtrack adapter
fix(core): T-020 prevent merge across differing variants
docs(blueprint): T-006 record Gimbab robots.txt and selectors
```
Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`. Scopes: `core`, `collector`, `api`, `web`, `ios`, `infra`, `blueprint`.

### Generated code
- TypeScript API types come from `openapi-typescript`. Swift models come from `swift-openapi-generator`. **Hand-written duplicates of these types are prohibited** and will be rejected in review.

---

## 5. Adding a new source (checklist)

Do these in order. Each step is part of the same task.

1. Write `docs/adapters/<source_id>.md` containing: robots.txt verbatim, relevant ToS clauses with your reading of them, listing URL and pagination pattern, whether JS rendering is required, a selector table for all eight fields, and whether JSON-LD / OpenGraph structured data is available.
2. Save ≥ 3 HTML fixtures under `apps/collector/tests/fixtures/<source_id>/` — one in-stock, one sold-out, one preorder.
3. Implement `packages/core/src/vinyl_core/adapters/<source_id>.py` against the `SourceAdapter` protocol. **Prefer structured data over CSS selectors when available.**
4. Write golden tests asserting every `RawItem` field for each fixture.
5. Add a row to the `sources` seed data.
6. Register the source in `parser-canary.yml`.

If the site requires login, blocks bots, or its ToS prohibits automated access: **stop, document the finding, and exclude the source.** Do not attempt to work around it.

---

## 6. Things that are easy to get wrong here

- **Variants are not duplicates.** A clear-vinyl pressing and a black pressing of the same album are different `release` rows. Merging them is a correctness bug, not a nicety.
- **Precision over recall in resolution.** When confidence is between 0.70 and 0.90, queue into `merge_candidates` and leave `release_id` NULL. Do not guess.
- **`PREORDER_OPEN` is time-critical.** Its dispatch path must not sit behind the batch notification queue.
- **`price_krw` is `NUMERIC(12,0)`.** Korean won has no minor unit; never introduce floats into price handling.
- **Timestamps are `TIMESTAMPTZ` and stored in UTC.** Source sites publish in KST; convert at parse time, never at display time in the database.
- **`content_hash` skipping is what keeps the crawl polite.** Do not disable it for convenience during development — use `--dry-run` instead.

---

## 7. Current state

> Update this section at the end of every task.

- **Milestone**: **M2 (시각 기반 알림)** — M1 완료
- **Last completed task**: **T-119 (일정 변동 시 옛 이벤트 무효화·재발송)**
  - 일정이 바뀌면 그 시각에서 나온 `PREORDER_OPENS_SOON`/`PREORDER_OPEN`/`RELEASED` 를
    **`superseded_at` 으로 무효화**한다. 피드에서 사라지고, 스케줄러가 새 시각에 다시 만든다
  - **지우지 않는다** — 그 행은 구독자에게 보낸 기록이고 `notification_deliveries` 가 참조한다
  - 실기기 검증: 예약 시각 변경 → `SCHEDULE_CHANGED` 발송 → 옛 2건 무효화 →
    **새 시각에 `PREORDER_OPENS_SOON`·`PREORDER_OPEN` 재발생·재발송**(오차 49초)
  - 앞선 **T-118**: 피드는 발매당 최신 이벤트 1건만 (`vinyl_api/feed_query.py`,
    `/v1/feed` 와 RSS 가 공유). `SCHEDULE_CHANGED` 신설 — enum·CHECK 제약·라벨 4곳
  - `make lint` / `make test` (**337 passed, 2 xfailed**) 통과
- **그 앞**: **T-117 (웹 구독 UI — PWA 매니페스트 + 서비스워커)**
  - `app/manifest.ts`, `public/sw.js`, `public/icon-*.png`,
    `lib/push.ts`, `lib/proxy.ts`, `app/api/push/*`, `subscribe/PushToggle.tsx`
  - 브라우저는 API 를 직접 부르지 않는다 — **같은 출처 프록시**
    ([ADR-0007](docs/adr/0007-same-origin-push-proxy.md))
  - 실 스택 검증: 매니페스트·아이콘 4종·`sw.js` 헤더(`no-store`) 200,
    프록시 왕복 201/201(갱신)/422/204/204(멱등), `<head>` 에 manifest·apple-touch-icon·theme-color
  - **`sw.js` 를 Node 에서 실제로 실행**해 카탈로그 페이로드 64건(16케이스 x 4이벤트) +
    깨진 페이로드 6건 + 클릭·탭 재사용·구독 교체까지 통과 확인
  - 발견·수정 2건 (§'구현 관례' 참조): 알림 텍스트 한 줄 정리, `renotify`
  - `make lint` / `make test` (**309 passed, 2 xfailed**) 통과
  - 앞서 완료: T-111~T-115, 엣지 케이스 카탈로그(`vinyl_core/testing.py` 25건)
- **Next task**: **T-116** (재시도 · 만료 구독 정리 · 무음 실패 알림).
  이제 실제 기기에서 성공/실패를 볼 수 있으므로 재시도 정책을 근거 있게 정할 수 있다
- **DB 에 시험 데이터가 있다**: `releases.id=31` `[테스트] 알림 확인용 발매`.
  **공개된 적이 있어 API 로는 지울 수 없다**(이벤트가 존재). 지우려면 이벤트·배송기록까지
  함께 지우는 SQL 이 필요하고, 규칙 10 에 따라 사용자 확인이 먼저다
- **실제 기기 시험 경로 (T-117 이후 추가)**: `cloudflared` 터널 + `PUBLIC_WEB_URL`.
  `collector test-push` 로 **전송 경로만** 따로 확인한다 —
  알림이 안 올 때 원인이 전송(VAPID·키·네트워크)인지 로직(이벤트 생성·대상 선정)인지
  구분되지 않으면 어디를 봐야 할지 알 수 없다.
  **터널 주소는 재시작마다 바뀐다** → `PUBLIC_WEB_URL` 도 같이 바꿔야 한다
- **`localhost` 도 보안 컨텍스트다** — 맥 Safari·크롬에서는 터널 없이 바로 구독된다.
  Safari 로 하면 **Apple 푸시 서버(`web.push.apple.com`)를 그대로 타서**
  아이폰과 같은 인프라를 미리 검증할 수 있다.
  **iOS 시뮬레이터로는 안 된다** — APNs 연결이 없어 `subscribe()` 가 실패한다
  (`simctl push` 는 네이티브 번들 ID 전용). 홈 화면 추가·아이콘·standalone 확인까지만 가능
- **T-007 이후 변경**: 목록 기반 수집으로 전환 ([ADR-0004](docs/adr/0004-list-page-collection.md)).
  `SourceAdapter.parse_item()` → **`parse_page()`** 로 일반화, 블루프린트 `.ko`/`.en` 동시 수정 완료
- **Known open questions**:
  1. **robots 안전망이 secondtrack 에서 동작하지 않는다 (감수하기로 한 위험).**
     `urllib.robotparser` 가 RFC 9309 의 최장 매치·와일드카드를 지원하지 않아
     `/shop_cart`, `/?mode=policy` 를 허용으로 잘못 판정한다. 현재 어댑터가 이 경로를
     만들지 않아 실제 위반은 없다. **보완책(`discover()` URL 패턴 화이트리스트)은 보류 중** —
     어댑터가 사이트 HTML 의 링크를 필터 없이 따라가기 시작하면 재검토
     ([ADR-0003](docs/adr/0003-robots-parser-library.md) §7 재검토 조건)
  2. **조건부 요청 검증자를 저장할 곳이 없다.** §3.3 은 `If-None-Match`/`If-Modified-Since` 를
     요구하지만 §4.2 의 `raw_snapshots` 에 `etag`/`last_modified` 컬럼이 없다.
     현재는 프로세스 메모리 캐시(재기동 시 소실). **T-017 에서 스키마와 함께 결정 필요**
  3. gimbab CD 카테고리(`cate_no=24` 계열) 수집 여부 미정 — 서비스 범위는 바이닐
  4. 포크라노스 `saleStatus` 의 전체 값 목록 미확인 (표본 3건) — 미지 값은 `UNKNOWN` 처리
  5. 포크라노스 다옵션 상품의 재고 판정 규칙 미정

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
- **`UNIQUE (event_id, device_token_id)` 가 발송 멱등성의 전부다.**
  코드가 아니라 제약이 보장한다
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
- **삭제는 "한 번도 공개된 적 없는" 초안만.** 공개했다 취소한 일정도 이미 구독자에게 나갔다.
  `listing_events` FK 에 CASCADE 를 걸지 않은 것도 같은 이유
- **⚠️ 세션 커밋은 응답 이후에 일어난다.** 엔드포인트에서 `flush()` 하지 않으면 제약 위반이
  응답 뒤에 터져 클라이언트가 성공으로 오해한다. 실제로 DELETE 가 FK 위반인데 204 를 돌려줬다.
  **쓰기 경로는 반드시 `flush()`**
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
- **`content_hash` 는 목록에서만 안정적** (상세엔 `qrcode_class` 난수). 조건부 요청은 gimbab 에서 무의미
- **예약(PREORDER) 취급은 보류** ([ADR-0001](docs/adr/0001-preorder-open-detection.md) Deferred).
  `StockStatus` 는 §3.1 원안 유지

#### 구현 관례

- **일정이 바뀌면 그 일정에서 나온 이벤트는 무효화한다** (`superseded_at`, §4.5.2).
  안 하면 두 가지가 동시에 깨진다 — 피드에 옛 시각과 새 시각이 함께 남고,
  멱등성 판정이 "이미 보냈다"로 세어 **새 시각에 예약 시작 알림이 안 나간다**.
  **영향받는 이벤트만** 무효화한다 (예약 마감만 고쳤는데 예약 시작을 무효화하면 중복 발송)
- **이벤트는 지우지 않고 표시한다.** `notification_deliveries` 가 참조하는 발송 기록이다 —
  보낸 사실은 취소되지 않는다
- **피드는 발매당 최신 이벤트 하나만** (`vinyl_api/feed_query.py`).
  `/v1/feed` 와 RSS 가 **같은 함수**를 쓴다 — 각자 질의를 들면 한쪽만 고쳐진다.
  푸시의 `tag=release-<id>` 와 같은 규칙이라 세 곳이 같은 것을 보여 준다
- **이벤트 종류는 네 곳에 흩어져 있다** — enum · DB CHECK 제약 · 알림 라벨 · 화면 라벨.
  enum 에만 더하면 INSERT 가 런타임에 죽고, 라벨을 빠뜨리면 사용자에게 원문이 보인다.
  `packages/core/tests/test_event_types.py` 가 넷을 묶어 둔다
- **엣지 케이스는 한 카탈로그에 모은다** (`vinyl_core/testing.py`). 경로마다 따로 만들면
  한쪽만 고쳐지고 다른 쪽이 조용히 깨진다. 검증 데이터는 `__EDGE__` 접두사로 골라 지운다
- **필드 간 관계 검증은 `@model_validator` 로** — 별도 메서드는 새 엔드포인트에서 빠뜨릴 수 있다.
  단, 부분 수정(PATCH)처럼 기존 DB 값과 합쳐야 하는 검증은 라우터에 남는다
- **0원은 유효하고 음수만 막는다** — 증정품·무료 배포가 실재한다

- **`PUBLIC_WEB_URL` 은 컨테이너에 전달되어야 한다.** 설정만 있고 compose 에 없으면
  기본값 localhost 가 쓰여 **발송은 성공하는데 알림 링크만 죽는다** — 발송 로그로는 안 보인다
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

- **colima** (4 CPU/8GB/100GB) + brew `docker-compose`. Docker Desktop 없음
- **`pip` + `pyproject.toml`** editable 설치. 가상환경은 `venv/`
- **`PYTHONPYCACHEPREFIX=/tmp/pycache`** — 호스트 `__pycache__` 가 마운트로 들어와
  `EOFError: marshal data too short` 로 워커가 죽었다
- **`WATCHFILES_FORCE_POLLING=true`** — virtiofs 는 inotify 를 전달하지 않아 `--reload` 가 안 먹는다
- **웹은 Next.js 16.** `apps/web/AGENTS.md` 가 요구하는 대로 **코드를 쓰기 전에**
  `apps/web/node_modules/next/dist/docs/` 의 해당 문서를 읽는다 — 학습 데이터와 다르다
- **컬렉터는 코드를 고쳐도 재기동해야 반영된다** (`docker compose restart collector`).
  API 는 `--reload` 가 있지만 상주 스케줄러는 없다. `NOTIFIABLE` 에 종류를 추가했는데
  발송이 안 돼서 보니 프로세스가 **기동 시점 값**을 들고 있었다
- **웹 컨테이너는 `app`/`lib`/`public`/`next.config.ts` 를 마운트한다.**
  `public/` 을 빠뜨리면 `sw.js` 수정이 이미지를 다시 빌드할 때까지 반영되지 않는다
- **VAPID 키는 자체 생성** (`.env`). `VAPID_SUBJECT` 는 **요청에 함께 전송되는 값**이라
  사용자가 명시한 주소만 넣는다. 키가 없으면 푸시만 꺼지고 서버는 정상 기동
- **`make backup` / `make restore`** (블루프린트 §9.3-1). 지우고 되살리는 것까지 시험 완료.
  **볼륨은 실수 삭제만 막을 뿐** 디스크 고장·잘못된 마이그레이션은 못 막는다
