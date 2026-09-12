# Vinyl Radar — Vinyl Release and Preorder Schedule Blueprint (English)

> **Reviewed: 2026-09-11 · Version 1.1.0**. Current behavior is described from source, migrations and runtime configuration.
> When implementation and prose disagree, update the prose to match implementation. Planned features are not current behavior or instructions to enable them.
> Maintain this alongside the [Korean edition](BLUEPRINT.ko.md); reconcile the Korean text first when the editions disagree, then translate.

## 0. Agent Directives (READ FIRST)

1. Follow the user-authorized scope. For backlog work, announce the existing `T-XXX` and complete one task at a time. Do not invent IDs for maintenance or reviews.
2. Distinguish existing paths from reserved future paths in §6. Do not create undefined top-level directories.
3. Automated tests must not request live external sites. Use saved HTML fixtures and fake push senders. `collector run --dry-run` makes live requests and is not an offline test.
4. Follow §3.4: at most 0.5 req/s per source, at most two concurrent connections, honor robots and use metadata only.
5. Run `make lint` and `make test` for implementation changes; also run web lint, Node tests and build for web changes. For documentation-only edits, check paths, commands and contracts without restarting services.
6. Draft an ADR for genuinely new architectural decisions. Do not request approval again for corrections within an already authorized direction.
7. Use `venv/bin/python`, Make targets or container Python.
8. Preserve existing data, keys and backups. Destructive actions require authorization; prefer isolated schemas and rollback in tests. Shared-DB cleanup must use exact IDs created by that test run.

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

> These are product targets, not measured results or guaranteed SLAs. Slack operator alerts are implemented, but external monitoring for host/process outages is absent.

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

### 2.1 Current Execution Flow

```text
Operator → localhost:8000/admin → FastAPI → PostgreSQL
                                draft → publish → SCHEDULE_ADDED
PostgreSQL ← collector: 60-second tick → time events → deliveries → WebPushSender
                                                                  ↓
                                           browser push service → sw.js → notification
Internet → Tailscale Funnel → localhost:3000 → Next.js → internal FastAPI
                                                ├ feed/detail/calendar/subscribe
                                                ├ /api/push/* proxies
                                                └ /v1/feed.rss and /v1/releases.ics proxies
```

APScheduler in one collector generates events and dispatches deliveries in the same tick.
There is no separate message broker, APNs sender or watchlist matching. Adapters and Fetcher
are wired only for manual `collector run --dry-run`; scheduled collection and persistence are planned for M3.

### 2.2 Current Stack and Deferred Work

| Layer | Implemented | Deferred / absent |
|---|---|---|
| Python | Python ≥3.12, pip editable, Pydantic v2, SQLAlchemy 2 async | No separate package workspace tool |
| API | FastAPI ≥0.121, admin key, public reads and anonymous push subscriptions | JWT, accounts and search APIs |
| Database | PostgreSQL 16, pg_trgm/unaccent, Alembic | Search/resolution services using these extensions |
| Scheduler/push | APScheduler every 60 seconds, DB deliveries, pywebpush via asyncio.to_thread | Broker, daily digest and APNs |
| Collection components | httpx async, selectolax, urllib.robotparser, three adapters | Scheduled persistence, normalization and resolution |
| Web | Next.js 16.3.3 App Router, React 19, Tailwind 4, npm, PWA | SwiftUI app and generated clients |
| Runtime | Docker Compose, Mac mini/colima with Funnel for public testing | EC2/GHCR/SSH deployment |
| Monitoring/automation | structlog, /healthz, Slack failure alerts, GitHub Actions CI, local tests and backup scripts | Prometheus, Sentry, external liveness monitoring and automated deployment |

---

## 3. Collection Layer

### 3.1 Implemented Adapter Interface

`packages/core/src/vinyl_core/adapters/base.py` defines the contract. `@register` and module discovery
handle registration without registry edits. A new source still needs fixtures, tests, survey notes and seed data.

