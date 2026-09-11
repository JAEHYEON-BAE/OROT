import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from starlette.requests import Request
from vinyl_core.models import Release

from vinyl_api.routers.feed import get_feed, release_feed_query


@pytest.mark.asyncio
async def test_upcoming_release_with_event_appears_only_once():
    now = datetime.now(UTC)
    release = Release(
        id=33,
        title="demo",
        title_norm="demo",
        curation="MANUAL",
        is_published=True,
        is_limited=False,
        created_at=now,
        preorder_opens_at=now + timedelta(days=1),
        links=[],
    )
    event = SimpleNamespace(occurred_at=now, event_type="SCHEDULE_ADDED")
    session = SimpleNamespace(
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [release])),
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(event, release)])),
    )
    response = await get_feed(
        session, Request({"type": "http", "headers": []}), Response(), limit=50, sort="recent"
    )
    items = json.loads(response.body)["items"]
    assert len(items) == 1
    assert items[0]["release"]["id"] == 33
    assert items[0]["kind"] == "UPCOMING"


def test_recent_sort_uses_last_edit_not_registration():
    """일정을 고치면 위로 올라와야 한다.

    등록 시각으로 줄세우면 **방금 바꾼 일정이 아래에 묻힌다.** 운영자가 시각을
    수정하는 것은 그 자체로 소식이고(`SCHEDULE_CHANGED`), 화면에서도 그렇게 보여야 한다.
    """
    query = str(release_feed_query("recent", datetime.now(UTC), 2))
    order_by = query[query.index("ORDER BY") :]
    assert "ORDER BY releases.updated_at DESC, releases.id DESC" in order_by
    # `created_at` 은 SELECT 컬럼 목록에도 나오므로 **정렬 절만** 본다.
    assert "created_at" not in order_by
    # 알림 시각으로 정렬하지 않는다 — 이벤트가 없는 일정이 영영 아래에 남는다.
    assert "listing_events" not in query
    assert "releases.is_published IS true" in query
