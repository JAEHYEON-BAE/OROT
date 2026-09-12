# OROT — 바이닐 발매·예약 일정 서비스 청사진 (한국어판)

> **기준일: 2026-09-11 · 버전 1.1.0**. 현재 구현은 소스·마이그레이션·실행 설정을 기준으로 설명한다.
> 문서와 구현이 충돌하면 구현을 우선하여 문서를 갱신한다. 미구현 계획은 현재 동작이나 자동 실행 지시가 아니다.
> [영어판](BLUEPRINT.en.md)과 함께 유지하며, 두 판의 설명이 충돌하면 한국어판을 먼저 바로잡고 번역한다.

## 0. 에이전트를 위한 우선 지시사항 (READ FIRST)

1. 사용자 지시 범위를 우선한다. 백로그 작업은 기존 `T-XXX`를 명시하고 하나씩 완료한다. 유지보수·점검에 임의의 태스크 ID를 만들지 않는다.
2. §6의 현재 경로와 향후 예약 경로를 구분한다. 정의되지 않은 최상위 디렉터리를 만들지 않는다.
3. 자동 테스트는 외부 실사이트에 요청하지 않는다. 어댑터는 저장된 HTML fixture, 푸시는 가짜 발송기로 검증한다. `collector run --dry-run`은 실제 네트워크 요청이므로 자동 테스트가 아니다.
4. 수집 정책은 §3.4를 따른다: 소스별 최대 0.5 req/s, 동시 연결 2 이하, robots 준수, 메타데이터만 사용.
5. 구현 변경에는 `make lint`와 `make test`, 웹 변경에는 웹 lint·Node 테스트·build를 실행한다. 문서만 고칠 때는 경로·명령·계약 대조를 하고 서비스를 재기동하지 않는다.
6. 새 아키텍처 결정이 필요하면 ADR 초안을 작성한다. 이미 승인된 방향의 구현·문서 정정은 다시 허가를 요구하지 않는다.
7. Python은 `venv/bin/python`, Make 타깃 또는 컨테이너의 Python을 사용한다.
8. 기존 데이터·키·백업을 보존한다. 파괴적 조작은 승인 범위에서만 수행하며, 테스트는 격리 스키마와 롤백을 우선한다. 공유 DB의 정리는 해당 실행에서 만든 정확한 ID만 대상으로 한다.

---

### 서비스 이름과 이전 설치 호환성

서비스 표기와 프로젝트 폴더는 **OROT**이다. 기술 식별자는 도구 규칙에 따라
`orot`, `orot-core`/`orot-api`/`orot-collector`/`orot-web`,
Python import는 `orot_core`/`orot_api`/`orot_collector`를 사용한다.
음반 재질·외부 사이트 원문의 vinyl 표기는 서비스 이름이 아니므로 보존한다.
RSS GUID·iCalendar UID는 대중 배포 전 사용자 결정(2026-09-12)에 따라
`orot_api/feed_identity.py`의 `OROT` namespace로 통일했다. 예: `event-10@OROT`,
`preorder-1@OROT`, `release-1@OROT`. 이후에는 고정 ID의 안정성을 유지한다.
이전 테스트 구독에서는 항목이 새로 인식될 수 있다. 표시명·다운로드 파일명도 OROT 기준이다.
기존 설치는 `.env`의 DB 접속 정보와 `POSTGRES_VOLUME_NAME`, `POSTGRES_VOLUME_EXTERNAL=true`,
`ENV_BACKUP_KEYCHAIN_SERVICE`로 기존 DB·암호화 백업을 이어 쓴다. 이를 새 이름으로
일괄 치환하면 데이터 접근이 끊기므로 실제 DB 역할·볼륨·키체인 식별자는 보존한다.
새 설치의 기본값은 `orot`, `orot_postgres_data`, `orot-env-backup`이다.
폴더 이동 시 로컬 venv 경로·LaunchAgent·Compose 소스 마운트를 함께 갱신한다.
VAPID 키·공개 URL·PWA start_url/scope는 이름 변경으로 바꾸지 않는다.

## 1. 문제 정의

### 1.1 현상

국내 바이닐(LP) 발매 정보는 다음과 같은 이유로 파편화되어 있습니다.

| 유형 | 사례 | 문제점 |
|---|---|---|
| 인디 레코드샵 | 김밥레코즈, 세컨드트랙, 도프레코드 | 각자 독립된 쇼핑몰 솔루션. RSS/API 부재. 입고 알림이 SNS로만 공지되는 경우 다수 |
| 레이블·유통사 | 포크라노스, 미러볼뮤직, 비트볼 | 발매 소식이 보도자료·인스타그램 중심. 정형화된 목록 부재 |
| 대형 유통 | YES24, 알라딘, 핫트랙스 | 검색은 되지만 "이번 주 신규 입고"라는 관점의 뷰가 없음 |
| 해외 | Discogs, Bandcamp | 국내 유통 여부·국내 가격을 알 수 없음 |

그 결과 수집가는 **한정반(限定盤)의 예약 판매 오픈 시점을 놓치는 문제**를 반복적으로 겪습니다. 한정반은 통상 수 시간 내 매진되므로, 정보 지연 자체가 실질적 손실로 이어집니다.

### 1.2 해결 가설

> 신규 발매·예약판매 **일정을 한 곳에 모아** 사용자가 구독할 수 있게 하고, **예약 시작 시각에 맞춰 알림**을 보내면, 한정반을 놓치는 문제를 실질적으로 해소할 수 있다.

**이 제품은 판매 데이터베이스가 아니라 일정 알림 서비스입니다.** ([ADR-0005](adr/0005-manual-curation-first.md))

- **핵심**: 신규 발매 일정, 예약판매 기간, 놓치지 않게 하는 알림
- **핵심 아님**: 판매처별 가격 비교, 아티스트 디스코그래피, 카탈로그 전수 수집

일정 데이터는 **1단계에서 운영자가 직접 등록**합니다. 자동 수집은 부품이 준비된 상태로 대기하며
운영자 등록이 병목이 되는 시점에 배선합니다 (M3).

> **자동 수집이 일정을 채울 수 없는 이유** (실측): 세 소스 모두 **발매일을 구조적 필드로 제공하지 않으며**,
> **예약 마감 시각은 어느 소스도 노출하지 않습니다.** 캘린더의 중심 데이터는 사람이 넣어야 합니다.

### 1.3 성공 지표 (MVP 기준)

> 아래는 제품 목표이며 현재 측정 결과나 보장된 SLA가 아니다. Slack 운영자 알림은 구현되어 있으나, 호스트·프로세스 중단을 감지하는 외부 감시는 없다.

| 지표 | 목표 |
|---|---|
| 등록된 일정 수 (주간) | 20건 이상 |
| **예약 시작 알림 발송 성공률** | **≥ 99%** (시각 기반이므로 누락은 버그) |
| 알림 발송 시각 오차 | ±1분 |
| 일정 등록 → 공개 피드 노출 | 즉시 |
| 무음 실패(silent failure) | 0건 (반드시 알림 발생) |

**M3(자동 수집 재개) 이후에 측정할 지표**

| 지표 | 목표 |
|---|---|
| 수집 대상 소스 수 | 3개 이상 |
| 신규 상품 등록 → 앱 노출 지연 | 중앙값 30분 이내 |
| 중복 병합 정확도 | 정밀도 ≥ 0.95, 재현율 ≥ 0.80 |

### 1.4 명시적 비목표 (Non-Goals)

- 상품 **판매 및 결제 대행**을 하지 않습니다. 항상 원본 판매처로 아웃링크합니다.
- 상품 **이미지·상세 설명 원문을 재호스팅하지 않습니다.**
- 해외 직구 가격 비교(Discogs Marketplace 시세 추적)는 v1 범위 밖입니다.
- 사용자 간 거래(중고 장터) 기능은 범위 밖입니다.
- **판매처별 가격 비교와 아티스트 디스코그래피는 v1 핵심 기능이 아닙니다** ([ADR-0005](adr/0005-manual-curation-first.md)).
- **카탈로그 전수 수집을 하지 않습니다.** 신규 발매·예약·재입고가 나타나는 표면만 봅니다.

---

## 2. 아키텍처 개요

### 2.1 현재 실행 흐름

```text
운영자 → localhost:8000/admin → FastAPI → PostgreSQL
                              초안 등록 → 공개 → SCHEDULE_ADDED
PostgreSQL ← collector: 60초 tick → 시각 이벤트 → 배송 계획 → WebPushSender
                                                       ↓
                                     브라우저 푸시 서비스 → sw.js → 기기 알림
인터넷 → Tailscale Funnel → localhost:3000 → Next.js → 내부 FastAPI
                                             ├ 피드·상세·캘린더·구독
                                             ├ /api/push/* 중계
                                             └ /v1/feed.rss · /v1/releases.ics 중계
```

단일 collector의 APScheduler가 이벤트 생성과 발송을 같은 tick에서 실행한다.
별도 메시지 브로커·APNs 발송기·워치리스트 매칭은 없다. 자동 수집 어댑터와 Fetcher는
수동 `collector run --dry-run`에서만 연결되며, DB 적재·주기 수집은 M3 계획이다.

### 2.2 현재 기술 스택과 보류 사항

| 계층 | 현재 구현 | 보류/미구현 |
|---|---|---|
| Python | Python ≥3.12, pip editable, Pydantic v2, SQLAlchemy 2 async | 별도 패키지 워크스페이스 도구 없음 |
| API | FastAPI ≥0.121, 관리자 키 인증, 공개 조회·익명 푸시 구독 | JWT·계정·검색 API |
| DB | PostgreSQL 16, pg_trgm/unaccent, Alembic | 확장을 이용한 검색·병합 서비스 |
| 스케줄러·푸시 | APScheduler 60초, DB 배송 기록, pywebpush를 asyncio.to_thread로 호출 | 메시지 브로커·일일 요약·APNs |
| 수집 부품 | httpx async, selectolax, urllib.robotparser, 3개 어댑터 | 자동 수집 적재·정규화·병합 |
| 웹 | Next.js 16.3.3 App Router, React 19, Tailwind 4, npm, PWA | SwiftUI 앱·생성 클라이언트 |
| 실행 | Docker Compose, Mac mini/colima + Funnel 공개 테스트 | EC2/GHCR/SSH 배포 |
| 관측·자동화 | structlog, /healthz, Slack 장애 알림, GitHub Actions CI, 로컬 테스트와 백업 스크립트 | Prometheus·Sentry·외부 생존 감시·자동 배포 |

