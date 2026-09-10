# Vinyl Radar — Aggregated Korean Vinyl Release Tracker (English Edition)

> **Purpose**: This document is the single source of truth shared by both humans and coding agents (Claude Code, Codex, etc.).
> The Korean edition is `docs/BLUEPRINT.ko.md`. The two must stay in sync; **if they conflict, the Korean edition prevails.**
>
> **Version**: 1.0.0
> **Last updated**: 2026-08-20

---

## 0. Agent Directives (READ FIRST)

Coding agents must observe the following before starting any work.

1. **Work is scoped by task IDs (`T-XXX`) from `§10 Task Backlog`.** Complete exactly one task at a time and satisfy every acceptance criterion before moving on.
2. **Before creating a file, verify its path exists in `§6 Repository Layout`.** Do not invent new top-level directories.
3. **Never issue live requests to scraped sites from tests.** Tests must use HTML snapshots stored under `tests/fixtures/`.
4. **Never write code that violates `§3.4 Crawling Ethics and Legal Compliance`.** In particular: no ignoring robots.txt, no request rates above 1/sec, no rehosting of source images.
5. **One commit per task.** Message format: `feat(collector): T-014 implement Secondtrack adapter`.
6. **Do not unilaterally settle uncertain design decisions.** Draft an ADR under `docs/adr/` and ask the user to confirm.
7. **Always activate the project virtualenv (`.venv`) before running Python.**

---

## 1. Problem Definition

### 1.1 Current State

Korean vinyl (LP) release information is fragmented across several classes of sources:

| Type | Examples | Problem |
|---|---|---|
| Indie record shops | Gimbab Records (김밥레코즈), Secondtrack (세컨드트랙), Dope Record | Independent storefronts, no RSS or API. Restock announcements often appear only on social media |
| Labels / distributors | Poclanos (포크라노스), Mirrorball Music, Beatball | News arrives via press releases and Instagram; no structured listing |
| Large retailers | YES24, Aladin, Hottracks | Searchable, but no "what arrived this week" view |
| International | Discogs, Bandcamp | No visibility into Korean distribution or local pricing |

The practical consequence is that collectors **repeatedly miss the moment preorders open for limited pressings**. Limited runs typically sell out within hours, so information latency translates directly into loss.

### 1.2 Hypothesis

> If we gather new-release and preorder **schedules in one place** for users to subscribe to, and **notify them at the moment preorders open**, the problem of missing limited pressings is substantially solved.

**This product is a schedule-notification service, not a sales database.** ([ADR-0005](adr/0005-manual-curation-first.md))

- **Core**: new-release schedules, preorder windows, notifications that keep users from missing them
- **Not core**: per-shop price comparison, artist discography, exhaustive catalog harvesting

Schedule data is **entered manually by the operator in phase one.** The automated harvester stays built
and tested but unwired, to be connected when manual entry becomes the bottleneck (M3).

> **Why harvesting cannot fill the calendar** (measured): none of the three sources exposes a release date
> as a structured field, and **no source exposes a preorder closing time at all.**
> The calendar's central data has to be entered by a human.

### 1.3 Success Metrics (MVP)

| Metric | Target |
|---|---|
| Schedules published per week | ≥ 20 |
| **Preorder-open notification delivery** | **≥ 99%** (time-driven, so a miss is a bug) |
| Notification timing error | ±1 min |
| Schedule entry → visible in public feed | immediate |
| Silent failures | 0 (must always alert) |

**Deferred until M3 (harvesting resumed)**

| Metric | Target |
|---|---|
| Number of sources harvested | ≥ 3 |
| Latency from listing appearing to surfacing in app | median ≤ 30 min |
| Deduplication accuracy | precision ≥ 0.95, recall ≥ 0.80 |

### 1.4 Explicit Non-Goals

- No **sales or payment processing**. Always out-link to the original seller.
- No **rehosting of source images or copying of product descriptions**.
- Discogs Marketplace price tracking is out of scope for v1.
- Peer-to-peer marketplace features are out of scope.
- **Per-shop price comparison and artist discography are not v1 core features** ([ADR-0005](adr/0005-manual-curation-first.md)).
- **No exhaustive catalog harvesting.** Only the surfaces where new releases, preorders, and restocks appear.

---

## 2. Architecture Overview

### 2.1 System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Collection Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Gimbab   │  │Secondtrack│ │ Poclanos │  │ (future) │        │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │  │ Adapter  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       └─────────────┴─────────────┴─────────────┘               │
│                          │                                       │
│              ┌───────────▼────────────┐                          │
│              │  Scheduler (APScheduler)│                          │
│              │  · per-source cron      │                          │
│              │  · concurrency limits   │                          │
│              └───────────┬────────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │ RawItem[]
┌──────────────────────────▼──────────────────────────────────────┐
│              Normalization & Resolution Layer                    │
│  Normalizer → EntityResolver → EventDetector                    │
│  · string norm.     · barcode/catalog   · snapshot diff          │
│  · format parsing   · fuzzy (pg_trgm)   · event emission         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                     PostgreSQL 16 (+ pg_trgm)                    │
│  raw_snapshots · listings · releases · artists · listing_events  │
│  users · watchlist_items · device_tokens                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    FastAPI (REST, /v1)                           │
│  feed · search · detail · watchlist · devices · RSS/ICS          │
└───────┬───────────────────────────────────┬──────────────────────┘
        │                                   │
┌───────▼─────────┐               ┌─────────▼──────────┐
│  Web (Next.js)  │               │  iOS (SwiftUI)     │
│  · SSR list     │               │  · feed / search   │
│  · SEO landing  │               │  · watchlist       │
└─────────────────┘               │  · APNs push       │
                                  └────────────────────┘
