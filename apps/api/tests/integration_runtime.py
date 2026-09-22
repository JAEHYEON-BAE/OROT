"""Explicit PostgreSQL check: isolated schema, outer rollback, fake push only.

Run with venv/bin/python apps/api/tests/integration_runtime.py and DATABASE_URL set.
CI runs this after migrations on disposable PostgreSQL; the default test suite excludes it.
The checks apply the actual migration chain in their own schema and roll it back.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from alembic import command
from alembic.config import Config
from orot_core.db import get_engine
from orot_core.enums import DeliveryStatus, EventType
from orot_core.models import Artist, DeviceToken, ListingEvent, NotificationDelivery, Release
from orot_core.notifications import SendOutcome, SendResult, dispatch_pending, plan_deliveries
from orot_core.schedule_events import generate_due_events
from sqlalchemy import event as sa_event
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from orot_api.routers.admin import (
    create_release,
    delete_release,
    publish_release,
    unpublish_release,
    update_release,
)
from orot_api.routers.calendar import releases_ics
from orot_api.schemas.release import ReleaseIn, ReleaseLinkIn, ReleaseUpdate


class FakeSender:
    def __init__(self, outcome=SendOutcome.SENT):
        self.calls = 0
        self.outcome = outcome

    async def send(self, subscription, payload):
        self.calls += 1
        return SendResult(self.outcome)


async def seed(session, now):
    release = Release(title="isolated audit", title_norm="isolated audit", is_published=True)
    token = DeviceToken(
        platform="WEB", token="https://example.invalid/audit", created_at=now - timedelta(hours=1)
    )
    session.add_all([release, token])
    await session.flush()
    event = ListingEvent(
        release_id=release.id,
        event_type=EventType.SCHEDULE_ADDED,
        occurred_at=now - timedelta(seconds=1),
    )
    session.add(event)
    await session.flush()
    return release, token, event


async def retry(session):
    now = datetime.now(UTC)
    await seed(session, now)
    sender = FakeSender(SendOutcome.FAILED)
    assert (
        await dispatch_pending(session, sender, base_url="https://example.invalid", now=now)
    ).failed == 1
    delivery = await session.scalar(select(NotificationDelivery))
    delivery.created_at = now
    await session.flush()
    await dispatch_pending(
        session, sender, base_url="https://example.invalid", now=now + timedelta(seconds=30)
    )
    assert sender.calls == 1
    await dispatch_pending(
        session, sender, base_url="https://example.invalid", now=now + timedelta(minutes=2)
    )
    assert sender.calls == 2
    sender.outcome = SendOutcome.SENT
    await dispatch_pending(
        session, sender, base_url="https://example.invalid", now=now + timedelta(minutes=6)
    )
    await dispatch_pending(
        session, sender, base_url="https://example.invalid", now=now + timedelta(minutes=7)
    )
    assert sender.calls == 3 and delivery.status == DeliveryStatus.SENT


async def cancellation(session, reason):
    now = datetime.now(UTC)
    release, token, event = await seed(session, now)
    assert len(await plan_deliveries(session, now=now)) == 1
    if reason == "unpublish":
        release.is_published = False
    elif reason == "unsubscribe":
        token.is_active = False
    else:
        event.superseded_at = now
    await session.flush()
    sender = FakeSender()
    result = await dispatch_pending(session, sender, base_url="https://example.invalid", now=now)
    assert result.expired == 1 and sender.calls == 0


async def exhausted_retries(session):
    now = datetime.now(UTC)
    await seed(session, now)
    sender = FakeSender(SendOutcome.FAILED)
    for minutes in (0, 2, 6, 10, 60):
        await dispatch_pending(
            session,
            sender,
            base_url="https://example.invalid",
            now=now + timedelta(minutes=minutes),
        )
    delivery = await session.scalar(select(NotificationDelivery))
    assert sender.calls == 3
    assert delivery.attempts == 3 and delivery.status == DeliveryStatus.FAILED

    # 소진은 **정확히 한 번만** 보고되어야 한다 (T-116). 매 주기 다시 세면
    # 운영자 알림이 끝없이 나가고, 그러면 사람이 알림을 꺼 버린다.
    counted = 0
    for minutes in (0, 2, 6, 10, 60, 120):
        result = await dispatch_pending(
            session,
            FakeSender(SendOutcome.FAILED),
            base_url="https://example.invalid",
            now=now + timedelta(minutes=minutes),
        )
        counted += result.exhausted
    assert counted == 0, "이미 소진된 배송을 다시 세면 안 된다"


async def sender_exception(session):
    now = datetime.now(UTC)
    release, _, _ = await seed(session, now)
    session.add(
        ListingEvent(
            release_id=release.id,
            event_type=EventType.PREORDER_OPEN,
            occurred_at=now - timedelta(seconds=1),
        )
    )
    await session.flush()

    class BrokenOnce(FakeSender):
        async def send(self, subscription, payload):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("synthetic transport error")
            return SendResult(SendOutcome.SENT)

    sender = BrokenOnce()
    result = await dispatch_pending(session, sender, base_url="https://example.invalid", now=now)
    assert result.failed == 1 and result.sent == 1 and sender.calls == 2


async def gone(session):
    now = datetime.now(UTC)
    release, _, _ = await seed(session, now)
    session.add(
        ListingEvent(
            release_id=release.id,
            event_type=EventType.PREORDER_OPEN,
            occurred_at=now - timedelta(seconds=1),
        )
    )
    await session.flush()
    sender = FakeSender(SendOutcome.GONE)
    result = await dispatch_pending(session, sender, base_url="https://example.invalid", now=now)
    assert result.expired == 2 and sender.calls == 1
    # 구독 하나가 꺼졌다. 배송 2건이 만료됐지만 **해제는 한 번**이어야 한다 (T-116) —
    # 구독 수로 세지 않고 배송 수로 세면 운영자에게 부풀려진 숫자가 간다.
    assert result.deactivated == 1


async def admin_flow(session):
    first = await create_release(
        ReleaseIn(title="audit first", artist_name="audit artist"), session, None
    )
    second = await create_release(
        ReleaseIn(title="audit second", artist_name="audit artist"), session, None
    )
    await publish_release(first.id, session, None)
    await publish_release(first.id, session, None)
    assert await session.scalar(select(func.count()).select_from(ListingEvent)) == 1
    session.add(ListingEvent(release_id=first.id, event_type=EventType.PREORDER_OPEN))
    await session.flush()
    await unpublish_release(first.id, session, None)
    await update_release(
        first.id, ReleaseUpdate(preorder_opens_at=datetime(2026, 10, 1, tzinfo=UTC)), session, None
    )
    old = await session.scalar(
        select(ListingEvent).where(ListingEvent.event_type == EventType.PREORDER_OPEN)
    )
    assert old.superseded_at is not None
    await delete_release(first.id, session, None)
    assert await session.get(Release, second.id) is not None
    assert await session.scalar(select(func.count()).select_from(ListingEvent)) == 0
    await update_release(
        second.id,
        ReleaseUpdate(
            links=[ReleaseLinkIn(shop_name="audit", url="https://example.invalid/original")]
        ),
        session,
        None,
    )
    try:
        async with session.begin_nested():
            await update_release(
                second.id,
                ReleaseUpdate(
                    title="must roll back",
                    links=[
                        ReleaseLinkIn(
                            shop_name="audit",
                            url="https://example.invalid/new",
                            source_id="does-not-exist",
                        )
                    ],
                ),
                session,
                None,
            )
    except IntegrityError:
        pass
    else:
        raise AssertionError("invalid source should fail")
    preserved = await session.get(Release, second.id, populate_existing=True)
    assert preserved.title == "audit second"
    assert [link.url for link in preserved.links] == ["https://example.invalid/original"]


async def calendar(session):
    session.add(
        DeviceToken(
            platform="WEB",
            token="https://example.invalid/calendar",
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )
    )
    release = Release(
        title="audit midnight",
        title_norm="audit midnight",
        is_published=True,
        release_date=date(2026, 9, 11),
        preorder_opens_at=datetime(2026, 9, 10, 23, 45, tzinfo=UTC),
    )
    session.add(release)
    await session.flush()
    result = await generate_due_events(session, now=datetime(2026, 9, 10, 15, tzinfo=UTC))
    assert result.released == 1
    assert len(await plan_deliveries(session, now=datetime(2026, 9, 10, 15, tzinfo=UTC))) == 2
    assert (
        await generate_due_events(session, now=datetime(2026, 9, 10, 15, tzinfo=UTC))
    ).total == 0
    response = await releases_ics(session, Request({"type": "http"}))
    body = response.body.decode()
    assert "DTSTART:20260910T234500Z" in body
    assert "DTEND:20260911T001500Z" in body


async def schedule_modes(session):
    now = datetime.now(UTC)
    release = await create_release(
        ReleaseIn(
            title="isolated modes",
            preorder_opens_at=now + timedelta(days=1),
            preorder_closes_at=now + timedelta(days=2),
            release_date=now.date(),
        ),
        session,
        None,
    )
    await publish_release(release.id, session, None)
    await generate_due_events(session, now=now)
    changed = await update_release(release.id, ReleaseUpdate(schedule_status="TBA"), session, None)
    assert changed.schedule_status == "TBA"
    assert changed.preorder_opens_at is None and changed.preorder_closes_at is None
    assert changed.release_date is None
    assert (await generate_due_events(session, now=now)).total == 0
    stale = await session.scalar(
        select(func.count())
        .select_from(ListingEvent)
        .where(ListingEvent.release_id == release.id, ListingEvent.superseded_at.is_not(None))
    )
    assert stale >= 1
    changed = await update_release(
        release.id,
        ReleaseUpdate(schedule_status="ON_SALE", preorder_closes_at=now + timedelta(days=2)),
        session,
        None,
    )
    assert changed.schedule_status == "ON_SALE" and changed.preorder_closes_at is not None
    changed = await update_release(release.id, ReleaseUpdate(until_sold_out=True), session, None)
    assert changed.until_sold_out and changed.preorder_closes_at is None
    changed = await update_release(release.id, ReleaseUpdate(title="renamed"), session, None)
    assert changed.schedule_status == "ON_SALE" and changed.until_sold_out
    changed = await update_release(
        release.id,
        ReleaseUpdate(
            schedule_status="SCHEDULED",
            until_sold_out=False,
            preorder_opens_at=now + timedelta(days=3),
            preorder_closes_at=now + timedelta(days=4),
        ),
        session,
        None,
    )
    assert changed.preorder_opens_at is not None and changed.preorder_closes_at is not None
    await session.refresh(await session.get(Release, release.id))
    # Public serialization must carry the explicit status, without operator notes.
    from orot_api.serializers import release_to_out

    public = await release_to_out(session, await session.get(Release, release.id))
    assert public.schedule_status == "SCHEDULED"
    assert "notes" not in public.model_dump()


async def sql_behavior(session):
    # CHECK behavior cannot be inferred from a successful alembic check.
    try:
        async with session.begin_nested():
            session.add(
                Release(
                    title="invalid TBA",
                    title_norm="invalid TBA",
                    schedule_status="TBA",
                    release_date=date.today(),
                )
            )
            await session.flush()
    except IntegrityError:
        pass
    else:
        raise AssertionError("migrated TBA CHECK must reject dates")

    now = datetime.now(UTC)
    for i in range(30):
        session.add(
            Release(
                title=f"artist audit {i}",
                title_norm=f"artist audit {i}",
                is_published=True,
                primary_artist=Artist(name_display=f"artist {i}", name_norm=f"artist {i}"),
            )
        )
    await session.flush()
    session.expunge_all()
    statements = []
    bind = session.get_bind()

    def count(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    sa_event.listen(bind, "before_cursor_execute", count)
    try:
        releases = list(await session.scalars(select(Release)))
        from orot_api.serializers import release_to_out

        output = [await release_to_out(session, release) for release in releases]
        assert len(output) == 30 and all(row.artist_name for row in output)
        assert len(statements) <= 3, f"artist N+1: {len(statements)} queries"
    finally:
        sa_event.remove(bind, "before_cursor_execute", count)

    release = releases[0]
    earlier = ListingEvent(release_id=release.id, event_type="SCHEDULE_ADDED", occurred_at=now)
    latest = ListingEvent(release_id=release.id, event_type="PREORDER_OPEN", occurred_at=now)
    session.add_all([earlier, latest])
    await session.flush()
    from orot_api.feed_query import latest_event_per_release

    rows = (await session.execute(latest_event_per_release(50))).all()
    assert len(rows) == 1 and rows[0][0].id == latest.id
    latest.superseded_at = now
    await session.flush()
    rows = (await session.execute(latest_event_per_release(50))).all()
    assert rows[0][0].id == earlier.id
    token = DeviceToken(platform="WEB", token="https://example.invalid/cascade")
    session.add(token)
    await session.flush()
    delivery = NotificationDelivery(event_id=earlier.id, device_token_id=token.id)
    session.add(delivery)
    await session.flush()
    delivery_id = delivery.id
    await session.delete(earlier)
    await session.flush()
    assert (
        await session.scalar(
            select(NotificationDelivery.id).where(NotificationDelivery.id == delivery_id)
        )
        is None
    )


async def main():
    engine = get_engine()
    schema = "audit_" + uuid4().hex
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            # Exclude public here: otherwise Alembic can read the host version table
            # and skip migrations, or tests can accidentally touch host tables.
            await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))

            def migrate(connection):
                config = Config("alembic.ini")
                config.attributes["connection"] = connection
                command.upgrade(config, "head")

            # pg_trgm operators installed in public must remain resolvable. A local
            # version table shadows public's version table before adding public.
            await conn.execute(
                text("CREATE TABLE alembic_version (version_num varchar(32) NOT NULL PRIMARY KEY)")
            )
            await conn.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            await conn.run_sync(migrate)
            assert await conn.scalar(text("SELECT current_schema()")) == schema
            cases = [
                ("migration CHECK, eager artists, DISTINCT ON and CASCADE", sql_behavior),
                ("retry/idempotency", retry),
                ("retry exhaustion", exhausted_retries),
                ("sender exception isolation", sender_exception),
                ("gone", gone),
                ("admin CRUD/draft schedule", admin_flow),
                ("KST/ICS", calendar),
                ("schedule modes/partial edits/stale events", schedule_modes),
            ]
            for reason in ("unpublish", "unsubscribe", "supersede"):

                async def run(session, reason=reason):
                    await cancellation(session, reason)

                cases.append((reason, run))
            for name, check in cases:
                async with AsyncSession(
                    bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
                ) as session:
                    await check(session)
                    await session.rollback()
                print("PASS", name)
        finally:
            await transaction.rollback()
        assert (
            await conn.scalar(
                text("SELECT count(*) FROM pg_namespace WHERE nspname=:name"), {"name": schema}
            )
            == 0
        )
    await engine.dispose()
    print("PASS isolated schema rolled back; no real pushes")


if __name__ == "__main__":
    asyncio.run(main())