---

## 3. 데이터 수집 계층 상세

### 3.1 구현된 어댑터 인터페이스

`packages/core/src/orot_core/adapters/base.py`가 계약이다. 등록은 `@register`와 모듈 자동 탐색으로
처리하며 registry 수정은 필요 없다. 새 소스에는 어댑터 외에도 fixture·테스트·조사 문서·시드가 필요하다.

```python
from collections.abc import AsyncIterator
from typing import Protocol
from orot_core.adapters.base import RawItem

class PageFetcher(Protocol):
    async def fetch_text(self, url: str) -> str | None: ...

class SourceAdapter(Protocol):
    source_id: str
    display_name: str
    base_url: str
    crawl_interval_seconds: int
    requires_javascript: bool

    def discover(self) -> AsyncIterator[str]: ...
    async def parse_page(self, url: str, html: str) -> list[RawItem]: ...
```

`RawItem`의 필수값은 source_id·source_item_id·url·title_raw·stock_status다.
부가 필드는 None, extra는 새 dict, fetched_at은 현재 UTC가 기본이다. 원화는 음수·소수를 거부하며
fetched_at은 타임존을 요구한다. 파싱 실패는 빈 목록과 로그로 나타낸다.
`PageFetcher`는 `orot_collector.bridge.FetcherPageAdapter`로 주입하여 core가 collector를 import하지 않게 한다.

### 3.2 소스별 조사 결과 및 구현 노트

현재 gimbab·secondtrack·poclanos 어댑터가 모두 존재한다. 아래 우선순위의 M0/M1 표기는 초기 조사 순서이며 현재 제품 마일스톤 상태를 뜻하지 않는다.

> **주의**: 각 사이트의 DOM 구조는 변경될 수 있습니다. 아래는 구현 착수 시점의 조사 가이드이며, 에이전트는 반드시 실제 HTML을 `tests/fixtures/<source_id>/` 에 저장한 뒤 셀렉터를 확정해야 합니다.

| source_id | 이름 | 특성 | 구현 우선순위 | 예상 난이도 |
|---|---|---|---|---|
| `gimbab` | 김밥레코즈 | 국내 대표 인디 레코드샵. 신보 입고가 빈번 | **1순위 (M0)** | 하 |
| `secondtrack` | 세컨드트랙 | 큐레이션 중심. 한정반 취급 비중 높음 | 2순위 (M1) | 중 |
| `poclanos` | 포크라노스 | 유통사. 발매 예정 정보가 가장 빠름 | 3순위 (M1) | 중 |
| `dope` | 도프레코드 | 확장 후보 | M4 이후 | 중 |
| `mirrorball` | 미러볼뮤직 | 확장 후보 | M4 이후 | 중 |
| `yes24` | YES24 LP | 대형 유통, 재고 안정적 | M4 이후 | 상 (봇 차단 정책 확인 필요) |

**조사 체크리스트 (새 소스 추가 시 반드시 수행):**

1. `https://<domain>/robots.txt` 확인 → `docs/adapters/<source_id>.md` 에 전문 기록
2. 이용약관에서 자동 수집 관련 조항 확인 → 동일 문서에 인용 및 판단 근거 기록
3. 목록 페이지 URL 패턴 및 페이지네이션 방식 파악 (offset / cursor / 무한스크롤 XHR)
4. JS 렌더링 필요 여부 판단 (`curl` 결과에 상품명이 포함되는지)
5. 상품 상세 페이지에서 다음 필드의 CSS 셀렉터 확정: 제목, 아티스트, 레이블, 가격, 재고, 포맷, 발매일, 썸네일
6. 구조화 데이터(JSON-LD `Product` 스키마, OpenGraph) 존재 여부 확인 — **존재하면 HTML 셀렉터보다 우선 사용** (변경에 강함)
6-1. **목록 페이지와 상세 페이지를 각각 확인한다.** JS 렌더링 필요 여부와 수집 가능한 필드는 **페이지 종류마다 다르다.** 목록만으로 `RawItem` 필드를 모두 채울 수 있으면 **목록 기반 수집을 우선한다** — 요청 수가 페이지당 상품 수만큼 줄어든다 (ADR-0004)
7. HTML 스냅샷 3건 이상을 fixture로 저장 (재고 있음 / 품절 / 예약판매 각 1건)

### 3.3 수집 파이프라인 계획 (M3, 미구현)

현재 CLI는 discover → Fetcher → parse_page → 출력까지만 실행한다. DB 적재·last_seen_at 갱신·해시 비교 생략은 없다.
Fetcher는 본문 해시를 계산하고 ETag/Last-Modified를 메모리에 보관하지만 영속 저장하지 않는다.
아래 그림은 향후 배선 계획이며, 계정 매칭과 APNs도 현재 실행되지 않는다. 이메일 채널은 만들지 않는다 (ADR-0006).

```
[Scheduler] 소스별 크론 트리거
     ↓
[discover()] 수집 대상 페이지(목록/상세) URL 집합 확보
     ↓
[Fetcher] URL별 GET (조건부 요청: If-None-Match / If-Modified-Since)
     ├─ 304 Not Modified → 스킵 (last_seen_at만 갱신)
     └─ 200 OK → 본문 해시 계산
           ├─ content_hash 동일 → 스킵
           └─ 상이 → raw_snapshots 저장 후 parse_page() 호출 (목록이면 N건)
     ↓
[Normalizer] RawItem → NormalizedListing
     ↓
[EntityResolver] release_id 결정 (신규 생성 또는 기존 병합)
     ↓
[EventDetector] 직전 listing 상태와 비교 → listing_events 생성
     ↓
[NotificationDispatcher] 워치리스트 매칭 → 설정된 푸시 채널 (향후)
```

### 3.4 수집 윤리 및 법적 준수사항 (필수)

에이전트는 다음 규칙을 **예외 없이** 코드에 반영합니다.

| 규칙 | 구현 방법 |
|---|---|
| robots.txt 준수 | `urllib.robotparser` 로 매 크롤 시작 시 파싱. `Disallow` 경로 접근 금지 |
| 요청 속도 제한 | 소스별 **최대 0.5 req/s**, 동시 연결 2 이하. `asyncio.Semaphore` + 지터(jitter) 적용 |
| User-Agent 명시 | `OROT/1.0 (+https://<도메인>/about; contact@<도메인>)` — 정체와 연락처를 밝힘 |
| 조건부 요청 사용 | ETag / Last-Modified 캐시로 불필요한 트래픽 최소화 |
| 저작물 재사용 최소화 | **메타데이터(제목·아티스트·가격·재고·발매일)만 저장.** 상세 설명 원문·리뷰 텍스트 저장 금지. 썸네일은 URL만 저장하고 자체 CDN에 복제하지 않음 |
| 원본 귀속 | 모든 화면에서 소스명 표기 + 원본 상품 페이지로 아웃링크 |
| 우회 금지 | CAPTCHA·봇 차단 우회, 로그인 필요 영역 접근, 비공개 내부 API 역공학 금지 |
| 차단 대응 | 429/403 수신 시 지수 백오프 후 해당 소스 자동 비활성화 + 운영자 알림 |
| 사전 고지 | 서비스 공개 전 각 소스 운영자에게 이메일로 목적 설명 및 제휴/API 제공 가능 여부 문의 |

**정책과 구현의 경계:** 위 표는 준수 정책이며 자동화가 전부 구현됐다는 뜻은 아니다.
현재 403/429 반복 시 Fetcher는 백오프 후 SourceBlockedError를 내고 CLI가 중단한다.
DB의 소스 자동 비활성화와 운영자 알림은 M3 미구현이다. robots 조회 실패는 금지로 취급하되
404는 robots 없음으로 처리한다. urllib.robotparser의 최장 매치·와일드카드 한계는 ADR-0003과
2개의 xfail 테스트에 기록되어 있다. 외부 연락은 사용자 승인 없이 전송하지 않는다.
아래 법률·사이트 조사 설명은 원래 조사 당시 배경이며, 현재 법률이나 사이트 상태를 재검증한 결과는 아니다.

> **법적 배경 참고**: 국내에서는 저작권법상 데이터베이스제작자의 권리(제91조~제98조), 부정경쟁방지법상 성과물 무단사용(제2조 제1호 차목), 각 사이트 이용약관이 쟁점이 될 수 있습니다. 일반적으로 **사실적 메타데이터의 소량 수집 + 원본 아웃링크 + 대체재가 아닌 보완재로 기능**하는 구조가 위험이 낮다고 평가되나, 이는 법률 자문이 아닙니다. 서비스를 공개적으로 운영하거나 수익화할 계획이라면 전문가 검토를 권합니다. 개인 학습·포트폴리오 목적이라면 **비공개 운영 + 소스 운영자 사전 동의 확보**가 가장 안전한 경로입니다.

---

## 4. 데이터 모델

### 4.1 개념 모델

- **`listing`**: 특정 판매처의 특정 상품 페이지 하나. 소스마다 별개로 존재.
- **`release`**: 물리적 실체로서의 한 판(edition). 카탈로그 번호와 바리언트(색상 등)로 구분.
- **`master`**: 동일 앨범의 여러 판을 묶는 상위 개념 (선택적, v1.1).

> 예시: 실리카겔 『Machine Boy』 한정 컬러반은 김밥레코즈와 세컨드트랙에 각각 `listing`으로 존재하지만, 동일한 하나의 `release`로 병합됩니다. 반면 블랙반과 클리어반은 **서로 다른 `release`** 입니다.

### 4.2 스키마 (PostgreSQL DDL)

이 DDL은 현재 모델의 설명용 요약이다. 실제 변경은 `migrations/versions/`의 Alembic 리비전으로 적용한다.
테이블이 있다는 사실이 계정·크롤 적재·병합 기능의 구현을 뜻하지는 않는다. ORM의 onupdate 동작은 DDL 트리거가 아니다.

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- 소스 마스터
CREATE TABLE sources (
    id                  TEXT PRIMARY KEY,           -- 'gimbab'
    display_name        TEXT NOT NULL,
    base_url            TEXT NOT NULL,
    kind                TEXT NOT NULL CHECK (kind IN ('shop','label','distributor')),
    crawl_interval_sec  INT  NOT NULL DEFAULT 1800 CHECK (crawl_interval_sec >= 300),
    is_enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    disabled_reason     TEXT,
    last_crawled_at     TIMESTAMPTZ
);

