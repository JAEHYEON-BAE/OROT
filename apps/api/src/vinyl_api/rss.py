"""RSS 2.0 생성.

iCalendar 와 같은 방침으로 의존성 없이 직접 만든다. 대신 규격에서 틀리기 쉬운 것을 지킨다.

1. **`pubDate` 는 RFC 822 형식** — `Wed, 27 Aug 2026 07:23:27 +0000`.
   ISO-8601 을 넣으면 리더가 날짜를 못 읽고 정렬이 무너진다
2. **XML 이스케이프** — `&` 를 먼저 바꾸지 않으면 이중 이스케이프가 된다
3. **`guid` 는 항목마다 고정** — 바뀌면 리더가 읽은 글을 새 글로 다시 띄운다
"""

from datetime import datetime
from email.utils import format_datetime
from typing import Final
from xml.sax.saxutils import escape as xml_escape

RSS_VERSION: Final = "2.0"
ATOM_NS: Final = "http://www.w3.org/2005/Atom"


def escape(value: str) -> str:
    """XML 텍스트 이스케이프. `<` `>` `&` 와 따옴표까지."""
    return xml_escape(value, {'"': "&quot;", "'": "&apos;"})


def rfc822(moment: datetime) -> str:
    """RSS `pubDate` 형식 (RFC 822)."""
    return format_datetime(moment)


class RssBuilder:
    """RSS 2.0 채널을 만든다."""

    def __init__(
        self,
        *,
        title: str,
        link: str,
        description: str,
        self_url: str,
        language: str = "ko",
        build_time: datetime | None = None,
    ) -> None:
        self._items: list[str] = []
        self._header = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<rss version="{RSS_VERSION}" xmlns:atom="{ATOM_NS}">',
            "  <channel>",
            f"    <title>{escape(title)}</title>",
            f"    <link>{escape(link)}</link>",
            f"    <description>{escape(description)}</description>",
            f"    <language>{escape(language)}</language>",
            # rel="self" 는 피드 자신의 주소를 알려 준다. 리더가 이동을 추적할 때 쓴다.
            f'    <atom:link href="{escape(self_url)}" rel="self" type="application/rss+xml"/>',
        ]
        if build_time is not None:
            self._header.append(f"    <lastBuildDate>{rfc822(build_time)}</lastBuildDate>")

    def add_item(
        self,
        *,
        title: str,
        link: str,
        guid: str,
        published_at: datetime,
        description: str = "",
        categories: list[str] | None = None,
    ) -> None:
        """항목 하나. `guid` 는 같은 글이면 항상 같아야 한다."""
        lines = [
            "    <item>",
            f"      <title>{escape(title)}</title>",
            f"      <link>{escape(link)}</link>",
            # isPermaLink="false" — guid 가 URL 이 아니라 우리 식별자임을 밝힌다.
            f'      <guid isPermaLink="false">{escape(guid)}</guid>',
            f"      <pubDate>{rfc822(published_at)}</pubDate>",
        ]
        if description:
            lines.append(f"      <description>{escape(description)}</description>")
        lines += [f"      <category>{escape(c)}</category>" for c in categories or []]
        lines.append("    </item>")
        self._items.extend(lines)

    def render(self) -> str:
        return "\n".join([*self._header, *self._items, "  </channel>", "</rss>", ""])
