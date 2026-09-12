"""RSS 2.0 생성 규칙 (T-108).

리더는 `pubDate` 로 정렬하고 `guid` 로 읽음 표시를 한다. 둘 중 하나만 틀려도
읽은 글이 다시 뜨거나 순서가 뒤집힌다.
"""

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from unittest.mock import AsyncMock, Mock

import pytest
from orot_core.models import ListingEvent, Release
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from orot_api.routers.rss import feed_rss
from orot_api.rss import RssBuilder, escape, rfc822

WHEN = datetime(2026, 8, 27, 7, 33, 2, tzinfo=UTC)


def _build() -> str:
    feed = RssBuilder(
        title="OROT",
        link="https://example.com",
        description="설명 & 특수문자",
        self_url="https://example.com/v1/feed.rss",
        build_time=WHEN,
    )
    feed.add_item(
        title='새소년 — 난춘 <7">',
        link="https://example.com/p?a=1&b=2",
        guid="event-10@OROT",
        published_at=WHEN,
        description="포맷: 7INCH · 한정반",
        categories=["일정 등록", "한정반"],
    )
    return feed.render()


def test_output_is_well_formed_xml() -> None:
    root = ET.fromstring(_build())
    assert root.tag == "rss"
    assert root.get("version") == "2.0"


@pytest.mark.parametrize("tag", ["title", "link", "description", "language", "lastBuildDate"])
def test_channel_has_required_elements(tag: str) -> None:
    channel = ET.fromstring(_build()).find("channel")
    assert channel is not None
    assert channel.find(tag) is not None


def test_special_characters_round_trip() -> None:
    """이스케이프한 값이 파싱하면 원본으로 돌아와야 한다.

    `&` 를 먼저 처리하지 않으면 이중 이스케이프되어 `&amp;amp;` 가 된다.
    """
    item = ET.fromstring(_build()).find("channel/item")
    assert item is not None
    assert item.findtext("title") == '새소년 — 난춘 <7">'
    assert item.findtext("link") == "https://example.com/p?a=1&b=2"


def test_pubdate_is_rfc822() -> None:
    """ISO-8601 을 넣으면 리더가 날짜를 못 읽고 정렬이 무너진다."""
    item = ET.fromstring(_build()).find("channel/item")
    assert item is not None
    assert parsedate_to_datetime(item.findtext("pubDate") or "") == WHEN


def test_guid_is_not_a_permalink() -> None:
    """URL 이 아니라 우리 식별자임을 밝혀야 리더가 링크로 착각하지 않는다."""
    guid = ET.fromstring(_build()).find("channel/item/guid")
    assert guid is not None
    assert guid.get("isPermaLink") == "false"


def test_categories_are_emitted() -> None:
    item = ET.fromstring(_build()).find("channel/item")
    assert item is not None
    assert [c.text for c in item.findall("category")] == ["일정 등록", "한정반"]


def test_atom_self_link_present() -> None:
    """리더가 피드 주소 이동을 추적할 때 쓴다."""
    assert 'rel="self"' in _build()


def test_escape_handles_ampersand_first() -> None:
    assert escape("a & b < c") == "a &amp; b &lt; c"


def test_rfc822_format() -> None:
    assert rfc822(WHEN) == "Thu, 27 Aug 2026 07:33:02 +0000"


def test_empty_feed_is_still_valid() -> None:
    """항목이 없어도 리더가 읽을 수 있어야 한다."""
    feed = RssBuilder(
        title="t", link="https://e.com", description="d", self_url="https://e.com/f.rss"
    )
    root = ET.fromstring(feed.render())
    assert root.find("channel") is not None


async def test_endpoint_uses_orot_guid() -> None:
    release = Release(id=1, title="테스트", links=[])
    event = ListingEvent(id=10, event_type="SCHEDULE_ADDED", occurred_at=WHEN)
    session = AsyncMock(spec=AsyncSession)
    rows = Mock()
    rows.all.return_value = [(event, release)]
    session.execute.return_value = rows
    response = await feed_rss(session, Request({"type": "http"}))
    guid = ET.fromstring(bytes(response.body)).find("channel/item/guid")
    assert guid is not None
    assert guid.text == "event-10@OROT"
    assert guid.get("isPermaLink") == "false"