-- 원본 스냅샷 (감사 및 파서 회귀 테스트용)
CREATE TABLE raw_snapshots (
    id            BIGSERIAL PRIMARY KEY,
    source_id     TEXT NOT NULL REFERENCES sources(id),
    url           TEXT NOT NULL,
    http_status   INT  NOT NULL,
    content_hash  TEXT NOT NULL,            -- sha256(body)
    body_path     TEXT,                     -- 로컬/S3 경로. 본문은 DB에 저장하지 않음
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON raw_snapshots (source_id, fetched_at DESC);
CREATE INDEX ON raw_snapshots (content_hash);

-- 아티스트
CREATE TABLE artists (
    id           BIGSERIAL PRIMARY KEY,
    name_display TEXT NOT NULL,
    name_ko      TEXT,
    name_en      TEXT,
    name_norm    TEXT NOT NULL,             -- 정규화 키
    mbid         UUID UNIQUE,               -- MusicBrainz ID
    UNIQUE (name_norm)
);
CREATE INDEX ON artists USING gin (name_norm gin_trgm_ops);

-- 정규화된 발매(판)
CREATE TABLE releases (
    id              BIGSERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    title_norm      TEXT NOT NULL,
    primary_artist_id BIGINT REFERENCES artists(id),
    label           TEXT,
    catalog_no      TEXT,
    barcode         TEXT,                   -- UPC/EAN. 최우선 병합 키
    format          TEXT,                   -- 'LP','2LP','7INCH','BOXSET'
    variant         TEXT,                   -- 'Clear Vinyl','Limited 300' 등
    is_limited      BOOLEAN NOT NULL DEFAULT FALSE,
    release_date    DATE,                   -- 발매일
    -- ── 일정 알림용 (ADR-0005) ────────────────────────────────
    preorder_opens_at  TIMESTAMPTZ,         -- 예약 시작. 알림 트리거
    preorder_closes_at TIMESTAMPTZ,         -- 예약 마감. 수동 등록만 채울 수 있음
    curation        TEXT NOT NULL DEFAULT 'MANUAL'
                    CHECK (curation IN ('MANUAL','CRAWLED')),
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,  -- 초안은 공개 API 에 노출 안 함
    notes           TEXT,                   -- 운영자 메모 (비공개)
    -- ──────────────────────────────────────────────────────────
    country         TEXT,
    discogs_id      BIGINT,
    cover_url       TEXT,
    master_id       BIGINT REFERENCES releases(id),  -- v1.1 확장용
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ON releases (barcode) WHERE barcode IS NOT NULL;
CREATE INDEX ON releases USING gin (title_norm gin_trgm_ops);
CREATE INDEX ON releases (release_date DESC NULLS LAST);

CREATE TABLE release_artists (
    release_id BIGINT REFERENCES releases(id) ON DELETE CASCADE,
    artist_id  BIGINT REFERENCES artists(id)  ON DELETE CASCADE,
    role       TEXT NOT NULL DEFAULT 'primary',
    PRIMARY KEY (release_id, artist_id, role)
);

-- 구매 링크 (수동 등록용, ADR-0005)
-- listings 를 재활용하지 않는 이유: source_item_id·content_hash 가 NOT NULL 이며
-- 수동 등록에는 존재하지 않는 값이다. 제약을 느슨하게 하면 크롤 경로의 불변식이 약해진다.
CREATE TABLE release_links (
    id         BIGSERIAL PRIMARY KEY,
    release_id BIGINT NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    source_id  TEXT REFERENCES sources(id),   -- 등록된 소스면 연결, 아니면 NULL
    shop_name  TEXT NOT NULL,                 -- 소스 미등록 판매처도 자유 입력
    url        TEXT NOT NULL,
    price_krw  NUMERIC(12,0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (release_id, url)
);
CREATE INDEX ON release_links (release_id);

-- 판매처별 상품 (**크롤 산출물 전용**. 수동 등록은 release_links 를 쓴다)
CREATE TABLE listings (
    id               BIGSERIAL PRIMARY KEY,
    source_id        TEXT NOT NULL REFERENCES sources(id),
    source_item_id   TEXT NOT NULL,
    url              TEXT NOT NULL,
    release_id       BIGINT REFERENCES releases(id),   -- 병합 전에는 NULL
    title_raw        TEXT NOT NULL,
    artist_raw       TEXT,
    label_raw        TEXT,
    price_krw        NUMERIC(12,0),
    stock_status     TEXT NOT NULL,
    format_raw       TEXT,
    release_date_raw TEXT,
    thumbnail_url    TEXT,
    extra            JSONB NOT NULL DEFAULT '{}',
    content_hash     TEXT NOT NULL,
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, source_item_id)
);
CREATE INDEX ON listings (release_id);
CREATE INDEX ON listings (first_seen_at DESC);
CREATE INDEX ON listings (stock_status) WHERE stock_status IN ('PREORDER','IN_STOCK');

-- 상태 변화 이벤트 (알림의 원천)
CREATE TABLE listing_events (
    id           BIGSERIAL PRIMARY KEY,
    -- 수동 등록 일정에서 나온 이벤트는 listing 이 없다 (ADR-0005). release_id 가 주 앵커다.
    listing_id   BIGINT REFERENCES listings(id) ON DELETE CASCADE,
    release_id   BIGINT REFERENCES releases(id),
    event_type   TEXT NOT NULL CHECK (event_type IN
                 -- 시각 기반 (수동 등록, ADR-0005)
                 ('SCHEDULE_ADDED','SCHEDULE_CHANGED',
                  'PREORDER_OPENS_SOON','PREORDER_OPEN','RELEASED',
                 -- diff 기반 (자동 수집, M3)
                  'NEW_LISTING','RESTOCK','SOLD_OUT',
                  'PRICE_DROP','PRICE_RISE','DELISTED')),
    CHECK (listing_id IS NOT NULL OR release_id IS NOT NULL),
    old_value    JSONB,
    new_value    JSONB,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 일정이 바뀌어 역할을 잃은 이벤트 (T-119). 지우지 않고 표시한다 —
    -- 이 행은 구독자에게 보낸 기록이고 notification_deliveries 가 참조한다.
    superseded_at TIMESTAMPTZ
);
CREATE INDEX ON listing_events (occurred_at DESC);
CREATE INDEX ON listing_events (release_id, occurred_at DESC);
-- 피드와 멱등성 판정이 모두 "무효화되지 않은 것"만 훑는다.
CREATE INDEX ON listing_events (release_id, occurred_at DESC) WHERE superseded_at IS NULL;

-- 병합 검토 큐 (신뢰도 중간 구간)
CREATE TABLE merge_candidates (
    id            BIGSERIAL PRIMARY KEY,
    listing_id    BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    release_id    BIGINT NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    score         REAL NOT NULL,
    method        TEXT NOT NULL,
    resolved      BOOLEAN NOT NULL DEFAULT FALSE,
    resolution    TEXT,                     -- 'ACCEPTED' | 'REJECTED'
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 사용자 및 워치리스트
CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT UNIQUE,
    apple_sub     TEXT UNIQUE,              -- Sign in with Apple
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE watchlist_items (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL CHECK (target_type IN ('ARTIST','LABEL','RELEASE','KEYWORD')),
    target_ref  TEXT NOT NULL,              -- artist_id / label명 / release_id / 키워드
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, target_type, target_ref)
);

-- 푸시 구독 (ADR-0006)
-- token 은 플랫폼마다 의미가 다르다 — WEB 이면 푸시 엔드포인트 URL, IOS 면 APNs 토큰.
CREATE TABLE device_tokens (
    id          BIGSERIAL PRIMARY KEY,
    -- Web Push 는 구독 자체가 식별자라 계정이 필요 없다. 계정 시스템(M4) 전까지 NULL.
    user_id     BIGINT REFERENCES users(id) ON DELETE CASCADE,
    platform    TEXT NOT NULL CHECK (platform IN ('IOS','WEB')),
    token       TEXT NOT NULL,
    p256dh      TEXT,                     -- Web Push 구독 공개키 (RFC 8291)
    auth        TEXT,                     -- Web Push 인증 시크릿
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    failure_count   INT NOT NULL DEFAULT 0,
    last_success_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, token)
);

-- 배송 행 중복을 막는 기록. 외부 푸시 전송과 DB 커밋의 원자성까지 보장하지는 않는다.
CREATE TABLE notification_deliveries (
    id              BIGSERIAL PRIMARY KEY,
    event_id        BIGINT NOT NULL REFERENCES listing_events(id) ON DELETE CASCADE,
    device_token_id BIGINT NOT NULL REFERENCES device_tokens(id)  ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','SENT','FAILED','EXPIRED')),
    attempts        INT NOT NULL DEFAULT 0,
    last_error      TEXT,
    sent_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, device_token_id)
);
CREATE INDEX ON notification_deliveries (status, created_at);
```

### 4.3 정규화 규칙 (`normalize()`)

> 정규화 확장 계획이다. 현재 수동 입력은 admin.normalize_name의 NFKC·casefold·공백 축약만 사용하며 별칭/포맷 파서는 없다.

정규화 함수는 병합 정확도를 좌우하는 핵심입니다. **결정론적(deterministic)** 이어야 하며, 단위 테스트로 전 규칙을 검증합니다.

```
1. Unicode NFKC 정규화
2. 소문자 변환
3. 부가 표기 제거 (정규식):
   [LP] [2LP] (LP) (Vinyl) (한정반) (Limited) (Deluxe Edition)
   (Remastered) (Reissue) (Color Vinyl) (Clear) (180g) [수입] [국내반]
   → 단, 제거한 토큰은 `variant` 후보로 별도 보관한다
4. 구두점·특수문자 제거 → 공백 1개로 치환
5. 연속 공백 축약, 양끝 트림
6. 아티스트 별칭 사전 적용:
   "실리카겔" ↔ "Silica Gel", "새소년" ↔ "SE SO NEON",
   "검정치마" ↔ "The Black Skirts" 등 → alias 테이블(seed 데이터)로 관리