```

### 2.2 Stack Decisions and Rationale

| Layer | Choice | Rationale | Considered but rejected |
|---|---|---|---|
| Collector | Python 3.12 + `httpx` (async) + `selectolax` | Most sources are static HTML, so a headless browser is unnecessary. selectolax is 5–10× faster than BeautifulSoup | Scrapy (framework overhead), Playwright (resource cost — used selectively only for JS-rendered sources) |
| Scheduler | APScheduler in a single container | Celery+Redis is over-engineered for 3–10 sources. Keep the interface swappable | Celery Beat (broker ops burden), GitHub Actions cron (no sub-5-minute cadence, awkward state) |
| Database | PostgreSQL 16 + `pg_trgm` + `unaccent` | Fuzzy string matching handled in-database; JSONB preserves source-specific fields | MongoDB (poor fit for relational merge logic), SQLite (concurrent write limits) |
| API | FastAPI + Pydantic v2 + SQLAlchemy 2.0 | Existing competence; auto-generated OpenAPI feeds directly into iOS client generation | Django REST (heavy), Litestar (ecosystem) |
| Web | Next.js 16 (App Router) + Tailwind, PWA | SSR for SEO (organic search for "<artist> vinyl release") | SvelteKit, pure SPA (loses SEO) |
| iOS | SwiftUI + `URLSession` + Swift Concurrency | See §8. Native recommended | WKWebView wrapper (App Store 4.2 risk) |
| Deployment | Docker Compose on EC2 (t4g.small, ARM) | Reuses existing experience; ~$10/month | Kubernetes (over-engineered), Vercel+Supabase (unsuitable for a long-running collector process) |
| CI/CD | GitHub Actions → GHCR → SSH deploy | Reuses existing experience | ArgoCD |
| Observability | structlog (JSON) + Prometheus + Sentry | Detecting silent parser failure is a core requirement | ELK (ops burden) |

---

## 3. Collection Layer

### 3.1 Adapter Interface

Every source implements this protocol. **Adding a new source must require no code changes outside its own adapter file.**

```python
# packages/core/src/vinyl_core/adapters/base.py
from typing import Protocol, AsyncIterator
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, HttpUrl


class StockStatus(StrEnum):
    IN_STOCK = "IN_STOCK"
    SOLD_OUT = "SOLD_OUT"
    PREORDER = "PREORDER"
    COMING_SOON = "COMING_SOON"   # announced, not yet purchasable
    UNKNOWN = "UNKNOWN"


class RawItem(BaseModel):
    """Raw item returned by an adapter. Preserves pre-normalization state verbatim."""
    source_id: str                 # e.g. "gimbab"
    source_item_id: str            # source-internal product ID (extracted from URL)
    url: HttpUrl
    title_raw: str                 # exactly as displayed. Never pre-process here
    artist_raw: str | None
    label_raw: str | None
    price_krw: Decimal | None
    stock_status: StockStatus
    format_raw: str | None         # e.g. "2LP", "LP+CD", "7\""
    release_date_raw: str | None   # e.g. "2026.09.12"
    thumbnail_url: HttpUrl | None  # stored as URL only, never rehosted
    extra: dict                    # source-specific fields (persisted as JSONB)
    fetched_at: datetime


class SourceAdapter(Protocol):
    source_id: str
    display_name: str
    base_url: str
    crawl_interval_seconds: int    # minimum 300
    requires_javascript: bool

    async def discover(self) -> AsyncIterator[str]:
        """Yield **page** URLs to collect (listing or detail — see ADR-0004)."""
        ...

    async def parse_page(self, url: str, html: str) -> list[RawItem]:
        """Extract every RawItem on the page.
        Many for a listing page, one for a detail page, empty on failure.
        Always log failures — never swallow exceptions."""
        ...
```

### 3.2 Source Survey and Implementation Notes

> **Caution**: Site DOM structures change. The table below is a starting guide only. Agents must save real HTML into `tests/fixtures/<source_id>/` and confirm selectors against it before finalizing.

| source_id | Name | Character | Priority | Expected difficulty |
|---|---|---|---|---|
| `gimbab` | Gimbab Records | Leading Korean indie record shop, frequent new arrivals | **1st (M0)** | Low |
| `secondtrack` | Secondtrack | Curation-driven, heavy limited-edition presence | 2nd (M1) | Medium |
| `poclanos` | Poclanos | Distributor; earliest signal on upcoming releases | 3rd (M1) | Medium |
| `dope` | Dope Record | Expansion candidate | Post-M4 | Medium |
| `mirrorball` | Mirrorball Music | Expansion candidate | Post-M4 | Medium |
| `yes24` | YES24 LP | Large retailer, stable inventory | Post-M4 | High (verify bot policy) |

**Survey checklist (mandatory for every new source):**

1. Fetch `https://<domain>/robots.txt` → record verbatim in `docs/adapters/<source_id>.md`
2. Review Terms of Service for automated-access clauses → quote and record the reasoning in the same file
3. Identify listing URL patterns and pagination style (offset / cursor / infinite-scroll XHR)
4. Determine whether JS rendering is required (does `curl` output contain the product title?)
5. Fix CSS selectors for: title, artist, label, price, stock, format, release date, thumbnail
6. Check for structured data (JSON-LD `Product`, OpenGraph) — **prefer it over HTML selectors** when present, as it is far more change-resistant
7. Save ≥ 3 HTML fixtures (one each for in-stock, sold-out, preorder)

### 3.3 Pipeline Flow

```
[Scheduler] per-source cron trigger
     ↓
[discover()] collect page URLs (listing or detail)
     ↓
[Fetcher] GET per URL (conditional: If-None-Match / If-Modified-Since)
     ├─ 304 Not Modified → skip (bump last_seen_at only)
     └─ 200 OK → compute body hash
           ├─ content_hash unchanged → skip
           └─ changed → persist raw_snapshot, then parse_page() (N items if listing)
     ↓
[Normalizer] RawItem → NormalizedListing
     ↓
[EntityResolver] assign release_id (merge or create)
     ↓
[EventDetector] diff against previous listing state → listing_events
     ↓
[NotificationDispatcher] match watchlists → enqueue APNs / email
```

### 3.4 Crawling Ethics and Legal Compliance (Mandatory)

Agents must encode these rules without exception.

| Rule | Implementation |
|---|---|
| Honor robots.txt | Parse with `urllib.robotparser` at the start of each crawl. Never request `Disallow`ed paths |
| Rate limiting | **Max 0.5 req/s per source**, ≤ 2 concurrent connections. `asyncio.Semaphore` plus jitter |
| Identify yourself | `User-Agent: VinylRadar/1.0 (+https://<domain>/about; contact@<domain>)` |
| Conditional requests | Cache ETag / Last-Modified to minimize traffic |
| Minimize reuse of protected content | **Store metadata only** (title, artist, price, stock, release date). Do not store product descriptions or review text. Store thumbnail URLs only; never copy images to your own CDN |
| Attribution | Display the source name on every surface and out-link to the original product page |
| No circumvention | Never bypass CAPTCHAs or bot protection, never access login-gated areas, never reverse-engineer private internal APIs |
| Backoff and disable | On 429/403, exponential backoff, then auto-disable that source and alert the operator |
| Notify in advance | Before public launch, email each source operator explaining the project and asking about partnership or an official feed |

