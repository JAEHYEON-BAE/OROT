"""Check the HTTP/transaction boundary with no network or database."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from orot_core.models import DeviceToken, ListingEvent, NotificationDelivery, Release
from orot_core.notifications import SendOutcome, SendResult, _send_one


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", [SendOutcome.SENT, SendOutcome.GONE, SendOutcome.FAILED])
async def test_http_runs_after_reads_commit(outcome):
    now = datetime.now(UTC)
    release = Release(id=1, title="test", title_norm="test", is_published=True)
    event = ListingEvent(id=1, release=release, occurred_at=now, event_type="PREORDER_OPEN")
    subscription = DeviceToken(
        id=1,
        platform="WEB",
        token="https://example.invalid/test",
        is_active=True,
        created_at=now - timedelta(hours=1),
        failure_count=0,
    )
    delivery = NotificationDelivery(
        id=1, event_id=1, device_token_id=1, attempts=0, status="PENDING"
    )
    session = AsyncMock(spec=AsyncSession)
    session.get.side_effect = [event, subscription]

    class Sender:
        async def send(self, token, payload):
            session.commit.assert_awaited_once()
            assert delivery.attempts == 0
            return SendResult(outcome)

    result = await _send_one(
        session, Sender(), delivery, base_url="https://example.invalid", moment=now, durable=True
    )
    assert delivery.attempts == 1
    if outcome is SendOutcome.SENT:
        assert result.sent == 1 and delivery.status == "SENT"
    elif outcome is SendOutcome.GONE:
        assert result.deactivated == 1 and not subscription.is_active
    else:
        assert result.failed == 1 and subscription.failure_count == 1


@pytest.mark.asyncio
async def test_unpublished_release_does_not_send():
    now = datetime.now(UTC)
    session = AsyncMock(spec=AsyncSession)
    session.get.side_effect = [
        ListingEvent(release=Release(is_published=False), occurred_at=now),
        DeviceToken(is_active=True, created_at=now - timedelta(hours=1)),
    ]
    sender = AsyncMock()
    delivery = NotificationDelivery(event_id=1, device_token_id=1, attempts=0)
    result = await _send_one(
        session, sender, delivery, base_url="https://example.invalid", moment=now, durable=True
    )
    assert result.expired == 1
    sender.send.assert_not_awaited()
    assert delivery.attempts == 0