7. "The " 접두어 제거 (아티스트명에 한함)
```

**포맷 파싱 규칙:**

| 원문 패턴 | 정규화 결과 |
|---|---|
| `LP`, `1LP`, `Vinyl` | `LP` |
| `2LP`, `Double LP`, `2xLP` | `2LP` |
| `7"`, `7인치`, `7 inch` | `7INCH` |
| `LP+CD`, `LP & CD` | `LP_CD` |
| `Box`, `박스세트` | `BOXSET` |

### 4.4 개체 병합 알고리즘 (EntityResolver)

> EntityResolver와 병합 CLI는 미구현이다. 아래 규칙은 보류된 설계안이며 실행 정책이 아니다.

신뢰도 순으로 단계적 적용하며, **먼저 매칭되는 단계에서 종료**합니다.

| 단계 | 조건 | 신뢰도 | 처리 |
|---|---|---|---|
| S1 | `barcode` 완전 일치 | 1.00 | 즉시 병합 |
| S2 | `catalog_no` 일치 AND `label_norm` 일치 | 0.95 | 즉시 병합 |
| S3 | `artist_norm` 일치 AND `title_norm` 유사도 ≥ 0.90 AND `variant` 일치 AND 발매연도 차이 ≤ 1 | 0.88 | 즉시 병합 |
| S4 | 위 조건에서 유사도 0.70~0.90 | 0.60~0.88 | `merge_candidates` 적재 후 **보류** |
| S5 | 매칭 없음 | — | 신규 `release` 생성 |

**주의사항 (에이전트 필독):**
- `variant`가 다르면 (예: 블랙 vs 클리어) **절대 병합하지 않습니다.** 수집가에게 이는 서로 다른 상품입니다.
- 병합은 되돌릴 수 있어야 합니다. `listings.release_id`만 변경하며 `listings` 행을 삭제하지 않습니다.
- 재현율보다 **정밀도를 우선**합니다. 잘못된 병합은 잘못된 미병합보다 사용자 신뢰를 크게 훼손합니다.

### 4.5 이벤트 감지 규칙 (EventDetector)

직전 `listings` 상태와 신규 `RawItem`을 비교합니다.

| 조건 | 생성 이벤트 |
|---|---|
| `listings`에 `source_item_id`가 없음 | `NEW_LISTING` |
| `stock_status`: `COMING_SOON`/`UNKNOWN` → `PREORDER` | `PREORDER_OPEN` |
| `stock_status`: `SOLD_OUT` → `IN_STOCK` | `RESTOCK` |
| `stock_status`: `IN_STOCK`/`PREORDER` → `SOLD_OUT` | `SOLD_OUT` |
| `price_krw` 5% 이상 하락 | `PRICE_DROP` |
| `price_krw` 5% 이상 상승 | `PRICE_RISE` |
| 3회 연속 크롤에서 URL 404/미발견 | `DELISTED` |

우선순위 큐·일일 요약은 미구현이다. 현재 M2는 모든 알림 대상 이벤트를 같은 60초 tick에서 처리하며,
PENDING을 FAILED 재시도보다 먼저, 배송 생성 시각/ID 오름차순으로 최대 500건 처리한다.

> 위 표는 **자동 수집(M3)** 이 붙은 뒤의 diff 규칙입니다. 현재(M2)는 운영자가 시각을
> 직접 입력하므로 diff 엔진이 필요 없고, 아래 시각 기반 규칙만 동작합니다.

#### 4.5.1 시각 기반 이벤트 (M2, 현재)

스케줄러가 60초마다 "지금 시점에서 나왔어야 할 이벤트가 아직 없는가"를 묻고 채웁니다.

| 조건 | 생성 이벤트 |
|---|---|
| 운영자가 일정을 공개함 | `SCHEDULE_ADDED` |
| **공개된 일정의 시각이 수정됨** | `SCHEDULE_CHANGED` |
| `preorder_opens_at` 이 24시간 안쪽으로 들어옴 | `PREORDER_OPENS_SOON` |
| `preorder_opens_at` 이 지남 | `PREORDER_OPEN` |
| `release_date` 가 됨 | `RELEASED` |

멱등성은 **이벤트의 존재**로 판정합니다 — `is_published` 같은 가변 상태로 판정하면
공개를 껐다 켤 때 알림이 두 번 나갑니다.

#### 4.5.2 일정이 바뀌면 옛 이벤트를 무효화한다 (T-119)

공개 취소 상태에서 바꾼 일정도 과거 이벤트를 무효화한다. 발매 자체를 승인하에 삭제하는 경우에는
예외로 그 발매의 이벤트와 배송도 삭제한다 (§5.2-1).

예약 시각이 17:00 → 19:00 으로 미뤄지면, 17:00 에서 나온 `PREORDER_OPENS_SOON` 과
`PREORDER_OPEN` 은 **역할을 잃습니다.** 그대로 두면 두 가지가 동시에 깨집니다.

1. 피드에 옛 시각을 말하는 알림이 남아, 어느 쪽을 믿어야 할지 알 수 없습니다
2. 멱등성 판정이 "이미 보냈다"로 세어, **19:00 에 예약 시작 알림이 안 나갑니다** —
   이 제품이 유일하게 놓치면 안 되는 순간입니다

그래서 `superseded_at` 에 표시합니다. **일정 수정 시에는 지우지 않습니다** — 그 행은 구독자에게 실제로
보낸 기록이고 `notification_deliveries` 가 참조합니다. 보낸 사실은 취소되지 않습니다.

| 바뀐 필드 | 무효화되는 이벤트 |
|---|---|
| `preorder_opens_at` | `PREORDER_OPENS_SOON`, `PREORDER_OPEN` |
| `release_date` | `RELEASED` |
| `preorder_closes_at` | (없음 — 이 시각에 걸린 이벤트가 없습니다) |

**영향받는 것만 무효화합니다.** 예약 마감만 고쳤는데 `PREORDER_OPEN` 까지 무효화하면
같은 알림이 이유 없이 두 번 나갑니다. `SCHEDULE_ADDED` 는 무효화하지 않습니다 —
일정이 등록되었다는 사실은 시각이 바뀌어도 그대로입니다.

#### 4.5.3 웹 피드·RSS·기기 알림의 구분

- `/v1/feed`: 이벤트 유무와 무관하게 공개 음반당 한 줄. SQL에서 정렬 후 limit을 적용한다.
  기본 `sort=imminent`는 예약 시작(없으면 KST 자정 발매일) 기준 미래 임박순 → 지난 일정 최신순 → 미정 순이다.
  `sort=recent`는 `updated_at` 내림차순이며 화면 라벨은 **최근 변경순**이다.
- 웹 오른쪽에는 예약 시작 또는 발매일만 표시한다. `FeedItem.at`은 API 내부 이벤트/일정 시각이며
  웹 표시의 기준이 아니다. 상태는 렌더링 시점에 예약 예정·진행 중·마감 또는 발매 예정·발매됨·일정 미정으로 계산한다.
- RSS는 `latest_event_per_release()`로 공개 음반당 최신 비무효 이벤트를 최대 50개 선택한다.
  `/v1/feed`도 최신 이벤트를 붙일 때 이 도우미를 쓰지만 음반 선택·정렬 쿼리는 별도다.
- 푸시 `tag`는 `release-<id>-<event_type>`이다. 서로 다른 이벤트는 별개 알림으로 남고,
  같은 이벤트 종류가 일정 변경으로 재발생하면 이전 알림을 교체한다.

---

## 5. API 설계

### 5.1 현재 계약

- 아래 표는 실제 라우터 기준이다. 정확한 스키마는 `make openapi`로 생성하는 [openapi.json](api/openapi.json)을 본다.
- 공개 조회와 Web Push 구독에는 계정 인증이 없다. 운영자 JSON API는 `X-Admin-Key`를 요구한다.
  `/admin` HTML 자체는 로그인 화면을 제공하며 OpenAPI에 포함하지 않는다.
- `/v1/releases`만 커서 페이지네이션(`limit` 기본 20, 1~100)을 지원한다.
  예약 시작 오름차순·NULL 마지막·ID 오름차순이며, 지난 일정을 자동 제외하지 않는다.
- API 목록 `/v1/releases`, `/v1/feed`는 ETag와 60초 캐시 헤더를 제공한다.
  RSS는 300초, ICS는 600초다. 웹의 API 조회와 같은 출처 중계 응답은 `no-store`다.
- JSON은 snake_case, 시간은 타임존 포함 UTC, 가격은 원화 정수다. 오류는 RFC 9457 Problem Details를 사용한다.
  웹 중계의 자체 오류는 `{detail: ...}` JSON일 수 있다.

### 5.2 구현된 공개 엔드포인트

| 메서드 | 경로 | 현재 동작 |
|---|---|---|
| GET | `/v1/feed` | 공개 음반당 한 줄. `sort=imminent|recent`, `limit` 기본 50·최대 100, 커서 없음 |
| GET | `/v1/releases` | 공개 목록. `cursor`, `limit`, `from`, `to`, `format`, `is_limited`. 날짜 필터는 발매일 기준 |
| GET | `/v1/releases/{release_id}` | 공개 상세와 구매 `links`. `artist_name`은 문자열; `listings`·`recent_events` 없음 |
| GET | `/v1/feed.rss` | 최신 이벤트 RSS 2.0 |
| GET | `/v1/releases.ics` | 예약 시작 30분 블록과 30분 전 알람. `include_release_dates` 기본 true로 발매일 종일 일정 포함 |
| GET | `/v1/push/public-key` | VAPID 공개키와 enabled |
| POST | `/v1/push/subscribe` | 익명 구독 생성/갱신. 재활성화에도 정원 검사 |
| DELETE | `/v1/push/subscribe` | endpoint 구독 비활성화, 이력 보존 |
| GET | `/healthz` | DB 연결까지 확인, 성공 200·DB 실패 503 |

FastAPI 기본 문서 `/docs`, `/redoc`, `/openapi.json`은 API 포트에서 제공한다.
검색·아티스트·이벤트 스트림·소스 목록·워치리스트·계정·APNs 기기·`/metrics` 라우터는 **미구현**이다.
Funnel 웹 도메인은 모든 API 경로를 공개하지 않는다. 푸시는 `/api/push/*`, RSS/ICS는 같은 `/v1/*` 경로로만 중계한다.

