# Vinyl Radar — 국내 바이닐 발매 정보 통합 서비스 청사진 (한국어판)

> **문서 목적**: 본 문서는 사람과 코딩 에이전트(Claude Code, Codex 등)가 **동일하게** 참조하는 단일 진실 공급원(Single Source of Truth)입니다.
> 영어판은 `docs/BLUEPRINT.en.md`이며 두 문서는 항상 동기화되어야 합니다. 내용이 충돌할 경우 **한국어판을 우선**합니다.
>
> **문서 버전**: 1.0.0
> **최종 수정**: 2026-08-20

---

## 0. 에이전트를 위한 우선 지시사항 (READ FIRST)

코딩 에이전트는 작업을 시작하기 전에 다음을 반드시 준수합니다.

1. **작업 단위는 `§10 작업 백로그`의 태스크 ID(`T-XXX`)를 기준으로 합니다.** 한 번에 하나의 태스크만 수행하고, 완료 조건(Acceptance Criteria)을 모두 충족한 뒤 다음 태스크로 이동합니다.
2. **파일을 새로 만들기 전에 `§6 리포지토리 구조`에 해당 경로가 정의되어 있는지 확인합니다.** 정의되지 않은 최상위 디렉터리를 임의로 생성하지 않습니다.
3. **스크래핑 대상 사이트에 실제 요청을 보내는 코드는 테스트에서 실행하지 않습니다.** 테스트는 반드시 `tests/fixtures/` 에 저장된 HTML 스냅샷을 사용합니다.
4. **`§3.4 수집 윤리 및 법적 준수사항`을 위반하는 코드는 작성하지 않습니다.** 특히 robots.txt 무시, 초당 1회를 초과하는 요청, 이미지 원본 재호스팅은 금지합니다.
5. **커밋 단위는 태스크 단위입니다.** 커밋 메시지는 `feat(collector): T-014 세컨드트랙 어댑터 구현` 형식을 따릅니다.
6. **불확실한 설계 결정은 임의로 확정하지 않습니다.** `docs/adr/` 에 ADR(Architecture Decision Record) 초안을 작성하고 사용자에게 확인을 요청합니다.
7. **Python 작업 시 반드시 프로젝트 가상환경(`.venv`)을 활성화한 상태에서 실행합니다.**

---

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

### 2.1 전체 구성도

**1단계 — 수동 등록 (현재, [ADR-0005](adr/0005-manual-curation-first.md))**

```
┌──────────────────────────────────────────────────────────────────┐
│  운영자 (개발자)                                                  │
│    · 발매 일정 등록 / 수정 / 공개                                  │
│    · 인증: ADMIN_API_KEY (계정 시스템 없음)                        │
└─────────────────────────────┬────────────────────────────────────┘
                              │ POST /admin/releases
┌─────────────────────────────▼────────────────────────────────────┐
│                     PostgreSQL 16                                 │
│  releases (일정·예약창·공개여부) · release_links (구매 링크)        │
│  listing_events (알림 원천) · sources                             │
└─────────────────────────────┬────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
┌─────────────▼──────────────┐   ┌────────────▼─────────────────┐
│  Scheduler (APScheduler)    │   │  FastAPI (REST, /v1)         │
│  · preorder_opens_at 감시   │   │  · /v1/releases  /v1/feed    │
│  · 24시간 전 / 정시 발송     │   │  · /v1/feed.rss              │
│  · diff 엔진 불필요          │   │  · /v1/releases.ics          │
└─────────────┬──────────────┘   └────────────┬─────────────────┘
              │                               │
              ▼                    ┌──────────┴──────────┐
        알림 발송 큐                ▼                     ▼
                              웹 피드/캘린더        RSS·캘린더 구독
                                                  (인증 불필요)
```

**핵심 설계 판단**: 알림 트리거가 **시각 기반**이다. 운영자가 `preorder_opens_at` 을 입력하므로
"직전 상태와 비교"하는 diff 엔진이 필요 없다. 발송 누락은 추정 오류가 아니라 **버그**다.

또한 **RSS·iCalendar 는 인증이 필요 없다.** 계정 시스템과 푸시 인프라를 만들기 전에
핵심 약속을 배송할 수 있다.

**2단계 — 자동 수집 재개 (M3)**

수집 부품은 **이미 만들어져 테스트를 통과한 상태로 대기**한다
(`fetcher.py`, `adapters/`, `registry.py`). 제품 루프에 배선되지 않았을 뿐이다.

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ 김밥      │  │ 세컨드    │  │ 포크라노스 │   ← 목록 페이지 기반 (ADR-0004)
│ Adapter  │  │ 트랙      │  │ Adapter  │      신규·예약·재입고 표면만
└────┬─────┘  └────┬─────┘  └────┬─────┘
     └─────────────┴─────────────┘
                   │ RawItem[]
        ┌──────────▼──────────┐
        │ Fetcher + Scheduler │  robots.txt · 0.5 req/s · 백오프
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────────────────────┐
        │  listings (크롤 산출물)               │
        │    ↓ curation='CRAWLED' 로 releases  │
        │      에 연결. 수동 등록분과 병존       │
        └─────────────────────────────────────┘