> **Legal context**: In Korea the relevant considerations include database producers' rights under the Copyright Act (Arts. 91–98), unauthorized use of another's output under the Unfair Competition Prevention Act (Art. 2(1)(ch)), and each site's Terms of Service. A design that harvests **small volumes of factual metadata, links back to the source, and complements rather than substitutes for the original** is generally lower-risk — but this is not legal advice. If you intend to operate publicly or monetize, obtain professional review. For a personal learning or portfolio project, **private operation plus prior consent from source operators** is the safest path.

---

## 4. Data Model

### 4.1 Conceptual Model

- **`listing`** — one product page at one seller. Separate per source.
- **`release`** — one physical edition, identified by catalog number plus variant.
- **`master`** — optional grouping of editions of the same album (v1.1).

> Example: the limited color pressing of Silica Gel's *Machine Boy* exists as a `listing` at both Gimbab Records and Secondtrack, merged into one `release`. The black pressing and the clear pressing are **different `release` rows**.

### 4.2 Schema (PostgreSQL DDL)

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

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

CREATE TABLE raw_snapshots (
    id            BIGSERIAL PRIMARY KEY,
    source_id     TEXT NOT NULL REFERENCES sources(id),
    url           TEXT NOT NULL,
    http_status   INT  NOT NULL,
    content_hash  TEXT NOT NULL,            -- sha256(body)
    body_path     TEXT,                     -- local/S3 path; bodies are not stored in the DB
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON raw_snapshots (source_id, fetched_at DESC);
CREATE INDEX ON raw_snapshots (content_hash);

CREATE TABLE artists (
    id           BIGSERIAL PRIMARY KEY,
    name_display TEXT NOT NULL,
    name_ko      TEXT,
    name_en      TEXT,
    name_norm    TEXT NOT NULL,
    mbid         UUID UNIQUE,               -- MusicBrainz ID
    UNIQUE (name_norm)
);
CREATE INDEX ON artists USING gin (name_norm gin_trgm_ops);

CREATE TABLE releases (
    id                BIGSERIAL PRIMARY KEY,
    title             TEXT NOT NULL,
    title_norm        TEXT NOT NULL,
    primary_artist_id BIGINT REFERENCES artists(id),
    label             TEXT,
    catalog_no        TEXT,
    barcode           TEXT,                 -- UPC/EAN. Highest-confidence merge key
    format            TEXT,                 -- 'LP','2LP','7INCH','BOXSET'
    variant           TEXT,                 -- 'Clear Vinyl','Limited 300'
    is_limited        BOOLEAN NOT NULL DEFAULT FALSE,
    release_date      DATE,
    -- ── schedule notification fields (ADR-0005) ───────────────
    preorder_opens_at  TIMESTAMPTZ,        -- notification trigger
    preorder_closes_at TIMESTAMPTZ,        -- only manual entry can fill this
    curation          TEXT NOT NULL DEFAULT 'MANUAL'
                      CHECK (curation IN ('MANUAL','CRAWLED')),
    is_published      BOOLEAN NOT NULL DEFAULT FALSE,  -- drafts stay out of public API
    notes             TEXT,                -- operator notes (private)
    -- ──────────────────────────────────────────────────────────
    country           TEXT,
    discogs_id        BIGINT,
    cover_url         TEXT,
    master_id         BIGINT REFERENCES releases(id),  -- reserved for v1.1
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
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

-- Purchase links for manually curated schedules (ADR-0005)
-- listings is not reused: source_item_id and content_hash are NOT NULL there and
-- do not exist for manual entries. Relaxing them would weaken the harvester's invariants.
CREATE TABLE release_links (
    id         BIGSERIAL PRIMARY KEY,
    release_id BIGINT NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    source_id  TEXT REFERENCES sources(id),   -- linked when the shop is a known source
    shop_name  TEXT NOT NULL,                 -- free text for unregistered shops
    url        TEXT NOT NULL,
    price_krw  NUMERIC(12,0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (release_id, url)
);
CREATE INDEX ON release_links (release_id);

CREATE TABLE listings (
    id               BIGSERIAL PRIMARY KEY,
    source_id        TEXT NOT NULL REFERENCES sources(id),
    source_item_id   TEXT NOT NULL,
    url              TEXT NOT NULL,
    release_id       BIGINT REFERENCES releases(id),   -- NULL until resolved
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

CREATE TABLE listing_events (
    id           BIGSERIAL PRIMARY KEY,
    -- Manual schedule events have no listing (ADR-0005); release_id is the anchor.
    listing_id   BIGINT REFERENCES listings(id) ON DELETE CASCADE,
    release_id   BIGINT REFERENCES releases(id),
    event_type   TEXT NOT NULL CHECK (event_type IN
                 -- time-driven (manual curation, ADR-0005)
                 ('SCHEDULE_ADDED','SCHEDULE_CHANGED',
                  'PREORDER_OPENS_SOON','PREORDER_OPEN','RELEASED',
                 -- diff-driven (harvesting, M3)
                  'NEW_LISTING','RESTOCK','SOLD_OUT',
                  'PRICE_DROP','PRICE_RISE','DELISTED')),
    CHECK (listing_id IS NOT NULL OR release_id IS NOT NULL),
    old_value    JSONB,
    new_value    JSONB,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Events invalidated by a schedule change (T-119). Marked, never deleted --
    -- the row records what was sent, and notification_deliveries references it.
    superseded_at TIMESTAMPTZ
);
CREATE INDEX ON listing_events (occurred_at DESC);
CREATE INDEX ON listing_events (release_id, occurred_at DESC);
-- Both the feed and the idempotency check scan only live events.
CREATE INDEX ON listing_events (release_id, occurred_at DESC) WHERE superseded_at IS NULL;

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
    target_ref  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, target_type, target_ref)
);

-- Push subscriptions (ADR-0006)
-- `token` means different things per platform: a push endpoint URL for WEB,
-- an APNs device token for IOS.
CREATE TABLE device_tokens (
    id          BIGSERIAL PRIMARY KEY,
    -- Web Push subscriptions are self-identifying, so no account is required.
    -- Stays NULL until the account system lands (M4).
    user_id     BIGINT REFERENCES users(id) ON DELETE CASCADE,
    platform    TEXT NOT NULL CHECK (platform IN ('IOS','WEB')),
    token       TEXT NOT NULL,
    p256dh      TEXT,                     -- Web Push subscription public key (RFC 8291)
    auth        TEXT,                     -- Web Push auth secret
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    failure_count   INT NOT NULL DEFAULT 0,
    last_success_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, token)
);

-- Delivery log. **This is what structurally prevents re-sending** (ADR-0006 §5.2).
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

### 4.3 Normalization Rules (`normalize()`)

Normalization determines merge accuracy. It must be **deterministic** and fully covered by unit tests.

```
1. Unicode NFKC normalization
2. Lowercase
3. Strip decorative tokens (regex):
   [LP] [2LP] (LP) (Vinyl) (한정반) (Limited) (Deluxe Edition)
   (Remastered) (Reissue) (Color Vinyl) (Clear) (180g) [수입] [국내반]
   → but retain the stripped tokens as `variant` candidates
4. Remove punctuation / special characters → replace with a single space
5. Collapse repeated whitespace, trim
6. Apply the artist alias dictionary:
   "실리카겔" ↔ "Silica Gel", "새소년" ↔ "SE SO NEON",
   "검정치마" ↔ "The Black Skirts", etc. — managed as seed data in an alias table
7. Drop a leading "The " (artist names only)
```

**Format parsing:**

| Source pattern | Normalized |
|---|---|
| `LP`, `1LP`, `Vinyl` | `LP` |
| `2LP`, `Double LP`, `2xLP` | `2LP` |
| `7"`, `7인치`, `7 inch` | `7INCH` |
| `LP+CD`, `LP & CD` | `LP_CD` |
| `Box`, `박스세트` | `BOXSET` |

### 4.4 Entity Resolution

Apply stages in confidence order; **stop at the first match**.

| Stage | Condition | Confidence | Action |
|---|---|---|---|
| S1 | Exact `barcode` match | 1.00 | Merge immediately |
| S2 | `catalog_no` match AND `label_norm` match | 0.95 | Merge immediately |
| S3 | `artist_norm` match AND `title_norm` similarity ≥ 0.90 AND `variant` match AND release year diff ≤ 1 | 0.88 | Merge immediately |
| S4 | As S3 but similarity 0.70–0.90 | 0.60–0.88 | Queue into `merge_candidates`, **do not merge** |
| S5 | No match | — | Create a new `release` |

**Notes for agents:**
- If `variant` differs (e.g. black vs clear), **never merge.** To a collector these are different products.
- Merges must be reversible: only mutate `listings.release_id`; never delete `listings` rows.
- **Precision outweighs recall.** A wrong merge damages trust far more than a missed merge.

### 4.5 Event Detection

Compare the incoming `RawItem` against the stored `listings` state.

| Condition | Event |
|---|---|
| `source_item_id` not previously seen | `NEW_LISTING` |
| `COMING_SOON`/`UNKNOWN` → `PREORDER` | `PREORDER_OPEN` |
| `SOLD_OUT` → `IN_STOCK` | `RESTOCK` |
| `IN_STOCK`/`PREORDER` → `SOLD_OUT` | `SOLD_OUT` |
| `price_krw` drops ≥ 5% | `PRICE_DROP` |
| `price_krw` rises ≥ 5% | `PRICE_RISE` |
| URL 404 / absent on 3 consecutive crawls | `DELISTED` |

`PREORDER_OPEN` is the **highest notification tier** and dispatches immediately. Others batch according to user preference (immediate or daily digest).

> That table is the **diff rule set for harvesting (M3)**. Today (M2) the operator enters
> times directly, so no diff engine is needed and only the time-driven rules below run.

#### 4.5.1 Time-driven events (M2, current)

Every 60 seconds the scheduler asks "is there an event that should exist by now but doesn't?"

| Condition | Event |
|---|---|
| Operator publishes a schedule | `SCHEDULE_ADDED` |
| **A published schedule's times are edited** | `SCHEDULE_CHANGED` |
| `preorder_opens_at` comes within 24 hours | `PREORDER_OPENS_SOON` |
| `preorder_opens_at` passes | `PREORDER_OPEN` |
| `release_date` arrives | `RELEASED` |

Idempotency is decided by **event existence**, never by mutable state such as
`is_published` — otherwise unpublish/republish sends the same notification twice.

#### 4.5.2 A schedule change supersedes the events it produced (T-119)

If a preorder moves from 17:00 to 19:00, the `PREORDER_OPENS_SOON` and `PREORDER_OPEN`
produced by the old time **lose their meaning**. Leaving them breaks two things at once.

1. The feed keeps an alert stating the old time next to one stating the new time, and
   the reader cannot tell which to trust
2. The idempotency check counts them as "already sent", so **no preorder alert fires at
   19:00** — the one moment this product must not miss

So they are stamped with `superseded_at`. They are **not deleted**: the row records what
was actually sent to subscribers, and `notification_deliveries` references it. Having
sent something is not revocable.

| Changed field | Superseded events |
|---|---|
| `preorder_opens_at` | `PREORDER_OPENS_SOON`, `PREORDER_OPEN` |
| `release_date` | `RELEASED` |
| `preorder_closes_at` | (none — no event is keyed to the closing time) |

**Only what the change actually affects.** Superseding `PREORDER_OPEN` because the closing
time moved would resend the same alert for no reason. `SCHEDULE_ADDED` is never superseded —
the schedule was still added, whatever its times became.

#### 4.5.3 The feed carries one event per release (T-118)

When `SCHEDULE_ADDED → PREORDER_OPENS_SOON → PREORDER_OPEN` accumulate on one album, the
top three rows of the feed are the same album. Only the last one is useful.

`/v1/feed` and `/v1/feed.rss` share **one query** (`vinyl_api/feed_query.py`). Holding
separate copies means one gets fixed and the other silently drifts. Push notifications
collapse the same way via `tag=release-<id>`, so all three surfaces follow one rule.

---

## 5. API Design

### 5.1 Conventions

- Base path: `/v1`
- Auth: `Authorization: Bearer <JWT>` (required only for watchlist and device endpoints)
- Pagination: **cursor-based** (`?cursor=<opaque>&limit=20`, max 100)
- Responses: `snake_case` JSON; timestamps in ISO-8601 UTC (`2026-08-20T04:00:00Z`)
- Errors: RFC 9457 Problem Details
- Caching: list responses carry `ETag` and `Cache-Control: public, max-age=60`

### 5.2 Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/feed` | Unified timeline, event-driven, newest first |
| `GET` | `/v1/releases` | Release list. Filters: `from`, `to`, `format`, `source`, `is_limited`, `stock_status`, `label`, `artist_id` |
| `GET` | `/v1/releases/{id}` | Detail plus the array of `listings` (price/stock comparison across sellers) |
| `GET` | `/v1/search?q=` | Unified search over artist, title, label (trigram) |
| `GET` | `/v1/artists/{id}` | Artist detail and releases |
| `GET` | `/v1/events` | Event stream, `?since=`, `?type=` |
| `GET` | `/v1/sources` | Source list with last crawl time and health |
| `POST` | `/v1/watchlist` | Add watchlist item |
| `GET` | `/v1/watchlist` | List watchlist |
| `DELETE` | `/v1/watchlist/{id}` | Remove watchlist item |
| `GET` | `/v1/push/public-key` | VAPID public key (needed to subscribe; no auth) |
| `POST` | `/v1/push/subscribe` | Register a Web Push subscription (no auth) |
| `DELETE` | `/v1/push/subscribe` | Unsubscribe |
| `POST` | `/v1/devices` | Register / refresh APNs token |
| `POST` | `/v1/auth/apple` | Sign in with Apple token exchange |
| `GET` | `/v1/feed.rss` | RSS 2.0 feed (unauthenticated; distribution channel) |
| `GET` | `/v1/releases.ics` | Release-date calendar (iCalendar) |
| `GET` | `/healthz` | Health check including DB connectivity |
| `GET` | `/metrics` | Prometheus metrics |

### 5.2-1 Operator API (manual curation, [ADR-0005](adr/0005-manual-curation-first.md))

Auth is a single `X-Admin-Key: <ADMIN_API_KEY>` header. **No account system** — building OAuth
for a single operator would be over-engineering.

| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/releases` | Create a schedule (draft, `is_published=false`) |
| `PATCH` | `/admin/releases/{id}` | Edit |
| `POST` | `/admin/releases/{id}/publish` | Publish — emits `SCHEDULE_ADDED` |
| `DELETE` | `/admin/releases/{id}` | Only unpublished drafts may be deleted |
| `POST` | `/admin/releases/{id}/links` | Add a purchase link |
| `GET` | `/admin/releases` | List including drafts |

**Public endpoints expose only `is_published=true`.** Leaking drafts would leak unannounced releases.

### 5.3 Example Response

```jsonc
// GET /v1/releases/1042
{
  "id": 1042,
  "title": "Machine Boy",
  "artist": { "id": 88, "name_display": "실리카겔", "name_en": "Silica Gel" },
  "label": "Magic Strawberry Sound",
  "catalog_no": "MSS-0142",
  "barcode": "8809876543210",
  "format": "2LP",
  "variant": "Clear Vinyl",
  "is_limited": true,
  "release_date": "2026-09-12",
  "cover_url": "https://…",          // original URL, not proxied
  "listings": [
    {
      "source": { "id": "gimbab", "display_name": "Gimbab Records" },
      "url": "https://…",
      "price_krw": 58000,
      "stock_status": "PREORDER",
      "last_seen_at": "2026-08-20T03:58:12Z"
    },
    {
      "source": { "id": "secondtrack", "display_name": "Secondtrack" },
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

## 6. Repository Layout

```
vinyl-radar/
├─ CLAUDE.md                        # persistent agent context (§0 summary + conventions)
├─ README.md
├─ compose.yaml                     # local dev stack
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
│  │  │  ├─ feed_query.py           # newest event per release — shared by feed and rss
│  │  │  ├─ icalendar.py            # RFC 5545 generation (hand-written)
│  │  │  ├─ rss.py                  # RSS 2.0 + RFC 822 generation (hand-written)
│  │  │  ├─ problems.py             # RFC 9457 error responses
│  │  │  ├─ pagination.py           # keyset cursor
│  │  │  ├─ caching.py              # ETag / Cache-Control
│  │  │  ├─ serializers.py
│  │  │  ├─ schemas/
│  │  │  └─ services/
│  │  ├─ tests/
│  │  ├─ pyproject.toml
│  │  └─ Dockerfile
│  ├─ collector/                    # scrapers + scheduler
│  │  ├─ src/vinyl_collector/
│  │  │  ├─ scheduler.py
│  │  │  ├─ fetcher.py              # httpx, rate limit, robots, conditional requests
│  │  │  ├─ pipeline.py
│  │  │  └─ cli.py                  # `collector run --source gimbab --dry-run`
│  │  ├─ tests/
│  │  │  └─ fixtures/<source_id>/*.html
│  │  ├─ pyproject.toml
│  │  └─ Dockerfile
│  ├─ web/                          # Next.js 16 (PWA)
│  │  ├─ app/
│  │  │  ├─ page.tsx                # feed
│  │  │  ├─ manifest.ts             # web app manifest (home-screen install = iOS push prerequisite)
│  │  │  ├─ api/push/               # same-origin proxy (ADR-0007)
│  │  │  ├─ subscribe/PushToggle.tsx  # push on/off (client component)
│  │  │  ├─ releases/[id]/page.tsx
│  │  │  ├─ search/page.tsx
│  │  │  └─ artists/[id]/page.tsx
│  │  ├─ public/
│  │  │  ├─ sw.js                   # service worker — push receipt, notification click
│  │  │  └─ icon-*.png              # PWA icons (192/512/maskable/apple-touch)
│  │  ├─ lib/api.ts                 # generated OpenAPI client (server components only)
│  │  ├─ lib/push.ts                # browser subscription
│  │  ├─ lib/proxy.ts               # API forwarding
│  │  ├─ components/
│  │  └─ Dockerfile
│  └─ ios/                          # Xcode project
│     └─ VinylRadar/
│        ├─ VinylRadarApp.swift
│        ├─ Features/{Feed,Search,ReleaseDetail,Watchlist,Settings}/
│        ├─ Core/{APIClient,Models,DesignSystem}/
│        └─ Notifications/
├─ packages/
│  └─ core/                         # shared Python package for api + collector
│     ├─ src/vinyl_core/
│     │  ├─ adapters/
│     │  │  ├─ base.py
│     │  │  ├─ gimbab.py
│     │  │  ├─ secondtrack.py
│     │  │  ├─ poclanos.py
│     │  │  └─ registry.py          # adapter auto-registration
│     │  ├─ models/                 # SQLAlchemy ORM
│     │  ├─ normalize.py
│     │  ├─ resolver.py
│     │  ├─ events.py
│     │  ├─ testing.py                # edge-case catalog shared by all output surfaces
│     │  └─ aliases.yaml            # artist alias dictionary
│     ├─ tests/
│     └─ pyproject.toml
├─ migrations/                      # Alembic
├─ backups/                        # pg_dump output (never committed)
├─ infra/
│  ├─ nginx/
│  ├─ prometheus/
│  └─ deploy.sh
├─ docs/
│  ├─ BLUEPRINT.ko.md
│  ├─ BLUEPRINT.en.md               # this document
│  ├─ adapters/<source_id>.md       # per-source survey record
│  ├─ adr/NNNN-*.md
│  └─ api/openapi.json              # generated in CI
└─ .github/workflows/
   ├─ ci.yml
   ├─ deploy.yml
   └─ parser-canary.yml             # once-daily live parser verification
```

---

## 7. Web Frontend

### 7.1 Screens

| Screen | Route | Key elements |
|---|---|---|
| Feed | `/` | Event timeline; `PREORDER_OPEN` badge emphasized; source filter chips |
| Calendar | `/calendar` | Monthly grid keyed on release date |
| Detail | `/releases/[id]` | Cover, metadata, per-seller price table, out-link buttons |
| Search | `/search` | Incremental search with artist/label/format facets |
| Artist | `/artists/[id]` | Discography plus watch button |
| Watchlist | `/watchlist` | Requires login |

### 7.2 Design Direction

- **Information density first.** Collectors scan many items per screen; do not over-pad cards.
- **Visual priority of state**: `Preorder open` > `Restock` > `New` > `Price change`. Use **label + icon combinations rather than color alone**, for color-vision accessibility.
- Dark mode by default. Cover art is the focal point, so keep backgrounds neutral.
- Allow source domains via `next/image` `remotePatterns`, but **do not store images locally.**

### 7.3 Generated API Client

Generate types from the FastAPI-produced `openapi.json`. Hand-written types are prohibited.

```bash
# apps/web
npx openapi-typescript ../../docs/api/openapi.json -o lib/api-types.ts
```

---

## 8. iOS Application

### 8.1 Implementation Approach — Analysis and Recommendation

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| **A. WKWebView wrapper** | 1–2 days of work; 100% web reuse | Real risk of rejection under App Store Review Guideline **4.2 (Minimum Functionality)**. No native push, haptics, or offline cache. Scroll feel immediately reads as "web" | Not recommended |
| **B. Native SwiftUI on the shared REST API** | Genuinely native UX; push, widgets, Live Activities, Spotlight. Client generated from OpenAPI | Screens must be built separately | **Recommended** |
| C. Hybrid (native shell, some screens in web view) | Compromise | Inherits the drawbacks of both stacks; higher maintenance complexity | Conditional |

**Recommendation**: adopt **Option B (native SwiftUI)**, for three reasons.

1. The stated goal is a **"more user-friendly"** iOS app. A web-view wrapper cannot, by definition, be friendlier than the web.
2. The core value of this service is **push notification** the instant a preorder opens. That requires native integration.
3. Because the design is API-first, web and iOS share the same contract — the web work is not wasted. "Build the web and leverage it" is realized through **shared API and domain model, not shared UI code.**

The counter-argument is stated fairly: if shipping something to iOS quickly matters more (learning or portfolio velocity), launching with Option A and converting screen-by-screen is defensible. In that case, implement at minimum the **push notifications, settings screen, and tab bar natively** to reduce 4.2 exposure.

### 8.2 Native App Structure

```
VinylRadar/
├─ VinylRadarApp.swift              @main, DI container
├─ Core/
│  ├─ APIClient.swift               URLSession + async/await
│  ├─ Generated/                    swift-openapi-generator output
│  ├─ Models/
│  ├─ KeychainStore.swift           JWT storage
│  └─ DesignSystem/                 Color, Typography, Badge
├─ Features/
│  ├─ Feed/          FeedView, FeedViewModel (@Observable)
│  ├─ Search/
│  ├─ ReleaseDetail/
│  ├─ Watchlist/
│  └─ Settings/
├─ Notifications/
│  ├─ PushRegistrar.swift           UNUserNotificationCenter + APNs registration
│  └─ NotificationHandler.swift     deep link → ReleaseDetail
└─ Widgets/                         v1.1: "this week's releases" widget
```

**Key decisions**
- Minimum target: iOS 17.0 (enables the `@Observable` macro)
- Architecture: MVVM — `@Observable` view models with SwiftUI `NavigationStack`
- Networking: [`swift-openapi-generator`](https://github.com/apple/swift-openapi-generator) turns `openapi.json` into a Swift client. **Hand-written models prohibited**
- Auth: Sign in with Apple (minimal signup friction, satisfies App Store requirements)
- Images: `AsyncImage` with an `NSCache` memory cache, loading original URLs directly
- Offline: SwiftData cache of the 200 most recent feed items

### 8.3 Push Notification Pipeline

```
EventDetector → emits PREORDER_OPEN
   ↓
match watchlist_items (ARTIST / LABEL / RELEASE / KEYWORD)
   ↓
NotificationDispatcher (FastAPI background task)
   ↓
aioapns → APNs (token-based auth, .p8 key)
   ↓
iOS: NotificationHandler → deep link vinylradar://release/1042
```

**Prerequisites**: Apple Developer Program ($99/yr), APNs Auth Key (.p8), Bundle ID, Push Notifications capability.

### 8.4 Division of Labor: VSCode vs Xcode (Important)

VSCode can be the primary IDE, but the iOS portion carries hard constraints.

| Task | VSCode | Xcode |
|---|---|---|
| All Python / TypeScript | ✅ | not needed |
| Editing Swift source | ✅ (Swift extension + SourceKit-LSP) | ✅ |
| SwiftUI previews | ❌ | ✅ required |
| Simulator run / debugging | ❌ | ✅ required |
| Code signing, provisioning, archiving | ❌ | ✅ required |
| App Store Connect upload | ❌ | ✅ required |

**Conclusion**: use VSCode for backend and web, Xcode alongside it for iOS. Claude Code can run in the VSCode terminal and edit Swift files under `apps/ios/`, with build verification performed in Xcode. (`xcodebuild` works from the VSCode terminal, but previews and visual debugging have no substitute.)

---

## 9. Development Environment and Operations

### 9.1 Quick Start

```bash
git clone <repo> && cd vinyl-radar
cp .env.example .env

make up          # start postgres + api + collector + web
make migrate     # apply Alembic migrations
make seed        # seed sources table + load artist aliases

# manual single-source run (parse only, no DB writes)
docker compose exec collector collector run --source gimbab --dry-run --limit 5

# API docs: http://localhost:8000/docs
# Web:      http://localhost:3000
```

### 9.2 Recommended VSCode Extensions

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

### 9.3 Test Strategy

| Layer | Method | Tooling |
|---|---|---|
| Adapter parsing | Golden tests against **stored HTML fixtures**. No network access | pytest + local fixtures |
| Normalization | Table-driven unit tests (≥ 30 input/expected pairs) | `pytest.mark.parametrize` |
| Resolution | Precision/recall measured on 100 labeled pairs. **CI fails on regression** | pytest + metric thresholds |
| API | Integration tests against a real PostgreSQL container | pytest + testcontainers |
| Parser canary | **One live request per day per source**, verifying required fields exist. Auto-files a GitHub Issue on failure | separate workflow |

The parser canary is the primary defense against the worst failure mode — a site redesign that silently yields zero items. It is not optional.

### 9.3-1 Backup and Restore

**A volume only protects against accidental deletion; it does not prevent data loss.**
Disk failure, instance termination, a bad migration, or a stray `DROP TABLE` all defeat it.

```bash
make backup                          # timestamped dump into backups/
make restore FILE=backups/xxx.sql.gz # restore (overwrites current data)
```

| Item | Detail |
|---|---|
| Method | `pg_dump --clean --if-exists` piped through gzip; restored with `psql` |
| Frequency | At least daily in production (cron) |
| Location | **Must also live off the server** (e.g. S3). A backup on the same disk dies with it |
| Verification | An untested backup is not a backup. Rehearse restores periodically |

> ⚠️ The `-v` in `docker compose down -v` **deletes volumes**. Plain `docker compose down`
> used during deploys only removes containers and keeps the data. Do not confuse the two.

### 9.4 Observability

| Item | Implementation |
|---|---|
| Logging | `structlog` JSON output; `source_id`, `url`, `trace_id` are required fields |
| Metrics | `collector_items_parsed_total{source}`, `collector_parse_errors_total{source}`, `collector_run_duration_seconds{source}`, `collector_last_success_timestamp{source}` |
| Alert conditions | ① a source's `last_success_timestamp` exceeds 3× its cron interval ② `parse_errors / items_parsed > 0.1` ③ zero `NEW_LISTING` events in 24h |
| Error tracking | Sentry, with per-source tags on parse exceptions |

### 9.5 CI/CD

```yaml
# .github/workflows/ci.yml (abridged)
jobs:
  quality:
    - ruff check / ruff format --check
    - mypy packages/core apps/api apps/collector
    - pytest --cov (threshold 70%)
    - regenerate openapi.json and diff against committed copy → fail on mismatch
  web:
    - pnpm lint / tsc --noEmit / next build
  image:
    - buildx linux/arm64 → push to GHCR (main branch only)
```

`deploy.yml` SSHes to EC2, runs `docker compose pull && up -d`, verifies `/healthz`, and rolls back to the previous tag on failure.

### 9.6 Estimated Monthly Cost (USD)

| Item | Cost |
|---|---|
| EC2 t4g.small (1-yr reserved) | ~$9 |
| EBS 20 GB | ~$2 |
| Domain | ~$1 |
| Apple Developer Program | ~$8 (amortized $99/yr) |
| **Total** | **~$20** |

Oracle Cloud Always Free (ARM, 4 OCPU / 24 GB) can run this at $0 initially.

---

## 10. Task Backlog

Each task is written to be **independently verifiable**. Agents must cite the task ID while working.

### M0 — Walking Skeleton (complete)

> The original goal ("one source → DB → API → one screen") was superseded by
> [ADR-0005](adr/0005-manual-curation-first.md). M0 closes with the harvester components built and tested.
> T-008–T-012 move to M3 (harvesting resumed).

| ID | Task | Acceptance criteria |
|---|---|---|
| T-001 | Monorepo scaffolding, `compose.yaml`, `Makefile`, `.env.example` | `make up` brings up postgres + api; `/healthz` returns 200 |
| T-002 | `packages/core` SQLAlchemy models + initial Alembic migration | `make migrate` succeeds; all §4.2 tables exist |
| T-003 | Seed `sources` (gimbab / secondtrack / poclanos) | 3 rows present after `make seed` |
| T-004 | `SourceAdapter` protocol and `registry.py` | registry imports cleanly with no adapters implemented |
| T-005 | `fetcher.py`: robots.txt parsing, rate limiting, conditional requests, backoff | Unit test proves ≤ 0.5 req/s |
| T-006 | **Survey Gimbab Records** → write `docs/adapters/gimbab.md`, save 3 fixtures | Doc contains robots.txt verbatim, selector table, JS-requirement verdict |
| T-007 | Implement `gimbab.py` | All 3 fixtures parse into `RawItem` with correct field values |
| T-008 | `normalize.py` + 30 unit tests | All §4.3 rules pass |
| T-009 | `pipeline.py`: RawItem → listings upsert (1:1 release creation, no merging yet) | `collector run --source gimbab` populates the DB |
| T-010 | `GET /v1/releases` with cursor pagination | Exposed in OpenAPI; returns real data |
| T-011 | Next.js feed screen (SSR, no filters) | List renders at `localhost:3000` |
| **M0 done when** | Gimbab Records items are harvested and visible on the web page | |

### M1 — Manual Curation → Public Feed ([ADR-0005](adr/0005-manual-curation-first.md))

> Goal: **the operator enters a schedule and users can subscribe to it.** Core value ships without harvesting.

| ID | Task | Done when |
|---|---|---|
| T-101 | Migration: `releases` schedule columns + `release_links` | `make migrate` succeeds, matches §4.2 DDL |
| T-102 | Operator auth (`X-Admin-Key`) | 401 without/with wrong key, passes with correct key |
| T-103 | `POST/PATCH/DELETE /admin/releases` + `/links` | Create, edit, add links all work |
| T-104 | `POST /admin/releases/{id}/publish` | Emits exactly one `SCHEDULE_ADDED` event |
| T-105 | `GET /v1/releases`, `GET /v1/releases/{id}` (cursor pagination) | Includes a test that **drafts are not exposed** |
| T-106 | `GET /v1/feed` — timeline ordered by imminent preorder | Mixed event/schedule ordering |
| T-107 | `GET /v1/releases.ics` (iCalendar) | Verified by subscribing in a real calendar app |
| T-108 | `GET /v1/feed.rss` (RSS 2.0) | Verified in a feed reader |
| T-109 | Operator entry screen (minimal web form) | Schedule created from the browser |
| T-110 | User feed and calendar screens (Next.js SSR) | Monthly grid renders at `localhost:3000` |

### M2 — Time-Driven Notifications

> Goal: **the notification arrives when preorders open.** Build the no-account subscription paths first.

| ID | Task | Done when |
|---|---|---|
| T-111 | APScheduler + `preorder_opens_at` watcher | Long-running container, 1-minute resolution in logs |
| T-112 | Emit `PREORDER_OPENS_SOON` (24h) / `PREORDER_OPEN` / `RELEASED` | All three verified with clock manipulation |
| T-113 | Delivery idempotency (never send the same event twice) | Zero duplicates after scheduler restart |
| T-114 | **Web Push subscription** (VAPID keys, subscribe/unsubscribe API, schema) — [ADR-0006](adr/0006-web-push-first.md) | Browser subscribes and the row lands in the DB |
| T-115 | Sender + **idempotent delivery** (`notification_deliveries`) | Zero duplicate sends after a scheduler restart |
| T-116 | Retry, expired-subscription cleanup, silent-failure alerting | Deliberate failure alerts the operator; 410 deactivates the subscription |
| T-117 | Web subscribe UI (PWA manifest + service worker) — [ADR-0007](adr/0007-same-origin-push-proxy.md) | Notification received on a real device |
| T-118 | Feed collapsing (one event per release) + `SCHEDULE_CHANGED` (§4.5.1, §4.5.3) | One row per album in the feed; editing a schedule notifies |
| T-119 | Supersede and re-fire on schedule change (§4.5.2) | Moving a preorder time re-sends the open alert **at the new time** |

> **Web Push is the first channel** ([ADR-0006](adr/0006-web-push-first.md)). Email is not built.
> The APNs plan in §8.3 is deferred to iOS app launch, not cancelled.
> T-113 verified **event-creation** idempotency; **delivery** idempotency lands in T-115.

### M3 — Harvesting Resumed

> Goal: wire up the dormant harvester. Coexists with manual entries (distinguished by `curation`).
> **Trigger to start**: when manual entry becomes the bottleneck.

| ID | Task | Done when |
|---|---|---|
| T-121 | Narrow gimbab collection surfaces (new / preorder / restock only) | ≤ 5 requests per cycle |
| T-122 | `pipeline.py`: RawItem → listings upsert | Rows persisted after `collector run --source gimbab` |
| T-123 | `raw_snapshots` + `content_hash` skip | Log confirms parsing skipped on unchanged content |
| T-124 | Link harvested rows to `releases` (`curation='CRAWLED'`) | No collision with manual entries |
| T-125 | Extract expected-delivery date from titles | Parses all three observed forms |
| T-126 | Parser canary workflow | Deliberate selector break fails CI |
| T-127 | `secondtrack.py` adapter | Fixtures parse |
| T-128 | `poclanos.py` adapter | Fixtures parse |
| T-129 | Lightweight duplicate suppression (normalized title+artist, 7-day window) | Zero duplicate notifications for one release |

> **Deferred (not cancelled)**: former T-019 (alias dictionary), T-020 (resolver S1–S5),
> T-021 (merge review CLI), T-022 (per-shop comparison), T-025 (pg_trgm search).
> Per-shop price comparison and discography were confirmed non-core
> ([ADR-0005](adr/0005-manual-curation-first.md)), so they wait until actually needed.

### M4 — Accounts and Watchlist

| ID | Task | Acceptance criteria |
|---|---|---|
| T-029 | Sign in with Apple + JWT issuance | Token verification tests pass |
| T-030 | Watchlist CRUD API | All 4 target types work |
| T-031 | Watchlist ↔ event matching query | Unit tested, including keyword matching |
| T-032 | Web watchlist screen | CRUD works after login |

### M5 — iOS App

| ID | Task | Acceptance criteria |
|---|---|---|
| T-033 | Create Xcode project, wire swift-openapi-generator | Builds; generated client calls `/v1/feed` |
| T-034 | DesignSystem (Color / Typography / StatusBadge) | Dark mode supported |
| T-035 | FeedView + FeedViewModel | Infinite scroll, pull-to-refresh |
| T-036 | SearchView, ReleaseDetailView | Out-links open in Safari |
| T-037 | Sign in with Apple + Keychain | Session persists across relaunch |
| T-038 | WatchlistView | CRUD works |
| T-039 | SwiftData offline cache | Recent feed visible in airplane mode |

### M6 — Push Notifications

| ID | Task | Acceptance criteria |
|---|---|---|
| T-040 | `POST /v1/devices` + `device_tokens` | Token register/refresh works |
| T-041 | `aioapns` dispatcher | Successful send to APNs sandbox |
| T-042 | iOS push receipt + deep link | Tapping a notification opens the release detail |
| T-043 | Notification settings (immediate / daily digest / off) | Per-user preference respected |

### M7 — Operational Hardening

| ID | Task | Acceptance criteria |
|---|---|---|
| T-044 | `deploy.yml` + rollback script | Zero-downtime deploy on push to main |
| T-045 | Daily DB backup to S3 | One restore rehearsal completed |
| T-046 | Source auto-disable / recovery logic | 5 consecutive 429s disables the source and alerts |
| T-047 | Discogs API enrichment for catalog number / barcode | Measured improvement in merge recall |

---

## 11. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Source redesign breaks parsers | High | High | Parser canary (T-018), golden fixture tests, per-source alerting |
| Source operator requests blocking | High | Medium | Advance notice and partnership outreach (§3.4); `sources.is_enabled` allows instant shutoff |
| Bad merges erode trust | Medium | Medium | Precision-first policy, `merge_candidates` hold queue, reversible merges |
| Bot protection (Cloudflare etc.) | Medium | Medium | Re-evaluate the source. **Do not attempt circumvention — drop the source instead** |
| Notification too slow, limited edition missed | High | Medium | Shorten cron to 5–10 min for preorder-heavy sources; separate priority queue |
| App Store rejection | Medium | Low | Native implementation (Option B), clear content attribution, privacy policy page |
| Solo-developer burnout | Medium | Medium | M0–M3 delivers ~80% of the real value. Ship a genuinely useful state there and pause |

---

## 12. Roadmap Beyond v1

- **Discogs / MusicBrainz integration**: authoritative metadata, cover art, tracklists, `master_id` grouping
- **Price history graphs**: visualize `listing_events` as a time series
- **Wishlist → budget simulation**: total committed spend for the month
- **iOS widget / Live Activity**: countdown to preorder opening
- **Discogs collection sync**: cross-check against owned items to prevent duplicate purchases
- **International sources**: Bandcamp, Rough Trade, HHV, Diskunion — price comparison against domestic editions
- **Personalized recommendations**: content-based recommendation from ownership and watch history (the approach from the existing whisky recommender project transfers directly)

---

## 13. Glossary

| Term | Definition |
|---|---|
| Listing | One product page at one seller |
| Release | One physical edition, identified by catalog number plus variant |
| Variant | A physical difference within the same album (color, limited quantity, weight, inserts) |
| Entity Resolution | Merging listings from different sources into one canonical release |
| Fixture | A stored real-world HTML snapshot used in tests |
| Canary | A scheduled low-volume live request that verifies parsers still work |
| Walking Skeleton | The minimal end-to-end path through every layer |