### 5.2-1 운영자 API

| 메서드 | 경로 | 현재 동작 |
|---|---|---|
| GET | `/admin` | 키 검증 전 본문을 감추는 로그인/등록/편집 화면 |
| GET | `/admin/releases` | 초안 포함 전체 목록 |
| GET | `/admin/releases/{release_id}` | 초안 포함 상세와 notes, can_delete |
| POST | `/admin/releases` | 초안 생성, 구매처 함께 등록 |
| PATCH | `/admin/releases/{release_id}` | 보낸 필드만 변경. links 생략은 유지, 배열은 전체 대체. 일정·구매처 원자적 저장 |
| POST | `/admin/releases/{release_id}/publish` | 공개하고 최초 SCHEDULE_ADDED 생성 |
| POST | `/admin/releases/{release_id}/unpublish` | 공개 취소, 이벤트 이력 유지 |
| DELETE | `/admin/releases/{release_id}` | 비공개 음반 삭제. 과거 공개 이력 허용, 연결 listings가 있으면 거부. 이벤트·배송은 함께 삭제 |
| POST | `/admin/releases/{release_id}/links` | 구매처 추가 |
| DELETE | `/admin/releases/{release_id}/links/{link_id}` | 해당 음반의 구매처 삭제 |

`can_delete`는 비공개이고 연결된 listings가 없을 때 true다. 다른 FK 참조가 있으면 실제 삭제는 409일 수 있다.
공개 API에는 notes가 없고 비공개 상세는 404다. 입력에서 공백/null 제목, null is_limited,
타임존 없는 시각, 잘못된 예약 창·URL·원화 범위를 거부한다.

### 5.2-2 실행 시 보장 사항 (2026-09-10 점검)

- 이벤트 생성 백필 상한은 7일, 배송 대상은 이벤트 발생 후 48시간이다. 예약 임박은 시작 전 24시간 이내에서만 생성한다.
- 배송은 활성 WEB 구독에만 계획하고 구독 이전 이벤트는 제외한다. 재활성화 시 구독 시작 시각을 갱신한다.

- 운영자 PATCH의 `links`는 생략하면 유지, 배열이면 전체 구매처 목록을 대체한다. 일정과 구매처는 한 트랜잭션에서 저장하고, 커밋 실패는 성공 응답으로 반환하지 않는다.
- 실패한 푸시는 최대 3회 시도한다. 배송 생성 1분·5분 이후 재시도하며, 매 회차 공개 여부·구독 활성 여부·이벤트 무효화·48시간 발송 기한을 재검사한다. 스케줄러 프로세스 간 중복 실행은 DB 잠금으로 막는다.
- 공개 취소 중 일정을 수정해도 이전 시각의 이벤트를 무효화한다. 재공개 후 새 시각의 이벤트가 생성될 수 있어야 한다.
- 발매일 기준은 KST 자정이다. 예약 캘린더 블록은 날짜 경계를 넘어도 30분이며, 웹 캘린더는 API의 모든 페이지를 조회한다.
- RSS·iCalendar는 공개 웹 도메인의 `/v1/feed.rss`, `/v1/releases.ics`를 통해 제공한다. 구독 주소는 실행 시 `PUBLIC_WEB_URL`을 사용한다.
- 외부 푸시 전송 성공과 DB 커밋 사이에 프로세스가 종료되면 중복 전송 가능성이 남는다. `SENT`는 푸시 서비스 수락이며, 기기 표시 확인을 의미하지 않는다.

### 5.3 공개 상세 응답 예시

다음은 현재 `ReleaseOut` 구조의 설명용 예시이며 실제 DB 행을 의미하지 않는다.

```json
{
  "id": 1042,
  "title": "Machine Boy",
  "artist_name": "실리카겔",
  "label": "Magic Strawberry Sound",
  "format": "2LP",
  "variant": "Clear Vinyl",
  "is_limited": true,
  "release_date": "2026-09-12",
  "preorder_opens_at": "2026-09-11T04:00:00Z",
  "preorder_closes_at": "2026-09-13T09:00:00Z",
  "cover_url": null,
  "curation": "MANUAL",
  "is_published": true,
  "links": [
    {
      "id": 1,
      "source_id": "gimbab",
      "shop_name": "김밥레코즈",
      "url": "https://example.com/release/1042",
      "price_krw": 58000
    }
  ]
}
```

---

## 6. 리포지토리 구조

아래는 현재 존재하는 주요 경로다. 파일명 중괄호는 같은 디렉터리의 파일들을 줄여 쓴 것이다.

```text
AGENTS.md / CLAUDE.md / README.md
compose.yaml / compose.prod.yaml / Makefile / .env.example
.vscode/{settings,extensions}.json
apps/
  api/
    src/orot_api/
      main.py / deps.py
      routers/{admin,admin_ui,releases,feed,rss,calendar,push}.py
      schemas/{release,push}.py
      feed_query.py / serializers.py / pagination.py / caching.py
      problems.py / request_limits.py / rate_limit.py / rss.py / icalendar.py
    tests/                         # integration_runtime.py + test_*.py
    pyproject.toml / Dockerfile
  collector/
    src/orot_collector/
      cli.py / scheduler.py / push_sender.py / slack_alerter.py / fetcher.py / bridge.py
    tests/fixtures/<source_id>/*.html
    pyproject.toml / Dockerfile
  web/
    app/
      page.tsx / calendar/page.tsx / releases/[id]/page.tsx
      subscribe/{page,PushToggle}.tsx / layout.tsx / globals.css / manifest.ts
      api/push/{public-key,subscribe}/route.ts
      v1/{feed.rss,releases.ics}/route.ts
    lib/{api,proxy,push,push-request,feed-display,calendar,format}.ts
    public/sw.js / public/*.png
    tests/*.test.mjs
    package.json / package-lock.json / next.config.ts / Dockerfile
packages/core/
  src/orot_core/
    models/{base,artist,release,listing,source,user}.py
    adapters/{base,registry,gimbab,secondtrack,poclanos}.py
    db.py / settings.py / seed.py / enums.py / logging.py / testing.py
    schedule_events.py / notifications.py / alerts.py
  tests/ / pyproject.toml
migrations/versions/ / alembic.ini
infra/{env-backup,env-restore,orot-start,orot-backup}.sh
docs/{BLUEPRINT.ko,BLUEPRINT.en}.md / docs/{adapters,adr}/
docs/api/openapi.json / docs/{security-review,runtime-review,documentation-review}.md
.github/workflows/ci.yml            # T-012 Python + web verification
backups/                           # ignored runtime artifacts
venv/                              # ignored local Python environment
```

**계획 경로**: `apps/ios/`, `apps/api/src/orot_api/services/`, collector의 `pipeline.py`,
core의 `normalize.py`·`resolver.py`·`events.py`·`aliases.yaml`, 웹 검색·아티스트·워치리스트,
`infra/nginx/`·`infra/prometheus/`·`infra/deploy.sh`, `.devcontainer/`는 현재 없다.
이 경로들은 향후 작업을 위한 예약이며, 이 표만으로 구현·활성화하지 않는다.

---

## 7. 웹 프론트엔드

### 7.1 구현된 화면

| 화면 | 경로 | 현재 내용 |
|---|---|---|
| 피드 | `/` | 공개 음반당 한 줄, 최근 변경순/발매 임박순, 예약/발매 상태와 시작 시각, 구매 링크 |
| 캘린더 | `/calendar?month=YYYY-MM` | KST 기준 예약 시작·발매일, 모든 API 페이지 조회 |
| 상세 | `/releases/[id]` | 제목·아티스트·포맷·예약 창·발매일·구매처 링크 |
| 구독 | `/subscribe` | Web Push 켜기/끄기, 공개 RSS·ICS 주소 |

검색·아티스트·워치리스트 화면은 없다. `cover_url`은 API 필드로 지원하지만 현재 웹에서 커버 이미지를 렌더링하지 않는다.

### 7.2 표시와 PWA

- 상태는 텍스트 배지로 표시한다. 정보 밀도를 유지하고 시스템 다크 모드를 지원한다.
- 피드·캘린더·상세·구독 화면은 동적으로 렌더링한다. 피드 상태는 페이지 렌더링 시 계산하며 실시간 자동 갱신 타이머는 없다.
- `manifest.ts`, PWA 아이콘, `sw.js`가 있다. 서비스워커는 설치 시 활성화하고 푸시·클릭·구독 교체를 처리하며, 오프라인 콘텐츠 캐시는 없다.
- iPhone 테스트 흐름은 Safari에서 홈 화면에 추가한 앱으로 실행해 권한을 허용하는 것이다. 실제 수신·표시는 실기기에서 확인한다.

### 7.3 API 클라이언트와 환경 변수

`apps/web/lib/api.ts`는 서버용 fetch 도우미와 **수기 TypeScript 타입**이다.
생성 클라이언트·`api-types.ts`·openapi-typescript는 없으며 생성 도입은 향후 작업이다.
`make openapi`는 API 계약 스냅샷만 생성한다.

- `API_BASE_URL`: 웹 서버가 사용하는 내부 API 주소 (Compose에서는 `http://api:8000`).
- `PUBLIC_WEB_URL`: api·collector·web이 링크를 만들 때 사용하는 브라우저 접근 가능한 공개 웹 주소.
  `/subscribe`는 실행 시 이 값을 읽는다. `PUBLIC_API_URL`은 현재 사용하지 않는다.
- 브라우저와 서비스워커는 같은 출처의 푸시 경로를 사용한다. API에 CORS 미들웨어는 없다.
- 각 API 요청은 10초 제한·no-store를 적용한다. 공개 RSS·ICS는 고정 경로 중계로 제공한다.

---

## 8. iOS 네이티브 애플리케이션 (M5 이후 계획)

> 이 절은 미구현 네이티브 앱 설계안이다. `apps/ios`·Swift 모델·APNs·JWT·SwiftData는 없다.
> 현재 iPhone 알림은 PWA Web Push이며, 네이티브 앱이나 Apple 로그인은 현재 서비스의 필수 조건이 아니다.
> 아래 플랫폼·심사 관련 비교는 당시 계획 배경이며, 네이티브 착수 시 다시 확인한다.

### 8.1 구현 방식 선택 — 검토와 권고