```

### 2.2 기술 스택 결정 및 근거

| 계층 | 선택 | 근거 | 검토했으나 채택하지 않은 대안 |
|---|---|---|---|
| 수집기 | Python 3.12 + `httpx`(async) + `selectolax` | 정적 HTML이 대부분이라 헤드리스 브라우저가 불필요. selectolax는 BeautifulSoup 대비 5~10배 빠름 | Scrapy(프레임워크 오버헤드), Playwright(리소스 과다 — JS 렌더링 필요한 소스에만 선택적 사용) |
| 스케줄러 | APScheduler (단일 컨테이너) | 소스 3~10개 규모에서 Celery+Redis는 과설계. 이후 필요 시 교체 가능한 인터페이스 유지 | Celery Beat(브로커 운영 부담), GitHub Actions cron(5분 미만 주기 불가·상태 유지 곤란) |
| DB | PostgreSQL 16 + `pg_trgm` + `unaccent` | 퍼지 문자열 매칭을 DB에서 처리 가능. JSONB로 소스별 원본 필드 보존 | MongoDB(관계형 병합 로직에 불리), SQLite(동시 쓰기 제약) |
| API | FastAPI + Pydantic v2 + SQLAlchemy 2.0 | 기존 숙련 스택. OpenAPI 자동 생성 → iOS 클라이언트 코드 생성에 직결 | Django REST(무거움), Litestar(생태계) |
| 웹 | Next.js 16 (App Router) + Tailwind, PWA | SSR로 SEO 확보(“OO 바이닐 발매” 검색 유입). React 생태계 | SvelteKit(팀 확장성), 순수 SPA(SEO 손실) |
| iOS | SwiftUI + `URLSession` + Swift Concurrency | §8 참조. 네이티브 우선 권장 | WKWebView 래퍼(App Store 심사 4.2 리스크) |
| 배포 | Docker Compose on EC2 (t4g.small, ARM) | 기존 경험 재사용. 월 $10 내외 | k8s(과설계), Vercel+Supabase(수집기 상주 프로세스 부적합) |
| CI/CD | GitHub Actions → GHCR → SSH 배포 | 기존 경험 재사용 | ArgoCD(과설계) |
| 관측 | structlog(JSON) + Prometheus + Sentry | 파서 무음 실패 감지가 핵심 요구사항 | ELK(운영 부담) |

---

## 3. 데이터 수집 계층 상세

### 3.1 어댑터 인터페이스

모든 소스는 아래 프로토콜을 구현합니다. **새 소스 추가 시 이 파일 외의 코드 변경이 없어야 합니다.**

```python
# packages/core/src/vinyl_core/adapters/base.py
from typing import Protocol, AsyncIterator
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, HttpUrl


class StockStatus(StrEnum):
    IN_STOCK = "IN_STOCK"        # 재고 있음
    SOLD_OUT = "SOLD_OUT"        # 품절
    PREORDER = "PREORDER"        # 예약판매 중
    COMING_SOON = "COMING_SOON"  # 입고 예정 (구매 불가)
    UNKNOWN = "UNKNOWN"


class RawItem(BaseModel):
    """어댑터가 반환하는 원시 항목. 정규화 전 상태를 그대로 보존한다."""
    source_id: str                 # 예: "gimbab"
    source_item_id: str            # 소스 내부 상품 ID (URL에서 추출)
    url: HttpUrl
    title_raw: str                 # 소스에 표기된 그대로. 절대 가공 금지
    artist_raw: str | None
    label_raw: str | None
    price_krw: Decimal | None
    stock_status: StockStatus
    format_raw: str | None         # 예: "2LP", "LP+CD", "7\""
    release_date_raw: str | None   # 예: "2026.09.12"
    thumbnail_url: HttpUrl | None  # 저장만 하고 재호스팅하지 않음
    extra: dict                    # 소스 고유 필드 (JSONB로 저장)
    fetched_at: datetime


class SourceAdapter(Protocol):
    source_id: str
    display_name: str
    base_url: str
    crawl_interval_seconds: int    # 최소 300
    requires_javascript: bool

    async def discover(self) -> AsyncIterator[str]:
        """수집 대상 **페이지** URL을 순회 반환한다 (목록 또는 상세 — ADR-0004)."""
        ...

    async def parse_page(self, url: str, html: str) -> list[RawItem]:
        """페이지 HTML에서 RawItem을 모두 뽑는다.
        목록이면 여러 건, 상세면 1건, 실패하면 빈 목록.
        실패 시 반드시 로그를 남긴다 (예외를 삼키지 않는다)."""
        ...
