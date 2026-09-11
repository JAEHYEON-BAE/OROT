# Repository Guidelines

## Product and source of truth

Vinyl Radar is a Korean vinyl release-schedule notification service. The current
product uses operator-entered schedules, a public feed/calendar, RSS/iCalendar,
and Web Push. Automated collection remains deliberately unwired until M3; do not
enable it as incidental cleanup or expand the product into a sales catalog.

Read `CLAUDE.md` for project rules and implementation pitfalls, and consult
`docs/BLUEPRINT.ko.md` (authoritative specification), its English mirror, and
relevant `docs/adr/` decisions before implementation. Current source, migrations
and runtime configuration take precedence over stale descriptions; update the
documents when they disagree. The blueprints distinguish implemented behavior
from planned features. Keep both editions synchronized when changing the spec.
For backlog work, announce the applicable `T-XXX` ID and complete one task's
acceptance criteria at a time. Document unresolved architectural decisions in a
draft ADR before requesting a decision; do not invent a task ID for maintenance.

## Repository map

- `packages/core/src/vinyl_core/`: shared settings, async database access,
  SQLAlchemy models, adapters, schedule events, and notification selection.
- `apps/api/src/vinyl_api/`: FastAPI routers, admin UI, schemas, feed queries,
  RSS, iCalendar, and push subscription endpoints.
- `apps/collector/src/vinyl_collector/`: CLI, fetcher, scheduler, and push sender.
- `apps/web/`: Next.js App Router, React, TypeScript, Tailwind CSS, and service
  worker. Follow its nested `AGENTS.md`; read the relevant installed Next.js
  guide under `apps/web/node_modules/next/dist/docs/` before writing web code.
- Each Python package has a `tests/` directory. Saved source HTML belongs in
  `apps/collector/tests/fixtures/<source_id>/`.
- `migrations/`: Alembic revisions; `docs/api/openapi.json`: API schema snapshot;
  `infra/` and Compose files: runtime and backup operations.

Do not introduce top-level directories outside blueprint §6. Inspect git status
before editing and preserve unrelated working changes.

## Development and verification

Run Python through the existing `venv/bin/python` or Make targets, never the
system interpreter. The Makefile uses `venv/`, despite older blueprint references
to `.venv/`. Python requires 3.12 or later.

```sh
make install       # Create venv and install all three Python packages editable
make lint          # Ruff check, format check, and mypy on core
make test          # Pytest across core, API, and collector
make format        # Mutating Ruff format and fixes; inspect resulting scope
make openapi       # Regenerate docs/api/openapi.json after API contract changes
make help          # Full command list
```

Run `make lint` and `make test` for implementation work; report failures and
environment limits without claiming success. Targeted tests can use
`venv/bin/python -m pytest <test-path> -q`. Tests must not call live external
services. Use saved fixtures and mocks; if a required source fixture is missing,
ask for it rather than silently scraping a replacement.

For web changes, run `npm run lint` and `npm run build` from `apps/web/`.
Run `node --test tests/*.test.mjs` there for web regressions; no npm test script exists. `make up` builds and starts the local
stack; `make down` preserves DB volumes. Database operations such as
`make migrate`, `make revision m="description"`, and `make seed` use running
containers. For documentation-only work, verify paths, commands and contracts without starting
or rebuilding services. Python/web test suites are required for implementation changes.

## Implementation conventions and invariants

- Python: typed public functions, Pydantic v2 boundaries, SQLAlchemy 2 typed
  `Mapped` models, async I/O, Ruff with 100-character lines. Core is intended to
  remain mypy-strict; check its `pyproject.toml` when invoking mypy directly.
- Keep database/JSON names `snake_case`, source IDs lowercase ASCII slugs,
  source text in `_raw`, and normalized values separately in `_norm`.
- Store timestamps in UTC with timezone-aware columns; convert KST inputs at
  the boundary. Keep won prices integral (`NUMERIC(12,0)`), never floats.
- Public queries must exclude unpublished releases and private notes. Flush writes
  early and keep the function-scoped session dependency: commit precedes response.
- Schedule changes supersede affected events and preserve delivery history, even
  when editing an unpublished release. An authorized deletion of an unpublished
  release removes its events and cascades to deliveries; linked listings block it.
  Unique delivery rows and scheduler locks prevent normal duplicate processing,
  but external push and DB commit are not atomic across crashes.
- Variants are distinct releases. Entity resolution must be reversible through
  `listings.release_id`; never delete listing rows as part of a merge.
- Browser push requests use same-origin `app/api/push/*` handlers and `lib/proxy.ts`;
  RSS/ICS use fixed `app/v1/*` proxies. Server API access uses `API_BASE_URL`;
  public links use `PUBLIC_WEB_URL` in api, collector and web (ADR-0007).
- Web API types in `apps/web/lib/api.ts` are handwritten today. OpenAPI is a
  generated snapshot, not an installed TypeScript/Swift client generation pipeline.
- `make prod` builds the web without source mounts. API still reloads mounted
  Python source; collector requires restart after source edits. Environment
  changes require container recreation, not only restart.
- Keep blocking `pywebpush` calls off the async event loop. Never send real test
  notifications without the user's authorization.
- Crawlers must honor robots.txt, stay at or below 0.5 requests/second per source
  and two concurrent connections, identify themselves with a contact-bearing
  User-Agent, and retain only metadata. Preserve source links; do not rehost
  images or bypass bot protection. Parse failures must be observable.

## Data and change hygiene

Never commit `.env`, credentials, VAPID private keys, or backup contents. Use
`.env.example` for documented configuration. Do not overwrite an existing `.env`
when setting up the project.

Destructive database or infrastructure operations require explicit authorization:
volume deletion, `docker compose down -v`, `colima delete`, pruning, unrestricted
SQL deletes, and restores that overwrite existing data. Back up before authorized
destructive work. Test cleanup must target only records created by that test;
do not assume a shared database is disposable. Prefer the isolated-schema check
in `apps/api/tests/integration_runtime.py` with its fake sender and outer rollback.
Use exact IDs from the test run for any shared-DB cleanup, never title patterns.

Use existing commit conventions when a commit is requested:
`<type>(<scope>): <T-ID> <summary>` for backlog tasks. Keep changes scoped, update
relevant docs, and report what changed, how it was verified, and any blockers.
