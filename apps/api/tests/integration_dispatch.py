"""Real commit/concurrency checks in an owned, migration-created disposable schema.

No real push endpoints; only FakeSender is used. Unlike integration_runtime, this
check commits intentionally, and removes only its UUID schema in finally.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
from orot_core import notifications
from orot_core.db import get_engine
from orot_core.models import DeviceToken, ListingEvent, NotificationDelivery, Release
from orot_core.notifications import SendOutcome, SendResult, dispatch_committed
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import object_session


async def main():
    admin_engine = get_engine()
    schema = "dispatch_audit_" + uuid4().hex
    async with admin_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        admin_engine.url,
        connect_args={"server_settings": {"search_path": f'"{schema}", public'}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("CREATE TABLE alembic_version (version_num varchar(32) NOT NULL PRIMARY KEY)")
            )

            def migrate(connection):
                config = Config("alembic.ini")
                config.attributes["connection"] = connection
                command.upgrade(config, "head")

            await conn.run_sync(migrate)
        now = datetime.now(UTC)
        async with factory.begin() as session:
            release = Release(title="durable check", title_norm="durable check", is_published=True)
            session.add(release)
            await session.flush()
            session.add(
                ListingEvent(release_id=release.id, event_type="PREORDER_OPEN", occurred_at=now)
            )
            for i in range(7):
                session.add(
                    DeviceToken(
                        platform="WEB",
                        token=f"https://example.invalid/{i}",
                        created_at=now - timedelta(hours=1),
                    )
                )

        class Sender:
            calls = 0
            active = 0
            maximum = 0
            cancel_at = 2

            async def send(self, subscription, payload):
                # The actual SQLAlchemy session must have ended its read transaction.
                assert not object_session(subscription).in_transaction()
                self.calls += 1
                if self.cancel_at and self.calls == self.cancel_at:
                    raise RuntimeError("synthetic sender error")
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                await asyncio.sleep(0.01)
                self.active -= 1
                return SendResult(SendOutcome.SENT)

        sender = Sender()
        result = await dispatch_committed(factory, sender, base_url="https://example.invalid")
        assert result.sent == 6 and result.failed == 1
        assert 1 < sender.maximum <= notifications.SEND_CONCURRENCY
        async with factory() as session:
            rows = list(await session.scalars(select(NotificationDelivery)))
            assert sum(row.status == "SENT" for row in rows) == 6
        again = await dispatch_committed(factory, sender, base_url="https://example.invalid")
        assert again.sent == 0 and sender.calls == 7
        # Retry only the failed delivery after its retry window; persisted SENT stays untouched.
        async with factory.begin() as session:
            failed = await session.scalar(
                select(NotificationDelivery).where(NotificationDelivery.status == "FAILED")
            )
            failed.created_at = now - timedelta(minutes=2)
        sender.cancel_at = 0
        retried = await dispatch_committed(factory, sender, base_url="https://example.invalid")
        assert retried.sent == 1 and sender.calls == 8
        print("PASS no transaction during HTTP, bounded parallelism, committed results and retry")

        # Stop after one committed send; later deliveries must remain pending for restart.
        async with factory.begin() as session:
            session.add(
                ListingEvent(
                    release_id=release.id, event_type="RELEASED", occurred_at=datetime.now(UTC)
                )
            )
        concurrency_patch = patch.object(notifications, "SEND_CONCURRENCY", 1)
        concurrency_patch.start()

        class Interrupted(Sender):
            calls = 0

            async def send(self, subscription, payload):
                self.calls += 1
                if self.calls == 2:
                    raise KeyboardInterruptForTest()
                assert not object_session(subscription).in_transaction()
                return SendResult(SendOutcome.SENT)

        try:
            await dispatch_committed(factory, Interrupted(), base_url="https://example.invalid")
        except BaseExceptionGroup:
            pass
        finally:
            concurrency_patch.stop()
        async with factory() as session:
            rows = list(
                await session.scalars(
                    select(NotificationDelivery)
                    .join(ListingEvent)
                    .where(ListingEvent.event_type == "RELEASED")
                )
            )
            assert sum(row.status == "SENT" for row in rows) == 1
            assert sum(row.status == "PENDING" for row in rows) == 6
        print("PASS interrupted dispatch preserves prior committed sends")
    finally:
        await engine.dispose()
        async with admin_engine.begin() as conn:
            # Only the randomly named schema created by this invocation is removed.
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()


class KeyboardInterruptForTest(BaseException):
    pass


if __name__ == "__main__":
    asyncio.run(main())