```

### 3.2 소스별 조사 결과 및 구현 노트

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

### 3.3 수집 파이프라인 동작

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
[NotificationDispatcher] 워치리스트 매칭 → APNs/이메일 발송 큐 적재
```

### 3.4 수집 윤리 및 법적 준수사항 (필수)

에이전트는 다음 규칙을 **예외 없이** 코드에 반영합니다.

| 규칙 | 구현 방법 |
|---|---|
| robots.txt 준수 | `urllib.robotparser` 로 매 크롤 시작 시 파싱. `Disallow` 경로 접근 금지 |
| 요청 속도 제한 | 소스별 **최대 0.5 req/s**, 동시 연결 2 이하. `asyncio.Semaphore` + 지터(jitter) 적용 |
| User-Agent 명시 | `VinylRadar/1.0 (+https://<도메인>/about; contact@<도메인>)` — 정체와 연락처를 밝힘 |
| 조건부 요청 사용 | ETag / Last-Modified 캐시로 불필요한 트래픽 최소화 |
| 저작물 재사용 최소화 | **메타데이터(제목·아티스트·가격·재고·발매일)만 저장.** 상세 설명 원문·리뷰 텍스트 저장 금지. 썸네일은 URL만 저장하고 자체 CDN에 복제하지 않음 |
| 원본 귀속 | 모든 화면에서 소스명 표기 + 원본 상품 페이지로 아웃링크 |
| 우회 금지 | CAPTCHA·봇 차단 우회, 로그인 필요 영역 접근, 비공개 내부 API 역공학 금지 |
| 차단 대응 | 429/403 수신 시 지수 백오프 후 해당 소스 자동 비활성화 + 운영자 알림 |
| 사전 고지 | 서비스 공개 전 각 소스 운영자에게 이메일로 목적 설명 및 제휴/API 제공 가능 여부 문의 |

> **법적 배경 참고**: 국내에서는 저작권법상 데이터베이스제작자의 권리(제91조~제98조), 부정경쟁방지법상 성과물 무단사용(제2조 제1호 차목), 각 사이트 이용약관이 쟁점이 될 수 있습니다. 일반적으로 **사실적 메타데이터의 소량 수집 + 원본 아웃링크 + 대체재가 아닌 보완재로 기능**하는 구조가 위험이 낮다고 평가되나, 이는 법률 자문이 아닙니다. 서비스를 공개적으로 운영하거나 수익화할 계획이라면 전문가 검토를 권합니다. 개인 학습·포트폴리오 목적이라면 **비공개 운영 + 소스 운영자 사전 동의 확보**가 가장 안전한 경로입니다.

---

## 4. 데이터 모델

### 4.1 개념 모델

- **`listing`**: 특정 판매처의 특정 상품 페이지 하나. 소스마다 별개로 존재.
- **`release`**: 물리적 실체로서의 한 판(edition). 카탈로그 번호와 바리언트(색상 등)로 구분.
- **`master`**: 동일 앨범의 여러 판을 묶는 상위 개념 (선택적, v1.1).

> 예시: 실리카겔 『Machine Boy』 한정 컬러반은 김밥레코즈와 세컨드트랙에 각각 `listing`으로 존재하지만, 동일한 하나의 `release`로 병합됩니다. 반면 블랙반과 클리어반은 **서로 다른 `release`** 입니다.

### 4.2 스키마 (PostgreSQL DDL)

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

-- 발송 기록. **재발송을 구조적으로 막는 장치다** (ADR-0006 §5.2).
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

`PREORDER_OPEN`은 **최우선 알림 등급**으로 즉시 발송합니다. 나머지는 배치 발송(사용자 설정에 따라 즉시/일 1회 요약)합니다.

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

예약 시각이 17:00 → 19:00 으로 미뤄지면, 17:00 에서 나온 `PREORDER_OPENS_SOON` 과
`PREORDER_OPEN` 은 **역할을 잃습니다.** 그대로 두면 두 가지가 동시에 깨집니다.

1. 피드에 옛 시각을 말하는 알림이 남아, 어느 쪽을 믿어야 할지 알 수 없습니다
2. 멱등성 판정이 "이미 보냈다"로 세어, **19:00 에 예약 시작 알림이 안 나갑니다** —
   이 제품이 유일하게 놓치면 안 되는 순간입니다

그래서 `superseded_at` 에 표시합니다. **지우지 않습니다** — 그 행은 구독자에게 실제로
보낸 기록이고 `notification_deliveries` 가 참조합니다. 보낸 사실은 취소되지 않습니다.

| 바뀐 필드 | 무효화되는 이벤트 |
|---|---|
| `preorder_opens_at` | `PREORDER_OPENS_SOON`, `PREORDER_OPEN` |
| `release_date` | `RELEASED` |
| `preorder_closes_at` | (없음 — 이 시각에 걸린 이벤트가 없습니다) |