| 방식 | 장점 | 단점 | 평가 |
|---|---|---|---|
| **A. WKWebView 래퍼** | 개발 1~2일. 웹 코드 100% 재사용 | App Store 심사 가이드라인 **4.2 (Minimum Functionality)** 로 반려될 위험이 실질적으로 존재. 푸시 알림·햅틱·오프라인 캐시 등 네이티브 경험 부재. 스크롤 감각이 즉시 “웹”으로 인지됨 | 비권장 |
| **B. 네이티브 SwiftUI + 공용 REST API** | 진정한 네이티브 UX. 푸시·위젯·Live Activity·Spotlight 연동 가능. OpenAPI로 클라이언트 자동 생성 | 화면을 별도 구현해야 함 | **권고** |
| C. 하이브리드 (네이티브 셸 + 일부 화면 웹뷰) | 절충 | 두 스택의 단점을 모두 상속. 유지보수 복잡도 증가 | 조건부 |

**권고**: **B안(네이티브 SwiftUI)** 을 채택합니다. 근거는 다음과 같습니다.

1. 사용자께서 명시한 목표가 “**더 사용자 친화적인** iOS 앱”입니다. 웹뷰 래퍼는 정의상 웹보다 친화적일 수 없습니다.
2. 이 서비스의 핵심 가치는 **푸시 알림**(예약판매 오픈 즉시 통지)입니다. 현재는 Web Push로 제공하며, 네이티브 통합은 앱 고유 기능을 위한 향후 선택입니다.
3. API 우선 설계이므로 웹과 iOS가 동일한 계약을 공유하며, 웹 작업이 낭비되지 않습니다. “웹을 만들고 이를 활용”한다는 의도는 **UI 코드 재사용이 아니라 API·도메인 모델 재사용**으로 달성됩니다.

다만 반대 논거도 명시합니다. 학습·포트폴리오 목적에서 iOS를 빠르게 배포해 보는 것이 우선이라면, A안으로 먼저 출시한 뒤 화면 단위로 네이티브 전환하는 경로도 합리적입니다. 이 경우 최소한 **푸시 알림·설정 화면·탭바는 네이티브로 구현**해야 4.2 리스크를 낮출 수 있습니다.

### 8.2 네이티브 앱 구조

```
OROT/
├─ OROTApp.swift              @main, DI 컨테이너
├─ Core/
│  ├─ APIClient.swift               URLSession + async/await
│  ├─ Generated/                    swift-openapi-generator 산출물
│  ├─ Models/
│  ├─ KeychainStore.swift           JWT 저장
│  └─ DesignSystem/                 Color, Typography, Badge
├─ Features/
│  ├─ Feed/          FeedView, FeedViewModel (@Observable)
│  ├─ Search/
│  ├─ ReleaseDetail/
│  ├─ Watchlist/
│  └─ Settings/
├─ Notifications/
│  ├─ PushRegistrar.swift           UNUserNotificationCenter + APNs 토큰 등록
│  └─ NotificationHandler.swift     딥링크 → ReleaseDetail
└─ Widgets/                         v1.1: 이번 주 발매 위젯
```