```python
from collections.abc import AsyncIterator
from typing import Protocol
from vinyl_core.adapters.base import RawItem

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

Required RawItem fields are source_id, source_item_id, url, title_raw and stock_status.
Optional metadata defaults to None, extra to a new dict, and fetched_at to current UTC. Won prices reject
negative/fractional values; fetched_at requires a timezone. Parse failures return an empty list and log the failure.
`vinyl_collector.bridge.FetcherPageAdapter` supplies PageFetcher without importing collector into core.

### 3.2 Source Survey and Implementation Notes

Adapters for gimbab, secondtrack and poclanos all exist today. M0/M1 priorities below describe the original survey order, not current product milestone status.

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

### 3.3 Collection Pipeline Plan (M3, Not Implemented)

The current CLI only runs discover → Fetcher → parse_page → output. It does not persist rows, update last_seen_at or skip unchanged hashes.
Fetcher computes body hashes and keeps ETag/Last-Modified in memory, without persistence. The diagram below is future wiring;
account matching and APNs are also inactive. Email is not a planned channel (ADR-0006).

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
[NotificationDispatcher] match watchlists → enqueue configured push channels (future)
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

**Policy versus enforcement:** the table states required policy, not completed automation. Repeated 403/429 responses
currently cause Fetcher to back off and raise SourceBlockedError; the CLI stops. Persistent source deactivation and
operator alerts remain M3 work. Failed robots retrieval denies access, except 404 means no robots file. Longest-match
and wildcard gaps in urllib.robotparser are documented in ADR-0003 and two xfail tests. Never send external outreach
without user authorization. Legal/site descriptions below are original research context, not a fresh verification of current law or sites.

> **Legal context**: In Korea the relevant considerations include database producers' rights under the Copyright Act (Arts. 91–98), unauthorized use of another's output under the Unfair Competition Prevention Act (Art. 2(1)(ch)), and each site's Terms of Service. A design that harvests **small volumes of factual metadata, links back to the source, and complements rather than substitutes for the original** is generally lower-risk — but this is not legal advice. If you intend to operate publicly or monetize, obtain professional review. For a personal learning or portfolio project, **private operation plus prior consent from source operators** is the safest path.

---

## 4. Data Model

### 4.1 Conceptual Model

- **`listing`** — one product page at one seller. Separate per source.
- **`release`** — one physical edition, identified by catalog number plus variant.
- **`master`** — optional grouping of editions of the same album (v1.1).

> Example: the limited color pressing of Silica Gel's *Machine Boy* exists as a `listing` at both Gimbab Records and Secondtrack, merged into one `release`. The black pressing and the clear pressing are **different `release` rows**.

### 4.2 Schema (PostgreSQL DDL)

This DDL summarizes current models for reading. Apply changes through Alembic revisions in `migrations/versions/`.
Existing tables do not imply implemented accounts, crawl persistence or resolution. ORM onupdate behavior is not a DDL trigger.

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

> This is planned normalization work. Manual input currently uses only admin.normalize_name (NFKC, casefold and whitespace collapse); aliases and format parsing are absent.

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

> EntityResolver and the merge-review CLI are absent. The following rules are deferred design, not running policy.

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

A priority queue and daily digest are not implemented. Current M2 handles all notifiable events in the same
60-second tick, processing PENDING before FAILED retries, then creation time/ID ascending, at most 500 per dispatch.

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

Editing while unpublished also supersedes old schedule events. Authorized deletion of the release itself
is the exception: its events and deliveries are removed (§5.2-1).

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

#### 4.5.3 Web Feed, RSS and Device Notifications

- `/v1/feed` returns one row per published release, including releases without events. SQL sorting precedes the limit.
  Default `sort=imminent` uses preorder opening, or release date at KST midnight: future starts first,
  most recent past starts next, unknown last. `sort=recent` uses descending `updated_at`, labeled **최근 변경순**.
- The web shows preorder opening or release date on the right. API `FeedItem.at` is an event/schedule timestamp,
  not the web display source. Status is calculated at render time from the schedule window or release date.
- RSS selects at most 50 latest non-superseded events, one per published release, using `latest_event_per_release()`.
  `/v1/feed` shares this event helper, but has its own release selection and sorting query.
- Push tags are `release-<id>-<event_type>`: different event types remain separate notifications;
  the same type emitted after rescheduling replaces its previous notification.

---

## 5. API Design

### 5.1 Current Contract

- Tables below reflect actual routers. Exact schemas are in [openapi.json](api/openapi.json), generated by `make openapi`.
- Public reads and Web Push subscriptions require no account. Admin JSON APIs require `X-Admin-Key`.
  `/admin` HTML serves the login interface and is excluded from OpenAPI.
- Only `/v1/releases` has cursor pagination (`limit` defaults to 20, range 1–100).
  It sorts by preorder opening ascending, NULL last, then ID ascending; past schedules are not automatically excluded.
- `/v1/releases` and `/v1/feed` return ETags and 60-second cache headers. RSS uses 300 seconds and ICS 600.
  Web API fetches and same-origin proxy responses use `no-store`.
- JSON is snake_case, timestamps are timezone-aware UTC, and won prices are integers. API errors use RFC 9457
  Problem Details; proxy-generated errors can instead be `{detail: ...}` JSON.

### 5.2 Implemented Public Endpoints

| Method | Path | Current behavior |
|---|---|---|
| GET | `/v1/feed` | One row per published release; `sort=imminent|recent`, limit defaults to 50, maximum 100, no cursor |
| GET | `/v1/releases` | Published list; `cursor`, `limit`, `from`, `to`, `format`, `is_limited`; date filters use release date |
| GET | `/v1/releases/{release_id}` | Published detail with purchase `links` and string `artist_name`; no listings or recent_events |
| GET | `/v1/feed.rss` | Latest-event RSS 2.0 |
| GET | `/v1/releases.ics` | 30-minute preorder blocks with alarms 30 minutes before; include_release_dates defaults to true for all-day release events |
| GET | `/v1/push/public-key` | VAPID public key and enabled flag |
| POST | `/v1/push/subscribe` | Anonymous creation/update; capacity also checked on reactivation |
| DELETE | `/v1/push/subscribe` | Deactivate the endpoint subscription and retain history |
| GET | `/healthz` | Checks DB connectivity: 200 on success, 503 on DB failure |

FastAPI also provides `/docs`, `/redoc` and `/openapi.json` on the API port. Search, artist detail,
event streams, source lists, watchlists, accounts, APNs device registration and `/metrics` are **not implemented**.
Funnel does not expose every API path: push is proxied through `/api/push/*`, and RSS/ICS through their fixed `/v1/*` paths.

### 5.2-1 Operator API

| Method | Path | Current behavior |
|---|---|---|
| GET | `/admin` | Login/create/edit UI; content stays hidden until key validation |
| GET | `/admin/releases` | Full list including drafts |
| GET | `/admin/releases/{release_id}` | Detail including drafts, notes and can_delete |
| POST | `/admin/releases` | Create a draft with purchase links |
| PATCH | `/admin/releases/{release_id}` | Update supplied fields; omitted links are preserved, arrays replace the list atomically with the schedule |
| POST | `/admin/releases/{release_id}/publish` | Publish and create the first SCHEDULE_ADDED |
| POST | `/admin/releases/{release_id}/unpublish` | Unpublish while retaining event history |
| DELETE | `/admin/releases/{release_id}` | Delete an unpublished release, even if previously published; linked listings block deletion; events/deliveries are removed |
| POST | `/admin/releases/{release_id}/links` | Add a purchase link |
| DELETE | `/admin/releases/{release_id}/links/{link_id}` | Delete this release's purchase link |

`can_delete` is true for unpublished releases without linked listings; other FK references may still cause a 409.
Public output excludes notes and returns 404 for unpublished details. Inputs reject blank/null titles,
null is_limited, naive timestamps, invalid preorder windows/URLs and invalid won prices.

### 5.2-2 Runtime guarantees (2026-09-10 review)

- Event backfill is limited to seven days; delivery eligibility to 48 hours after the event. Preorder-soon events are generated only within 24 hours before opening.
- Deliveries target active WEB subscriptions, excluding events before subscription creation. Reactivation resets that subscription start time.

- Admin PATCH preserves links when `links` is omitted and replaces the full link list when an array is supplied. Schedule and links share one transaction; commit failures cannot return success.
- Failed pushes receive at most three attempts, with retries eligible one and five minutes after delivery creation. Every attempt rechecks publication, subscription activity, supersession and the 48-hour delivery horizon. A database lock prevents overlapping scheduler processes.
- Editing an unpublished schedule also supersedes events for its previous times, allowing new events after republication.
- Release dates begin at KST midnight. Preorder calendar blocks remain 30 minutes across date boundaries; the web calendar reads all API pages.
- RSS and iCalendar are exposed on the public web domain at `/v1/feed.rss` and `/v1/releases.ics`. Subscription addresses use runtime `PUBLIC_WEB_URL`.
- A process crash between external push acceptance and database commit can still duplicate a transmission. `SENT` means push-service acceptance, not confirmation of device display.

### 5.3 Public Detail Response Example

This illustrates the current `ReleaseOut` shape; it does not refer to a real database row.

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

## 6. Repository Layout

These are the principal existing paths. Braces abbreviate multiple files in the same directory.

```text
AGENTS.md / CLAUDE.md / README.md
compose.yaml / compose.prod.yaml / Makefile / .env.example
.vscode/{settings,extensions}.json
apps/
  api/
    src/vinyl_api/
      main.py / deps.py
      routers/{admin,admin_ui,releases,feed,rss,calendar,push}.py
      schemas/{release,push}.py
      feed_query.py / serializers.py / pagination.py / caching.py
      problems.py / request_limits.py / rate_limit.py / rss.py / icalendar.py
    tests/                         # integration_runtime.py + test_*.py
    pyproject.toml / Dockerfile
  collector/
    src/vinyl_collector/
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
  src/vinyl_core/
    models/{base,artist,release,listing,source,user}.py
    adapters/{base,registry,gimbab,secondtrack,poclanos}.py
    db.py / settings.py / seed.py / enums.py / logging.py / testing.py
    schedule_events.py / notifications.py / alerts.py
  tests/ / pyproject.toml
migrations/versions/ / alembic.ini
infra/{env-backup,env-restore,vinyl-radar-start,vinyl-radar-backup}.sh
docs/{BLUEPRINT.ko,BLUEPRINT.en}.md / docs/{adapters,adr}/
docs/api/openapi.json / docs/{security-review,runtime-review,documentation-review}.md
.github/workflows/ci.yml            # T-012 Python + web verification
backups/                           # ignored runtime artifacts
venv/                              # ignored local Python environment
```

**Reserved future paths:** `apps/ios/`, `apps/api/src/vinyl_api/services/`, collector `pipeline.py`,
core `normalize.py`/`resolver.py`/`events.py`/`aliases.yaml`, web search/artist/watchlist routes,
`infra/nginx/`, `infra/prometheus/`, `infra/deploy.sh` and `.devcontainer/` do not exist.
These are reserved for future tasks; their listing does not authorize creating or activating them.

---

## 7. Web Frontend

### 7.1 Implemented Screens

| Screen | Path | Current content |
|---|---|---|
| Feed | `/` | One row per published release, recent-change/imminent sorting, schedule status/start time and purchase links |
| Calendar | `/calendar?month=YYYY-MM` | Preorder openings and release dates in KST; follows all API pages |
| Detail | `/releases/[id]` | Title, artist, format, preorder window, release date and purchase links |
| Subscribe | `/subscribe` | Web Push toggle and public RSS/ICS addresses |

Search, artist and watchlist screens are absent. The API accepts cover_url, but the current web does not render cover images.

### 7.2 Display and PWA

- Status uses text badges. Layout keeps information density and supports system dark mode.
- Feed, calendar, detail and subscribe pages render dynamically. Feed status is calculated on render; there is no automatic live-refresh timer.
- `manifest.ts`, PWA icons and `sw.js` exist. The worker activates on install and handles push, clicks and subscription replacement; it has no offline content cache.
- The iPhone test flow uses Safari's Add to Home Screen, launches that app and grants permission. Verify actual reception/display on a physical device.

### 7.3 API Client and Environment

`apps/web/lib/api.ts` contains server-side fetch helpers and **handwritten TypeScript types**.
There is no generated client, api-types.ts or openapi-typescript dependency. Generation remains future work;
`make openapi` currently generates only the API contract snapshot.

- `API_BASE_URL` is the web server's internal API address (`http://api:8000` in Compose).
- `PUBLIC_WEB_URL` is the browser-accessible public web address used for links by api, collector and web.
  `/subscribe` reads it at runtime. `PUBLIC_API_URL` is unused.
- Browsers and service workers use same-origin push routes. The API has no CORS middleware.
- API requests have 10-second timeouts and no-store; public RSS and ICS use fixed-path proxies.

---

## 8. Native iOS Application (Planned for M5+)

> This is an unimplemented native-app design. apps/ios, Swift models, APNs, JWT and SwiftData are absent.
> Current iPhone notifications use PWA Web Push; a native app and Apple login are not prerequisites for the current service.
> Platform/review comparisons below are historical planning context and must be checked again before native work starts.

### 8.1 Implementation Approach — Analysis and Recommendation

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| **A. WKWebView wrapper** | 1–2 days of work; 100% web reuse | Real risk of rejection under App Store Review Guideline **4.2 (Minimum Functionality)**. No native push, haptics, or offline cache. Scroll feel immediately reads as "web" | Not recommended |
| **B. Native SwiftUI on the shared REST API** | Genuinely native UX; push, widgets, Live Activities, Spotlight. Client generated from OpenAPI | Screens must be built separately | **Recommended** |
| C. Hybrid (native shell, some screens in web view) | Compromise | Inherits the drawbacks of both stacks; higher maintenance complexity | Conditional |

**Recommendation**: adopt **Option B (native SwiftUI)**, for three reasons.

1. The stated goal is a **"more user-friendly"** iOS app. A web-view wrapper cannot, by definition, be friendlier than the web.
2. The core value of this service is **push notification** the instant a preorder opens. Current delivery uses Web Push; native integration is a future choice for app-specific features.
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

### 9.1 Current Execution

A Docker engine and Compose are required. The macOS test setup uses colima.

```bash
# New environments only; never overwrite an existing .env.
cp -n .env.example .env
# Configure ADMIN_API_KEY; public testing requires a secret of at least 32 characters.
make up          # development web, API, collector and PostgreSQL
make migrate     # initial setup or new migrations
make seed        # sources only; aliases are not implemented
```

`make prod` builds/starts with compose.yaml plus compose.prod.yaml. It is used for public testing
on the Mac mini and is not an EC2 deployment command.

| Component | Development: make up | Public test: make prod |
|---|---|---|
| Web | next dev with source mounts | Built image with next start; web mounts removed |
| API | Source mounts and uvicorn --reload | Same mounts/reload; ENVIRONMENT=production |
| Collector | Source mounts; scheduler; no automatic reload | Same; ENVIRONMENT=production |
| DB/ports | postgres_data volume; loopback 5432/8000/3000 bindings | Same |

API Python edits reload automatically. Collector Python edits require `docker compose restart collector`.
Rebuild production web edits and dependency changes. Environment/Compose changes require container recreation
with `make prod` or `up -d` using the same overlay; restart alone does not update environment variables.

| Variable | Consumer and purpose |
|---|---|
| DATABASE_URL | API/collector database connection |
| ADMIN_API_KEY | API authentication; production settings validation in API and collector |
| API_BASE_URL | Web internal API calls; Compose sets http://api:8000 |
| PUBLIC_WEB_URL | Public links and subscription addresses in API, collector and web |
| VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_SUBJECT | API subscription availability and collector push delivery |
| SLACK_WEBHOOK_URL | Collector operator failure alerts; blank/unset disables them |
| CRAWLER_* | Manual collector configuration; does not enable scheduled harvesting |
| ENV_BACKUP_DIR / ENV_BACKUP_KEEP | Host .env backup scripts |

Local mode accepts the development admin key but rejects empty keys. Staging/production reject the default
or keys shorter than 32 characters. Incomplete VAPID settings produce enabled=false, subscription POST 503,
and FAILED from the sender; this is not recorded as a successful no-op.

### 9.2 Local Tools

.vscode/settings.json selects venv/bin/python and Python test directories. Recommended extensions live in
.vscode/extensions.json. There are no launch.json, tasks.json or devcontainer files. Use `make install` for
Python and `npm ci` in apps/web for web dependencies.

### 9.3 Implemented Verification

```bash
make lint
make test
make openapi
cd apps/web
npm run lint
node --test tests/*.test.mjs
npm run build
```

Default Python tests use fixtures, mocks, TestClient and SQL query checks; no testcontainers setup starts a DB.
apps/api/tests/integration_runtime.py is an **explicitly invoked** PostgreSQL check. It uses a fake sender,
creates an isolated schema and rolls everything back. It is excluded from make test, runs as a separate CI step and sends no real pushes.
`collector test-push` does send real notifications and requires user authorization.

T-012 CI automates local checks and the separate DB check (§9.5). Parser canaries and coverage gates are absent. Test counts in docs/runtime-review.md are dated 2026-09-10
results, not a substitute for a fresh run. Documentation work must not start services or test deletion on existing records.

### 9.3-1 Backup and Restore

- `make backup` pipes pg_dump through gzip into backups/. It detects pipeline failure and removes failed artifacts.
- `make restore FILE=...` prompts first, then applies successfully decompressed SQL with psql in one transaction,
  stopping on SQL errors. It overwrites current data and requires authorization and a prior backup. Test restores in a separate DB.
- `make backup-prune` retains 30 DB backups. infra/vinyl-radar-backup.sh runs backup, prune and .env backup
  when the DB is running; it skips when DB is stopped and logs a warning if .env backup fails.
- infra/env-backup.sh encrypts .env and infra/env-restore.sh restores it. ENV_BACKUP_DIR defaults to
  **local project storage**, backups/env; off-disk storage must be configured separately. Default retention is 10;
  `make backup-env-setup` configures the Keychain password.
- No LaunchAgent plist or registration command is stored in this repository. Verify host registration and timing separately.
- Ordinary down preserves the volume; down -v, volume deletion, SQL deletion and disk failure do not. A volume is not a backup.

### 9.3-2 Funnel Public Testing

```text
Internet → Tailscale Funnel → Mac mini 127.0.0.1:3000
                             → colima/Docker web → api:8000 → postgres:5432
```

The address used in this session is https://jaehyeonui-macmini.tail598a5f.ts.net. Check the actual URL and tunnel
registration with `tailscale funnel status`. Code and DB remain on the Mac mini. Expose only web; API/admin/DB
ports stay on loopback. Do not add an unrestricted API proxy to the web.

After reboot, `colima start` followed by `make prod` starts the stack. infra/vinyl-radar-start.sh also checks
colima, runs Compose up and polls API health, but does not build images. Docker restart policies apply only
while the engine is running; they do not guarantee host login or daemon startup.

### 9.4 Observability and Limits

Current signals are structlog logs, DB-aware /healthz, scheduler.tick, notifications.dispatched and
push.retry_exhausted. Setting `SLACK_WEBHOOK_URL` enables Slack alerts for scheduler tick errors and
retry exhaustion ([ADR-0008](adr/0008-operator-failure-alerts.md)). Exhaustion is reported after the
delivery transaction commits; alert failures do not roll back deliveries. By default, each error key
is successfully sent only once per process, including recurrences after recovery. Restart resets suppression.
There is no durable queue to retain and retry exhaustion alerts after Slack failure.
Host/process outage detection, universal trace_id, Prometheus and Sentry are absent.
Anonymous subscriptions have URL/key validation, body size/time bounds, process-local rate limits, DB capacity
checks and same-origin validation in web ([security review](security-review.md)). API rate limits are not shared across processes.

### 9.5 CI/CD Status

`T-012` in `.github/workflows/ci.yml` runs on all PRs, main pushes and manual dispatch.
The Python 3.12 job runs `make install`, `make lint`, `make test`, applies migrations to disposable
PostgreSQL 16 with `venv/bin/python -m alembic upgrade head`, then executes
`venv/bin/python apps/api/tests/integration_runtime.py` for nine isolated scenarios and schema rollback.
Those scenarios use a separate ORM-created schema, not the migrated schema directly.
The Node 22 job runs `npm ci`, web lint, Node regression tests and a production build.
Each job has a 15-minute timeout; newer runs cancel older runs for the same ref. Repository permissions
are `contents: read`; no production secrets, databases or real notifications are used. Verify GitHub run
results and required-check settings separately in the repository.
GHCR publishing, SSH deploy and automatic rollback remain absent; operational startup uses Compose.

### 9.6 Cost and Operational Scope

The current implementation runs public tests on the owner's Mac mini. Historical EC2/Apple price tables were
neither actual current bills nor verified estimates. Recalculate resources and prices when cloud/native work begins.

---

## 10. Task Backlog

Each task is written to be **independently verifiable**. Agents must cite the task ID while working.

> Status as of 2026-09-11: M1 paths and M2 time events/Web Push are implemented.
> T-116 has retries, 404/410 deactivation and **Slack operator alerts implemented in code**. Live configuration and receipt remain separate operational checks.
> M3+ is planned; acceptance criteria are not completion claims. T-008–T-011 rows preserve the original M0 plan.
> T-008/T-009 are deferred/unimplemented; public API/web responsibilities were delivered as T-105/T-110. The T-012 CI workflow is implemented; GitHub run results must be verified separately.

### M0 — Walking Skeleton (complete)

> The original goal ("one source → DB → API → one screen") was superseded by
> [ADR-0005](adr/0005-manual-curation-first.md). M0 closes with the harvester components built and tested.
> Collection pipeline work moved to M3; public API/web were delivered in M1 for manual schedules.

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
| T-012 | GitHub Actions CI (Python, web, PostgreSQL integration) | PR/main push runs both jobs; lint, test, migration or web build failures fail the corresponding job (§9.5) |
| **M0 closed scope** | Scaffolding, schema and collection components; crawl-to-DB-to-web remains deferred | |

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
| T-113 | Event-generation idempotency | Sequential reruns create no duplicate live event |
| T-114 | **Web Push subscription** (VAPID keys, subscribe/unsubscribe API, schema) — [ADR-0006](adr/0006-web-push-first.md) | Browser subscribes and the row lands in the DB |
| T-115 | Delivery records and deduplication | Committed SENT rows are not reprocessed; see §5.2-2 for the send/commit crash gap |
| T-116 | Retry, expired-subscription cleanup, **Slack operator alerts** | A deliberate failure reaches Slack; 410 deactivates the subscription |
| T-117 | Web subscribe UI (PWA manifest + service worker) — [ADR-0007](adr/0007-same-origin-push-proxy.md) | Notification received on a real device |
| T-118 | Feed collapsing (one event per release) + `SCHEDULE_CHANGED` (§4.5.1, §4.5.3) | One row per album in the feed; editing a schedule notifies |
| T-119 | Supersede and re-fire on schedule change (§4.5.2) | Moving a preorder time re-sends the open alert **at the new time** |
| T-120 | Always-on readiness (port binding, admin key, production build, backup automation) | Two commands restore after reboot; encrypted `.env` backup lives off-disk |
| T-130 | Hardening for public exposure ([`docs/security-review.md`](security-review.md)) | No unauthenticated SSRF, 500, or XSS |
| T-131 | Notification `tag` scoped per event | Distinct alerts no longer erase each other on the device |
| T-132 | Feed `sort=recent` keyed on `updated_at` | Editing a schedule moves it to the top |
| T-133 | Allow deleting drafts (unpublish → delete) | Removable from the UI without SQL; published rows stay protected |
| T-134 | Admin login screen | Body stays closed until the key verifies; no re-entry afterwards |

> **Web Push is the first channel** ([ADR-0006](adr/0006-web-push-first.md)). Email is not built.
> The APNs plan in §8.3 is deferred to iOS app launch, not cancelled.
> T-113 verified event-generation idempotency; T-115 uses delivery records and locks, with no exactly-once guarantee across send/commit failures.

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

### M6 — Native APNs and Push Extensions (Separate from Current Web Push)

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

Distinguish active measures from planned ones: parser canaries, persistent source deactivation, automatic
recovery and crawler-specific external alerts are not running today. Future mitigations below are not completed safeguards.

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Source redesign breaks parsers | High | High | Parser canary (T-126), golden fixture tests, per-source alerting |
| Source operator requests blocking | High | Medium | Advance notice and partnership outreach (§3.4); `sources.is_enabled` allows instant shutoff |
| Bad merges erode trust | Medium | Medium | Precision-first policy, `merge_candidates` hold queue, reversible merges |
| Bot protection (Cloudflare etc.) | Medium | Medium | Re-evaluate the source. **Do not attempt circumvention — drop the source instead** |
| Notification too slow, limited edition missed | High | Medium | Current manual schedules use a 60-second tick and bounded retries; a priority queue remains planned |
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