**영향받는 것만 무효화합니다.** 예약 마감만 고쳤는데 `PREORDER_OPEN` 까지 무효화하면
같은 알림이 이유 없이 두 번 나갑니다. `SCHEDULE_ADDED` 는 무효화하지 않습니다 —
일정이 등록되었다는 사실은 시각이 바뀌어도 그대로입니다.

#### 4.5.3 피드는 발매당 최신 이벤트 하나만 싣는다 (T-118)

같은 앨범에 `SCHEDULE_ADDED → PREORDER_OPENS_SOON → PREORDER_OPEN` 이 쌓이면 피드 상단
세 줄이 전부 같은 앨범이 됩니다. 쓸모 있는 것은 마지막 하나뿐입니다.

`/v1/feed` 와 `/v1/feed.rss` 가 **같은 질의**(`vinyl_api/feed_query.py`)를 씁니다.
각자 들고 있으면 한쪽만 고쳐지고 다른 쪽이 조용히 어긋납니다.
푸시도 `tag=release-<id>` 로 같은 발매의 알림을 하나로 묶으므로 세 곳이 같은 규칙을 씁니다.

---

## 5. API 설계

### 5.1 규약

- 베이스 경로: `/v1`
- 인증: `Authorization: Bearer <JWT>` (워치리스트·디바이스 엔드포인트만 필수)
- 페이지네이션: **커서 기반** (`?cursor=<opaque>&limit=20`, 최대 100)
- 응답: `snake_case` JSON. 타임스탬프는 ISO-8601 UTC (`2026-08-20T04:00:00Z`)
- 오류: RFC 9457 Problem Details 형식
- 캐싱: 목록 응답에 `ETag` 및 `Cache-Control: public, max-age=60`

### 5.2 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/v1/feed` | 통합 타임라인. 이벤트 기반 최신순 |
| `GET` | `/v1/releases` | 발매 목록. 필터: `from`, `to`, `format`, `source`, `is_limited`, `stock_status`, `label`, `artist_id` |
| `GET` | `/v1/releases/{id}` | 상세 + 소속 `listings` 배열 (판매처별 가격·재고 비교) |
| `GET` | `/v1/search?q=` | 통합 검색 (아티스트·타이틀·레이블 대상, trigram) |
| `GET` | `/v1/artists/{id}` | 아티스트 상세 + 발매 목록 |
| `GET` | `/v1/events` | 이벤트 스트림. `?since=`, `?type=` |
| `GET` | `/v1/sources` | 소스 목록 및 각 소스의 최종 수집 시각·상태 |
| `POST` | `/v1/watchlist` | 워치리스트 추가 |
| `GET` | `/v1/watchlist` | 워치리스트 조회 |
| `DELETE` | `/v1/watchlist/{id}` | 워치리스트 삭제 |
| `GET` | `/v1/push/public-key` | VAPID 공개키 (브라우저 구독에 필요, 인증 불필요) |
| `POST` | `/v1/push/subscribe` | Web Push 구독 등록 (인증 불필요) |
| `DELETE` | `/v1/push/subscribe` | Web Push 구독 해지 |
| `POST` | `/v1/devices` | APNs 토큰 등록/갱신 (iOS 앱 도입 시) |
| `POST` | `/v1/auth/apple` | Sign in with Apple 토큰 교환 |
| `GET` | `/v1/feed.rss` | RSS 2.0 피드 (인증 불필요, 확산 채널) |
| `GET` | `/v1/releases.ics` | 발매일 캘린더 (iCalendar) |
| `GET` | `/healthz` | 헬스체크 (DB 연결 포함) |
| `GET` | `/metrics` | Prometheus 메트릭 |

### 5.2-1 운영자 API (수동 등록, [ADR-0005](adr/0005-manual-curation-first.md))