**주요 결정사항**
- 최소 지원: iOS 17.0 (`@Observable` 매크로 사용 가능)
- 아키텍처: MVVM. `@Observable` ViewModel + SwiftUI `NavigationStack`
- 네트워킹: [`swift-openapi-generator`](https://github.com/apple/swift-openapi-generator) 로 `openapi.json` → Swift 클라이언트 자동 생성. **수기 모델 정의 금지**
- 인증: Sign in with Apple (계정 생성 마찰 최소화, App Store 요구사항 충족)
- 이미지: `AsyncImage` + `NSCache` 메모리 캐시. 원본 URL 직접 로드
- 오프라인: SwiftData로 최근 피드 200건 캐시

### 8.3 푸시 알림 파이프라인

```
EventDetector → PREORDER_OPEN 이벤트 생성
   ↓
watchlist_items 매칭 쿼리 (ARTIST/LABEL/RELEASE/KEYWORD)
   ↓
NotificationDispatcher (FastAPI 백그라운드 태스크)
   ↓
aioapns → APNs (token-based auth, .p8 키)
   ↓
iOS: NotificationHandler → 딥링크 orot://release/1042
```

**필요 사항**: Apple Developer Program 연 $99 USD, APNs Auth Key(.p8), Bundle ID, Push Notifications Capability.

### 8.4 VSCode와 Xcode의 역할 분담 (중요)

VSCode를 주 IDE로 사용하시되, iOS 부분에는 제약이 있음을 명확히 밝힙니다.

| 작업 | VSCode | Xcode |
|---|---|---|
| Python/TypeScript 전체 | ✅ 가능 | 불필요 |
| Swift 코드 편집 | ✅ 가능 (Swift 확장 + SourceKit-LSP) | 가능 |
| SwiftUI 프리뷰 | ❌ 불가 | ✅ 필수 |
| 시뮬레이터 실행·디버깅 | ❌ 불가 | ✅ 필수 |
| 코드 서명·프로비저닝·아카이브 | ❌ 불가 | ✅ 필수 |
| App Store Connect 업로드 | ❌ 불가 | ✅ 필수 |

**결론**: 백엔드·웹은 VSCode, iOS는 Xcode를 병행하십시오. Claude Code는 VSCode 터미널에서 실행하되 `apps/ios/` 디렉터리의 Swift 파일도 편집할 수 있으며, 빌드 검증만 Xcode에서 수행하는 방식이 실용적입니다. (`xcodebuild` CLI로 VSCode 터미널에서 빌드는 가능하나, 프리뷰와 시각적 디버깅은 대체 불가합니다.)

---

## 9. 개발 환경 및 운영

### 9.1 현재 실행 방법

Docker 엔진과 Compose가 필요하다. macOS 테스트 환경은 colima를 사용한다.

```bash
# 새 환경에서만 실행; 기존 .env를 덮어쓰지 않는다.
cp -n .env.example .env
# .env의 ADMIN_API_KEY를 설정한다. 공개 테스트에서는 32자 이상의 비밀 키를 사용한다.
make up          # 개발 웹 + API + collector + PostgreSQL
make migrate     # 최초 실행 또는 새 DB 마이그레이션이 있을 때
make seed        # sources만 시드; 별칭은 미구현
```

`make prod`는 `compose.yaml`과 `compose.prod.yaml`을 합쳐 빌드·기동한다.
현재는 Mac mini에서 테스트를 위해 이 모드를 사용하며 EC2 배포 명령이 아니다.

| 항목 | 개발 `make up` | 공개 테스트 `make prod` |
|---|---|---|
| 웹 | next dev, 소스 마운트 | 빌드 이미지 + next start, 웹 마운트 제거 |
| API | 소스 마운트 + uvicorn --reload | 동일한 마운트/--reload 유지, ENVIRONMENT=production |
| collector | 소스 마운트, scheduler 실행, 자동 리로드 없음 | 동일, ENVIRONMENT=production |
| DB·포트 | postgres_data 볼륨, 5432/8000/3000 loopback 바인딩 | 동일 |

API Python 편집은 리로드된다. collector Python 편집은 `docker compose restart collector`가 필요하다.
production 웹 편집과 의존성 변경은 재빌드한다. `.env`/Compose 환경 변수 변경은 `make prod` 또는
동일 오버레이의 `up -d`로 컨테이너를 재생성해야 한다. `restart`만으로 환경 변수를 바꾸지 못한다.

| 환경 변수 | 소비자·용도 |
|---|---|
| DATABASE_URL | api·collector의 DB 연결 |
| ADMIN_API_KEY | API 인증, api·collector production 설정 검증 |
| API_BASE_URL | 웹 내부 API 호출 (Compose에서 http://api:8000) |
| PUBLIC_WEB_URL | api·collector·web의 공개 링크와 구독 주소 |
| VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_SUBJECT | api 구독 가능 여부, collector Web Push 전송 |
| SLACK_WEBHOOK_URL | collector 운영자 장애 알림; 공백/미설정이면 비활성화 |
| CRAWLER_* | collector 수동 수집 설정; 자동 수집을 활성화하지 않음 |
| ENV_BACKUP_DIR / ENV_BACKUP_KEEP | 호스트의 .env 백업 스크립트 |

`ENVIRONMENT=local`에서는 개발 기본 관리자 키를 허용하되 빈 키는 거부한다. staging/production은
기본 키 또는 32자 미만 키를 거부한다. VAPID 설정이 부족하면 public-key의 enabled=false,
구독 POST는 503이며 발송기는 FAILED를 반환한다. 이를 성공/no-op로 기록하지 않는다.

### 9.2 로컬 도구

`.vscode/settings.json`은 `venv/bin/python`과 Python 테스트 디렉터리를 지정한다.
권장 확장은 `.vscode/extensions.json`에 있다. launch.json·tasks.json·devcontainer는 없다.
Python은 `make install`, 웹 의존성은 `apps/web`에서 `npm ci`로 준비한다.

### 9.3 실제 검증 경로

```bash
make lint
make test
make openapi
cd apps/web
npm run lint
node --test tests/*.test.mjs
npm run build
```

Python 기본 테스트는 fixture·mock·TestClient·SQL 질의 검증 중심이다. testcontainers 기반 자동 DB 기동은 없다.
`apps/api/tests/integration_runtime.py`는 **명시적으로 실행하는** PostgreSQL 통합 검증이다.
가짜 발송기와 독립 스키마를 만들고 전체 롤백하며, 실제 기기로 보내지 않는다. 일반 `make test`에는 포함하지 않으며 CI에서는 별도 단계로 실행한다.
수신 표시 확인이 필요한 `collector test-push`는 실제 발송이며 사용자 승인이 필요하다.

T-012 CI는 아래 로컬 검증과 별도 DB 검증을 자동 실행한다(§9.5). 파서 카나리·커버리지 게이트는 미구현이다. `docs/runtime-review.md`의 테스트 수치는 2026-09-10의 기록이며
매 실행의 최신 결과를 대신하지 않는다. 문서 수정만으로 서비스를 기동하거나 실제 데이터로 삭제 시험을 하지 않는다.

### 9.3-1 백업과 복구

- `make backup`: pg_dump → gzip을 `backups/`에 저장한다. 파이프 실패를 감지하고 실패 파일을 제거한다.
- `make restore FILE=...`: 사용자 확인 후 압축 해제에 성공한 SQL만 psql 단일 트랜잭션으로 적용한다.
  SQL 오류 시 중단한다. 기존 데이터를 덮어쓰므로 승인과 사전 백업이 필요하다. 시험 복구는 별도 DB에서 한다.
- `make backup-prune`: 최근 DB 백업 30개를 남긴다. `infra/orot-backup.sh`는 DB 실행 시
  backup → prune → .env 백업을 실행한다. DB가 꺼져 있으면 건너뛰며 .env 백업 실패는 경고 로그로 남긴다.
- `.env` 암호화는 `infra/env-backup.sh`, 복구는 `infra/env-restore.sh`다. `ENV_BACKUP_DIR` 기본값은
  **프로젝트 내부** backups/env이며 디스크 밖 저장은 별도 설정해야 한다. keep 기본 10개, 키체인 암호 설정은 `make backup-env-setup`이다.
- 저장소에는 LaunchAgent plist나 등록 명령이 없다. 호스트에서의 자동 실행 등록 여부·주기는 별도로 확인한다.
- `down`은 볼륨을 유지하지만 `down -v`·볼륨 삭제·SQL 삭제·디스크 고장을 막지 못한다. 볼륨은 백업이 아니다.

### 9.3-2 Funnel 공개 테스트

```text
인터넷 → Tailscale Funnel → Mac mini의 127.0.0.1:3000
                             → colima/Docker의 web → api:8000 → postgres:5432
```

현재 대화에서 사용한 주소는 `https://jaehyeonui-macmini.tail598a5f.ts.net`이다.
실제 주소·터널 등록 상태는 `tailscale funnel status`로 확인한다. 코드와 DB는 Mac mini에 있다.
웹만 공개하고 API/관리자/DB 포트는 loopback에 둔다. 웹에 범용 API 프록시를 추가하지 않는다.

재부팅 후 `colima start`와 `make prod`로 기동할 수 있다. `infra/orot-start.sh`도
colima 확인 → Compose up → API health 확인을 수행하지만 이미지를 빌드하지 않는다.
Docker의 restart 정책은 Docker 엔진이 떠 있을 때만 유효하며, 호스트 로그인·데몬 자동 기동을 보장하지 않는다.

### 9.4 관측성과 알림 한계

structlog 로그, /healthz의 DB 연결 검사, scheduler.tick, notifications.dispatched,
push.retry_exhausted가 현재 관측 수단이다. `SLACK_WEBHOOK_URL`을 설정하면 스케줄러 주기 오류와
재시도 소진을 Slack으로 알린다([ADR-0008](adr/0008-operator-failure-alerts.md)). 정상 배송 커밋 뒤에
소진을 보고하고, 알림 전송 실패는 배송을 롤백시키지 않는다. 같은 오류 종류는 기본적으로 프로세스당
성공 전송 1회로 억제되어 복구 후 재발도 다시 알리지 않는다. 재시작 시 억제 상태가 초기화된다.
Slack 실패 후 소진 경보를 보존·재전송하는 큐는 없다.
프로세스·호스트 중단 감지, 공통 trace_id·Prometheus 메트릭·Sentry는 없다.
익명 구독에는 URL/키 검증·본문 크기/시간 상한·프로세스 메모리 속도 제한·DB 정원 검사와
웹 동일 출처 검사가 있다 ([보안 점검](security-review.md)). 속도 제한은 다중 API 프로세스 간 공유되지 않는다.

### 9.5 CI/CD 상태

`T-012`의 `.github/workflows/ci.yml`은 모든 PR, main push, 수동 실행을 지원한다.
Python 3.12 작업은 `make install`, `make lint`, `make test` 후 임시 PostgreSQL 16에
`venv/bin/python -m alembic upgrade head`를 적용하고
`venv/bin/python apps/api/tests/integration_runtime.py`로 9개 격리 시나리오와 스키마 롤백을 검증한다.
통합 시나리오는 ORM으로 만든 별도 스키마에서 실행하며, 마이그레이션 결과를 직접 사용하는 검증은 아니다.
Node 22 작업은 `npm ci`, 웹 lint·Node 회귀 테스트·production build를 실행한다.
작업별 제한은 15분이며 같은 ref의 이전 실행은 취소한다. 저장소 권한은 `contents: read`이고
운영 비밀·DB·실제 알림 발송을 사용하지 않는다. GitHub 실행 결과와 필수 체크 지정은 저장소에서 별도 확인한다.
GHCR push·SSH 배포·자동 롤백은 미구현이며 운영 기동은 Compose를 사용한다.

### 9.6 비용과 운영 범위

현재 구현은 소유한 Mac mini의 공개 테스트다. 과거 EC2/Apple 요금표는 현재 청구액이나 검증된 견적이 아니다.
클라우드·네이티브 앱 도입 시 필요한 자원과 당시 요금으로 다시 산정한다.

---

## 10. 작업 백로그

각 태스크는 **독립적으로 완료 판정 가능**하도록 작성되었습니다. 에이전트는 태스크 ID를 명시하며 진행합니다.

> 상태 기준(2026-09-11): M1 경로와 M2의 시각 이벤트·Web Push가 구현되어 있다.
> T-116은 재시도/404·410 비활성화와 **Slack 운영자 알림이 코드에 구현되어 있다**. 실제 수신 설정·결과는 별도 운영 검증 사항이다.
> M3 이후는 계획이며 완료 조건 표가 구현 완료를 뜻하지 않는다. 기존 T-008~T-011 행은 원래 M0 계획의 기록이다.
> T-008/T-009는 미구현 보류, 공개 API/웹 역할은 T-105/T-110으로 구현했다. T-012 CI 워크플로는 구현되어 있으며 GitHub에서의 실행 결과는 별도 확인한다.

### M0 — Walking Skeleton (완료)

> 목표였던 "1개 소스 → DB → API → 화면"은 [ADR-0005](adr/0005-manual-curation-first.md) 로
> 방향이 바뀌어 **수집 부품까지 완료한 상태로 마감**한다.
> 수집 파이프라인 관련 작업은 M3로 미뤘고, 공개 API/웹은 M1에서 수동 일정용으로 구현했다.

| ID | 작업 | 완료 조건 |
|---|---|---|
| T-001 | 모노레포 스캐폴딩, `compose.yaml`, `Makefile`, `.env.example` | `make up` 으로 postgres+api 기동, `/healthz` 200 |
| T-002 | `packages/core` SQLAlchemy 모델 + Alembic 초기 마이그레이션 | `make migrate` 성공, §4.2 모든 테이블 생성 확인 |
| T-003 | `sources` 시드 데이터 (gimbab/secondtrack/poclanos) | `make seed` 후 3행 존재 |
| T-004 | `SourceAdapter` 프로토콜 및 `registry.py` | 어댑터 미구현 상태에서 registry 임포트 성공 |
| T-005 | `fetcher.py`: robots.txt 파싱, 레이트리밋, 조건부 요청, 백오프 | 단위 테스트로 0.5 req/s 준수 검증 |
| T-006 | **김밥레코즈 사이트 조사** → `docs/adapters/gimbab.md` 작성, fixture 3건 저장 | 문서에 robots.txt 전문·셀렉터 표·JS 필요 여부 기재 |
| T-007 | `gimbab.py` 어댑터 구현 | fixture 3건 모두 `RawItem` 파싱 성공, 필드 값 일치 |
| T-008 | `normalize.py` + 단위 테스트 30건 | §4.3 전 규칙 통과 |
| T-009 | `pipeline.py`: RawItem → listings upsert (병합 없이 release 1:1 생성) | `collector run --source gimbab` 후 DB에 행 적재 |
| T-010 | `GET /v1/releases` (커서 페이지네이션) | OpenAPI 문서 노출, 실데이터 반환 |
| T-011 | Next.js 피드 화면 (SSR, 필터 없음) | `localhost:3000` 에서 목록 렌더링 |
| T-012 | GitHub Actions CI (Python·웹·PostgreSQL 통합 검증) | PR/main push에서 두 작업 실행; lint·테스트·마이그레이션·웹 build 실패 시 해당 작업 실패 (§9.5) |
| **M0 마감 범위** | 스캐폴딩·스키마·수집 부품까지 완료. 수집 → DB → 웹 연결은 보류 | |

### M1 — 수동 등록 → 공개 피드 ([ADR-0005](adr/0005-manual-curation-first.md))

> 목표: **운영자가 일정을 등록하면 사용자가 구독할 수 있다.** 자동 수집 없이 핵심 가치를 배송한다.

| ID | 작업 | 완료 조건 |
|---|---|---|
| T-101 | `releases` 일정 컬럼 + `release_links` 테이블 마이그레이션 | `make migrate` 성공, §4.2 DDL 과 일치 |
| T-102 | 운영자 API 인증 (`X-Admin-Key`) | 키 없음/오류 시 401, 정상 키로 통과 |
| T-103 | `POST/PATCH/DELETE /admin/releases` + `/links` | 일정 등록·수정·링크 추가 동작 |
| T-104 | `POST /admin/releases/{id}/publish` | 공개 시 `SCHEDULE_ADDED` 이벤트 1건 생성 |
| T-105 | `GET /v1/releases`, `GET /v1/releases/{id}` (커서 페이지네이션) | **초안 미노출** 검증 포함 |
| T-106 | `GET /v1/feed` — 예약 시작 임박순 타임라인 | 이벤트·일정 혼합 정렬 |
| T-107 | `GET /v1/releases.ics` (iCalendar) | 실제 캘린더 앱에서 구독 확인 |
| T-108 | `GET /v1/feed.rss` (RSS 2.0) | 리더에서 구독 확인 |
| T-109 | 운영자 등록 화면 (웹, 최소 폼) | 브라우저에서 일정 등록 완료 |
| T-110 | 사용자 피드·캘린더 화면 (Next.js SSR) | `localhost:3000` 에서 월간 그리드 렌더링 |

### M2 — 시각 기반 알림

> 목표: **예약 시작 시각에 알림이 도착한다.** 계정 없이 구독 가능한 경로를 먼저 만든다.

| ID | 작업 | 완료 조건 |
|---|---|---|
| T-111 | APScheduler 도입 + `preorder_opens_at` 감시 | 컨테이너 상주, 1분 해상도 로그 확인 |
| T-112 | `PREORDER_OPENS_SOON`(24h 전) / `PREORDER_OPEN` / `RELEASED` 생성 | 시각 조작 테스트로 3종 전부 검증 |
| T-113 | 이벤트 생성 멱등성 | 순차 재실행 시 같은 유효 이벤트가 중복 생성되지 않음 |
| T-114 | **Web Push 구독** (VAPID 키, 구독/해지 API, 스키마 확장) — [ADR-0006](adr/0006-web-push-first.md) | 브라우저가 구독하고 DB 에 저장됨 |
| T-115 | 배송 기록·중복 처리 방지 | 커밋된 SENT 재처리 없음. 전송/커밋 사이 장애의 중복 가능성은 §5.2-2 참조 |
| T-116 | 재시도 + 만료 구독 정리 + **Slack 운영자 알림** | 의도적 실패 시 Slack 수신, 410 이면 구독 비활성화 |
| T-117 | 웹 구독 UI (PWA 매니페스트 + 서비스워커) — [ADR-0007](adr/0007-same-origin-push-proxy.md) | 실제 기기에서 알림 수신 |
| T-118 | 피드 접기(발매당 최신 1건) + `SCHEDULE_CHANGED` (§4.5.1, §4.5.3) | 같은 앨범이 피드에 한 줄만, 일정 수정 시 알림 발송 |
| T-119 | 일정 변동 시 옛 이벤트 무효화·재발송 (§4.5.2) | 예약 시각을 미루면 **새 시각에** 예약 시작 알림이 다시 나감 |
| T-120 | 상시 운영 준비 (포트 바인딩·운영자 키·production 빌드·백업 자동화) | 재부팅 후 수동 2줄로 복구, `.env` 암호화 백업이 디스크 밖에 |
| T-130 | 공개 노출 대비 보안 강화 ([`docs/security-review.md`](security-review.md)) | 인증 없이 SSRF·500·XSS 를 만들 수 없음 |
| T-131 | 알림 `tag` 를 이벤트 단위로 | 서로 다른 알림이 기기 목록에서 서로를 지우지 않음 |
| T-132 | 피드 `sort=recent` 를 `updated_at` 기준으로 | 일정을 수정하면 맨 위로 올라옴 |
| T-133 | 초안 삭제 허용 (공개 취소 → 삭제) | SQL 없이 화면에서 지울 수 있고, 공개 중인 것은 막힘 |
| T-134 | 관리 화면 로그인 | 키 확인 전에는 본문이 열리지 않고, 이후 재입력 불필요 |

> **알림 채널은 Web Push 우선** ([ADR-0006](adr/0006-web-push-first.md)). 이메일은 만들지 않는다.
> §8.3 의 APNs 는 폐기가 아니라 **iOS 앱 배포 시점으로 미룬 것**이다.
> T-113 이 검증한 것은 **이벤트 생성** 멱등성이며, **발송** 중복 방지는 T-115의 배송 기록과 잠금으로 수행하되, 전송/커밋 사이의 장애까지 exactly-once를 보장하지 않는다.

### M3 — 자동 수집 재개

> 목표: 잠들어 있던 수집 부품을 배선한다. 수동 등록과 **병존**한다 (`curation` 으로 구분).
> **착수 조건**: 운영자 수동 등록이 병목이라고 판단될 때.

| ID | 작업 | 완료 조건 |
|---|---|---|
| T-121 | gimbab 수집 표면 축소 (신규·예약·재입고만) | 1주기 요청 5회 이하 |
| T-122 | `pipeline.py`: RawItem → listings upsert | `collector run --source gimbab` 후 DB 적재 |
| T-123 | `raw_snapshots` + `content_hash` 스킵 | 동일 내용 재크롤 시 파싱 미수행 로그 |
| T-124 | 크롤 결과 → `releases` 연결 (`curation='CRAWLED'`) | 수동 등록분과 충돌 없음 |
| T-125 | 제목에서 배송예정일 추출 | `10월 1일 이후` / `9월초` 등 관측 3형태 파싱 |
| T-126 | 파서 카나리 워크플로 | 의도적 셀렉터 파손 시 CI 실패 재현 |
| T-127 | `secondtrack.py` 어댑터 | fixture 파싱 성공 |
| T-128 | `poclanos.py` 어댑터 | fixture 파싱 성공 |
| T-129 | 경량 중복 억제 (정규화 제목+아티스트, 7일 창) | 동일 발매 중복 알림 0건 |

> **보류 (삭제 아님)**: 기존 T-019(별칭 사전), T-020(resolver S1~S5),
> T-021(병합 검토 CLI), T-022(판매처별 비교), T-025(pg_trgm 검색).
> 판매처별 가격 비교와 디스코그래피가 핵심이 아니라고 확정되었으므로
> ([ADR-0005](adr/0005-manual-curation-first.md)) 필요해지는 시점까지 미룬다.

### M4 — 계정·워치리스트

| ID | 작업 | 완료 조건 |
|---|---|---|
| T-029 | Sign in with Apple + JWT 발급 | 토큰 검증 테스트 통과 |
| T-030 | 워치리스트 CRUD API | 4종 target_type 동작 |
| T-031 | 워치리스트 ↔ 이벤트 매칭 쿼리 | 키워드 매칭 포함 단위 테스트 |
| T-032 | 웹 워치리스트 화면 | 로그인 후 CRUD 동작 |

### M5 — iOS 앱

| ID | 작업 | 완료 조건 |
|---|---|---|
| T-033 | Xcode 프로젝트 생성, swift-openapi-generator 연동 | 빌드 성공, 생성된 클라이언트로 `/v1/feed` 호출 |
| T-034 | DesignSystem (Color/Typography/StatusBadge) | 다크모드 대응 |
| T-035 | FeedView + FeedViewModel | 무한 스크롤, Pull-to-refresh |
| T-036 | SearchView, ReleaseDetailView | 아웃링크 Safari 오픈 |
| T-037 | Sign in with Apple + Keychain | 재실행 시 세션 유지 |
| T-038 | WatchlistView | CRUD 동작 |
| T-039 | SwiftData 오프라인 캐시 | 기내 모드에서 최근 피드 표시 |

### M6 — 네이티브 APNs·확장 푸시 (현재 Web Push와 별도)

| ID | 작업 | 완료 조건 |
|---|---|---|
| T-040 | `POST /v1/devices` + `device_tokens` | 토큰 등록/갱신 |
| T-041 | `aioapns` 디스패처 | 샌드박스 APNs 발송 성공 |
| T-042 | iOS 푸시 수신 + 딥링크 | 알림 탭 → 해당 릴리스 상세 이동 |
| T-043 | 알림 설정(즉시/일간요약/끄기) | 사용자별 설정 반영 |

### M7 — 운영 강화

| ID | 작업 | 완료 조건 |
|---|---|---|
| T-044 | `deploy.yml` + 롤백 스크립트 | main 푸시 시 무중단 배포 |
| T-045 | DB 일 1회 백업(S3) | 복구 리허설 1회 완료 |
| T-046 | 소스 자동 비활성화·복구 로직 | 429 연속 5회 시 비활성화 + 알림 |
| T-047 | Discogs API 연동으로 카탈로그 번호/바코드 보강 | 병합 recall 개선 측정 |

---

## 11. 위험 요소 및 대응

현재 대응과 향후 계획을 구분한다. 파서 카나리·소스 DB 비활성화·자동 복구·수집 장애 외부 경보는 아직 없으며,
아래 미래 대응을 이미 운영 중인 장치로 해석하지 않는다.

| 위험 | 영향 | 가능성 | 대응 |
|---|---|---|---|
| 소스 사이트 개편으로 파서 파손 | 상 | 상 | 파서 카나리(T-126) + fixture 골든 테스트 + 소스별 알람 |
| 소스 운영자의 차단 요청 | 상 | 중 | 사전 고지·제휴 문의(§3.4). `sources.is_enabled` 플래그로 즉시 중단 가능한 구조 |
| 잘못된 병합으로 인한 신뢰 하락 | 중 | 중 | 정밀도 우선 정책, `merge_candidates` 보류 큐, 되돌릴 수 있는 병합 |
| 봇 차단(Cloudflare 등) | 중 | 중 | 대상 소스 재검토. **우회 시도하지 않고 해당 소스 제외** |
| 알림 지연으로 한정반 놓침 | 상 | 중 | 현재 수동 일정은 60초 tick·제한된 재시도. 별도 우선순위 큐는 미구현 |
| iOS 심사 반려 | 중 | 하 | 네이티브 구현(B안), 명확한 콘텐츠 귀속 표기, 개인정보처리방침 페이지 준비 |
| 단독 개발자 번아웃 | 중 | 중 | M0~M3까지가 실사용 가치의 80%. 여기서 일단 “쓸 만한 상태”로 마감하고 휴지기 |

---

## 12. 확장 로드맵 (v1.1 이후)

- **Discogs/MusicBrainz 연동**: 정식 메타데이터·커버·트랙리스트 보강, `master_id` 그룹핑
- **가격 이력 그래프**: `listing_events`를 시계열로 시각화
- **위시리스트 → 예산 시뮬레이션**: 이번 달 예약 총액 계산
- **iOS 위젯 / Live Activity**: 예약 오픈 카운트다운
- **Discogs 컬렉션 동기화**: 보유 목록과 대조하여 중복 구매 방지
- **해외 소스 확장**: Bandcamp, Rough Trade, HHV, Diskunion (국내 발매와의 가격 비교)
- **개인화 추천**: 보유·워치 이력 기반 콘텐츠 기반 추천 (기존 위스키 추천 프로젝트의 접근을 재사용 가능)

---

## 13. 용어집

| 용어 | 정의 |
|---|---|
| Listing | 특정 판매처의 특정 상품 페이지 1건 |
| Release | 물리적 한 판(edition). 카탈로그 번호 + 바리언트로 식별 |
| Variant | 동일 앨범의 물리적 차이 (색상, 한정 수량, 중량, 부속) |
| Entity Resolution | 서로 다른 소스의 Listing을 동일 Release로 병합하는 과정 |
| Fixture | 테스트용으로 저장된 실제 HTML 스냅샷 |
| Canary | 실사이트를 대상으로 소량 요청하여 파서 정상 동작을 확인하는 정기 점검 |
| Walking Skeleton | 전 계층을 관통하는 최소 기능 경로 |