인증은 `X-Admin-Key: <ADMIN_API_KEY>` 헤더 하나다. **계정 시스템을 쓰지 않는다** —
사용자가 1명(운영자)인 단계에서 OAuth 를 만드는 것은 과설계다.

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/admin/releases` | 발매 일정 등록 (기본 `is_published=false` 초안) |
| `PATCH` | `/admin/releases/{id}` | 일정 수정 |
| `POST` | `/admin/releases/{id}/publish` | 공개 — 이 시점에 `SCHEDULE_ADDED` 이벤트 발생 |
| `DELETE` | `/admin/releases/{id}` | 미공개 초안만 삭제 가능 |
| `POST` | `/admin/releases/{id}/links` | 구매 링크 추가 |
| `GET` | `/admin/releases` | 초안 포함 전체 조회 |

**공개 API 는 `is_published=true` 만 노출한다.** 초안이 새어 나가면 미공지 발매가 유출된다.

> `POST /admin/releases` 요청 예시
> ```jsonc
> {
>   "title": "Machine Boy",
>   "artist_name": "실리카겔",
>   "label": "Magic Strawberry Sound",
>   "format": "2LP",
>   "variant": "Clear Vinyl",
>   "is_limited": true,
>   "release_date": "2026-09-12",
>   "preorder_opens_at": "2026-08-25T14:00:00+09:00",  // KST 로 받아 UTC 로 저장
>   "preorder_closes_at": "2026-09-05T23:59:59+09:00",
>   "cover_url": "https://...",
>   "notes": "300장 한정, 인스타 공지 확인",
>   "links": [
>     { "shop_name": "김밥레코즈", "source_id": "gimbab", "url": "https://...", "price_krw": 52000 }
>   ]
> }
> ```

### 5.3 응답 예시

```jsonc
// GET /v1/releases/1042
{
  "id": 1042,
  "title": "Machine Boy",
  "artist": { "id": 88, "name_display": "실리카겔", "name_en": "Silica Gel" },
  "label": "매직스트로베리사운드",
  "catalog_no": "MSS-0142",
  "barcode": "8809876543210",
  "format": "2LP",
  "variant": "Clear Vinyl",
  "is_limited": true,
  "release_date": "2026-09-12",
  "cover_url": "https://…",          // 원본 URL. 프록시하지 않음
  "listings": [
    {
      "source": { "id": "gimbab", "display_name": "김밥레코즈" },
      "url": "https://…",
      "price_krw": 58000,
      "stock_status": "PREORDER",
      "last_seen_at": "2026-08-20T03:58:12Z"
    },
    {
      "source": { "id": "secondtrack", "display_name": "세컨드트랙" },
      "url": "https://…",
      "price_krw": 56000,
      "stock_status": "SOLD_OUT",
      "last_seen_at": "2026-08-20T03:59:04Z"
    }
  ],
  "recent_events": [
    { "event_type": "PREORDER_OPEN", "occurred_at": "2026-08-19T02:00:11Z", "source_id": "gimbab" }
  ]
}
```

---

## 6. 리포지토리 구조

```
vinyl-radar/
├─ CLAUDE.md                        # 에이전트용 상시 컨텍스트 (§0 요약 + 관례)
├─ README.md
├─ compose.yaml                     # 로컬 개발 스택
├─ compose.prod.yaml
├─ Makefile                         # make up / test / lint / migrate / seed
├─ .env.example
├─ .vscode/
│  ├─ settings.json
│  ├─ launch.json
│  ├─ tasks.json
│  └─ extensions.json
├─ .devcontainer/
│  └─ devcontainer.json
├─ apps/
│  ├─ api/                          # FastAPI
│  │  ├─ src/vinyl_api/
│  │  │  ├─ main.py
│  │  │  ├─ deps.py
│  │  │  ├─ routers/{feed,releases,calendar,rss,push,admin,admin_ui}.py
│  │  │  ├─ feed_query.py           # 발매당 최신 이벤트 하나 — feed 와 rss 가 공유
│  │  │  ├─ icalendar.py            # RFC 5545 생성 (직접 구현)
│  │  │  ├─ rss.py                  # RSS 2.0 + RFC 822 생성 (직접 구현)
│  │  │  ├─ problems.py             # RFC 9457 오류 응답
│  │  │  ├─ pagination.py           # keyset 커서
│  │  │  ├─ caching.py              # ETag / Cache-Control
│  │  │  ├─ serializers.py
│  │  │  ├─ schemas/
│  │  │  └─ services/
│  │  ├─ tests/
│  │  ├─ pyproject.toml
│  │  └─ Dockerfile
│  ├─ collector/                    # 수집기 + 스케줄러
│  │  ├─ src/vinyl_collector/
│  │  │  ├─ scheduler.py
│  │  │  ├─ fetcher.py              # httpx, rate limit, robots, 조건부 요청
│  │  │  ├─ pipeline.py
│  │  │  └─ cli.py                  # `collector run --source gimbab --dry-run`
│  │  ├─ tests/
│  │  │  └─ fixtures/<source_id>/*.html
│  │  ├─ pyproject.toml
│  │  └─ Dockerfile
│  ├─ web/                          # Next.js 16 (PWA)
│  │  ├─ app/
│  │  │  ├─ page.tsx                # 피드
│  │  │  ├─ manifest.ts             # 웹 앱 매니페스트 (홈 화면 추가 = iOS 푸시의 전제)
│  │  │  ├─ api/push/               # 같은 출처 프록시 (ADR-0007)
│  │  │  ├─ subscribe/PushToggle.tsx  # 푸시 켜기/끄기 (클라이언트 컴포넌트)
│  │  │  ├─ releases/[id]/page.tsx
│  │  │  ├─ search/page.tsx
│  │  │  └─ artists/[id]/page.tsx
│  │  ├─ public/
│  │  │  ├─ sw.js                   # 서비스워커 — 푸시 수신·알림 클릭
│  │  │  └─ icon-*.png              # PWA 아이콘 (192/512/maskable/apple-touch)
│  │  ├─ lib/api.ts                 # OpenAPI 생성 클라이언트 (서버 컴포넌트 전용)
│  │  ├─ lib/push.ts                # 브라우저 구독
│  │  ├─ lib/proxy.ts               # API 전달
│  │  ├─ components/
│  │  └─ Dockerfile
│  └─ ios/                          # Xcode 프로젝트
│     └─ VinylRadar/
│        ├─ VinylRadarApp.swift
│        ├─ Features/{Feed,Search,ReleaseDetail,Watchlist,Settings}/
│        ├─ Core/{APIClient,Models,DesignSystem}/
│        └─ Notifications/
├─ packages/
│  └─ core/                         # API·collector 공용 Python 패키지
│     ├─ src/vinyl_core/
│     │  ├─ adapters/
│     │  │  ├─ base.py
│     │  │  ├─ gimbab.py
│     │  │  ├─ secondtrack.py
│     │  │  ├─ poclanos.py
│     │  │  └─ registry.py          # 어댑터 자동 등록
│     │  ├─ models/                 # SQLAlchemy ORM
│     │  ├─ normalize.py
│     │  ├─ resolver.py
│     │  ├─ events.py
│     │  ├─ testing.py                # 엣지 케이스 카탈로그 (전 출력 경로 공용)
│     │  └─ aliases.yaml            # 아티스트 별칭 사전
│     ├─ tests/
│     └─ pyproject.toml
├─ migrations/                      # Alembic
├─ backups/                        # pg_dump 산출물 (git 에 커밋하지 않음)
├─ infra/
│  ├─ nginx/
│  ├─ prometheus/
│  └─ deploy.sh
├─ docs/
│  ├─ BLUEPRINT.ko.md               # 본 문서
│  ├─ BLUEPRINT.en.md
│  ├─ adapters/<source_id>.md       # 소스별 조사 기록
│  ├─ adr/NNNN-*.md
│  └─ api/openapi.json              # CI에서 자동 생성
└─ .github/workflows/
   ├─ ci.yml
   ├─ deploy.yml
   └─ parser-canary.yml             # 실사이트 대상 일 1회 파서 검증
```

---

## 7. 웹 프론트엔드

### 7.1 화면 구성

| 화면 | 경로 | 핵심 요소 |
|---|---|---|
| 피드 | `/` | 이벤트 타임라인. `PREORDER_OPEN` 뱃지 강조. 소스 필터 칩 |
| 발매 캘린더 | `/calendar` | 월간 그리드. 발매 예정일 기준 |
| 상세 | `/releases/[id]` | 커버·메타데이터·판매처별 가격 비교 테이블·아웃링크 버튼 |
| 검색 | `/search` | 인크리멘털 검색. 아티스트/레이블/포맷 패싯 |
| 아티스트 | `/artists/[id]` | 디스코그래피 + 워치 버튼 |
| 워치리스트 | `/watchlist` | 로그인 필요 |

### 7.2 디자인 방향

- **정보 밀도 우선.** 수집가는 한 화면에서 많은 항목을 스캔합니다. 카드 간 여백을 과하게 두지 않습니다.
- **상태의 시각적 우선순위**: `예약오픈` > `재입고` > `신규` > `가격변동`. 색상보다 **레이블+아이콘 조합**을 사용하여 색각 이상 사용자를 배려합니다.
- 다크 모드 기본 지원. 커버 아트가 주인공이므로 중성적 배경을 사용합니다.
- 이미지는 `next/image`의 `remotePatterns`로 원본 도메인을 허용하되 **자체 저장하지 않습니다.**

### 7.3 API 클라이언트 생성

FastAPI가 생성한 `openapi.json`으로부터 타입을 자동 생성합니다. 수기 타입 정의를 금지합니다.

```bash
# apps/web
npx openapi-typescript ../../docs/api/openapi.json -o lib/api-types.ts
```

---

## 8. iOS 애플리케이션

### 8.1 구현 방식 선택 — 검토와 권고

| 방식 | 장점 | 단점 | 평가 |
|---|---|---|---|
| **A. WKWebView 래퍼** | 개발 1~2일. 웹 코드 100% 재사용 | App Store 심사 가이드라인 **4.2 (Minimum Functionality)** 로 반려될 위험이 실질적으로 존재. 푸시 알림·햅틱·오프라인 캐시 등 네이티브 경험 부재. 스크롤 감각이 즉시 “웹”으로 인지됨 | 비권장 |
| **B. 네이티브 SwiftUI + 공용 REST API** | 진정한 네이티브 UX. 푸시·위젯·Live Activity·Spotlight 연동 가능. OpenAPI로 클라이언트 자동 생성 | 화면을 별도 구현해야 함 | **권고** |
| C. 하이브리드 (네이티브 셸 + 일부 화면 웹뷰) | 절충 | 두 스택의 단점을 모두 상속. 유지보수 복잡도 증가 | 조건부 |

**권고**: **B안(네이티브 SwiftUI)** 을 채택합니다. 근거는 다음과 같습니다.

1. 사용자께서 명시한 목표가 “**더 사용자 친화적인** iOS 앱”입니다. 웹뷰 래퍼는 정의상 웹보다 친화적일 수 없습니다.
2. 이 서비스의 핵심 가치는 **푸시 알림**(예약판매 오픈 즉시 통지)입니다. 이는 네이티브 통합이 필수적입니다.
3. API 우선 설계이므로 웹과 iOS가 동일한 계약을 공유하며, 웹 작업이 낭비되지 않습니다. “웹을 만들고 이를 활용”한다는 의도는 **UI 코드 재사용이 아니라 API·도메인 모델 재사용**으로 달성됩니다.

다만 반대 논거도 명시합니다. 학습·포트폴리오 목적에서 iOS를 빠르게 배포해 보는 것이 우선이라면, A안으로 먼저 출시한 뒤 화면 단위로 네이티브 전환하는 경로도 합리적입니다. 이 경우 최소한 **푸시 알림·설정 화면·탭바는 네이티브로 구현**해야 4.2 리스크를 낮출 수 있습니다.

### 8.2 네이티브 앱 구조

```
VinylRadar/
├─ VinylRadarApp.swift              @main, DI 컨테이너
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
iOS: NotificationHandler → 딥링크 vinylradar://release/1042
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

### 9.1 로컬 실행 (Quick Start)

```bash
git clone <repo> && cd vinyl-radar
cp .env.example .env

make up          # postgres + api + collector + web 컨테이너 기동
make migrate     # Alembic 마이그레이션 적용
make seed        # sources 테이블 시드 + 아티스트 별칭 로드

# 단일 소스 수동 수집 (DB 쓰기 없이 파싱 결과만 출력)
docker compose exec collector collector run --source gimbab --dry-run --limit 5

# 접속
# API 문서: http://localhost:8000/docs
# 웹:       http://localhost:3000
```

### 9.2 `.vscode/extensions.json` 권장 확장

```jsonc
{
  "recommendations": [
    "ms-python.python",
    "charliermarsh.ruff",
    "ms-python.mypy-type-checker",
    "ms-azuretools.vscode-docker",
    "ms-vscode-remote.remote-containers",
    "bradlc.vscode-tailwindcss",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "humao.rest-client",
    "mtxr.sqltools",
    "sswg.swift-lang",
    "yzhang.markdown-all-in-one"
  ]
}
```

### 9.3 테스트 전략

| 계층 | 방식 | 도구 |
|---|---|---|
| 어댑터 파싱 | **저장된 HTML fixture** 기반 골든 테스트. 실제 네트워크 요청 금지 | pytest + 로컬 fixture |
| 정규화 | 테이블 주도 단위 테스트 (입력 → 기대 출력 쌍 30건 이상) | pytest.mark.parametrize |
| 병합 로직 | 정답 라벨링된 100쌍으로 precision/recall 측정. **회귀 시 CI 실패** | pytest + 메트릭 임계값 |
| API | 실제 PostgreSQL 컨테이너 대상 통합 테스트 | pytest + testcontainers |
| 파서 카나리 | **일 1회 실사이트 1건 요청** 후 필수 필드 존재 검증. 실패 시 GitHub Issue 자동 생성 | 별도 워크플로 |

파서 카나리는 “사이트 개편으로 조용히 0건이 수집되는” 최악의 실패 모드를 방지하는 핵심 장치입니다. 반드시 구현하십시오.

### 9.3-1 백업과 복구

**볼륨은 "실수로 안 지워진다"를 보장할 뿐, 유실을 막지 못합니다.**
디스크 고장·인스턴스 삭제·잘못된 마이그레이션·`DROP TABLE` 은 볼륨으로 막을 수 없습니다.

```bash
make backup                          # backups/ 에 타임스탬프 덤프 생성
make restore FILE=backups/xxx.sql.gz # 복구 (기존 데이터를 덮어씀)
```

| 항목 | 내용 |
|---|---|
| 방식 | `pg_dump --clean --if-exists` → gzip. 복구는 `psql` 로 그대로 적용 |
| 주기 | 실서비스에서는 **일 1회 이상** (cron) |
| 보관 위치 | **반드시 서버 밖**(S3 등)에도 둔다. 같은 디스크에만 두면 디스크와 함께 죽는다 |
| 검증 | 복구를 실제로 해 보지 않은 백업은 백업이 아니다. 주기적으로 시험 복구할 것 |

> ⚠️ **`docker compose down -v` 의 `-v` 는 볼륨을 삭제합니다.** 배포 시 쓰는
> `docker compose down` 은 컨테이너만 정리하므로 데이터가 남습니다. 둘을 혼동하지 마십시오.

### 9.4 관측성

| 항목 | 구현 |
|---|---|
| 로그 | `structlog` JSON 출력. `source_id`, `url`, `trace_id` 필수 필드 |
| 메트릭 | `collector_items_parsed_total{source}`, `collector_parse_errors_total{source}`, `collector_run_duration_seconds{source}`, `collector_last_success_timestamp{source}` |
| 알람 조건 | ① 특정 소스의 `last_success_timestamp`가 크론 간격의 3배 초과 ② `parse_errors / items_parsed > 0.1` ③ 24시간 내 `NEW_LISTING` 이벤트 0건 |
| 오류 추적 | Sentry (파싱 예외에 소스별 태그 부착) |

### 9.5 CI/CD

```yaml
# .github/workflows/ci.yml (요약)
jobs:
  quality:
    - ruff check / ruff format --check
    - mypy packages/core apps/api apps/collector
    - pytest --cov (커버리지 임계 70%)
    - openapi.json 생성 후 커밋본과 diff → 불일치 시 실패
  web:
    - pnpm lint / tsc --noEmit / next build
  image:
    - buildx로 linux/arm64 이미지 빌드 → GHCR push (main 브랜치만)
```

배포는 `deploy.yml`에서 SSH로 EC2 접속 → `docker compose pull && up -d` → `/healthz` 검증 → 실패 시 이전 태그로 롤백합니다.

### 9.6 예상 운영 비용 (월, USD)

| 항목 | 비용 |
|---|---|
| EC2 t4g.small (1년 약정) | 약 $9 |
| EBS 20GB | 약 $2 |
| 도메인 | 약 $1 |
| Apple Developer Program | 약 $8 (연 $99 분할) |
| **합계** | **약 $20** |

초기에는 Oracle Cloud Always Free(ARM 4 OCPU/24GB)로 $0 운영도 가능합니다.

---

## 10. 작업 백로그

각 태스크는 **독립적으로 완료 판정 가능**하도록 작성되었습니다. 에이전트는 태스크 ID를 명시하며 진행합니다.

### M0 — Walking Skeleton (완료)

> 목표였던 "1개 소스 → DB → API → 화면"은 [ADR-0005](adr/0005-manual-curation-first.md) 로
> 방향이 바뀌어 **수집 부품까지 완료한 상태로 마감**한다.
> T-008~T-012 는 M3(자동 수집 재개)로 이동한다.

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
| **M0 완료 기준** | 김밥레코즈 상품이 수집되어 웹 화면에 표시된다 | |

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
| T-113 | 발송 멱등성 (동일 이벤트 재발송 금지) | 스케줄러 재기동 후 중복 발송 0건 |
| T-114 | **Web Push 구독** (VAPID 키, 구독/해지 API, 스키마 확장) — [ADR-0006](adr/0006-web-push-first.md) | 브라우저가 구독하고 DB 에 저장됨 |
| T-115 | 발송기 + **멱등 배송** (`notification_deliveries`) | 스케줄러 재기동 후 중복 발송 0건 |
| T-116 | 재시도 + 만료 구독 정리 + 무음 실패 알림 | 의도적 실패 시 운영자 알림, 410 이면 구독 비활성화 |
| T-117 | 웹 구독 UI (PWA 매니페스트 + 서비스워커) — [ADR-0007](adr/0007-same-origin-push-proxy.md) | 실제 기기에서 알림 수신 |
| T-118 | 피드 접기(발매당 최신 1건) + `SCHEDULE_CHANGED` (§4.5.1, §4.5.3) | 같은 앨범이 피드에 한 줄만, 일정 수정 시 알림 발송 |
| T-119 | 일정 변동 시 옛 이벤트 무효화·재발송 (§4.5.2) | 예약 시각을 미루면 **새 시각에** 예약 시작 알림이 다시 나감 |

> **알림 채널은 Web Push 우선** ([ADR-0006](adr/0006-web-push-first.md)). 이메일은 만들지 않는다.
> §8.3 의 APNs 는 폐기가 아니라 **iOS 앱 배포 시점으로 미룬 것**이다.
> T-113 이 검증한 것은 **이벤트 생성** 멱등성이며, **발송** 멱등성은 T-115 에서 완료된다.

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

### M6 — 푸시 알림

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

| 위험 | 영향 | 가능성 | 대응 |
|---|---|---|---|
| 소스 사이트 개편으로 파서 파손 | 상 | 상 | 파서 카나리(T-018) + fixture 골든 테스트 + 소스별 알람 |
| 소스 운영자의 차단 요청 | 상 | 중 | 사전 고지·제휴 문의(§3.4). `sources.is_enabled` 플래그로 즉시 중단 가능한 구조 |
| 잘못된 병합으로 인한 신뢰 하락 | 중 | 중 | 정밀도 우선 정책, `merge_candidates` 보류 큐, 되돌릴 수 있는 병합 |
| 봇 차단(Cloudflare 등) | 중 | 중 | 대상 소스 재검토. **우회 시도하지 않고 해당 소스 제외** |
| 알림 지연으로 한정반 놓침 | 상 | 중 | 예약판매 감지 소스는 크론 간격 5~10분으로 단축, 우선 큐 분리 |
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
