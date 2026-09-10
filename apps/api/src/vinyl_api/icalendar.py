"""iCalendar (RFC 5545) 생성.

의존성을 늘리지 않고 직접 만든다. 대신 **틀리기 쉬운 세 가지**를 규칙대로 지킨다.

1. **줄 끝은 CRLF** (§3.1). LF 만 쓰면 일부 캘린더 앱이 조용히 거부한다
2. **75옥텟에서 줄 접기** (§3.1) — 다음 줄은 공백 하나로 시작한다.
   한글은 UTF-8 로 3바이트이므로 **글자 수가 아니라 바이트 수**로 세야 한다
3. **텍스트 이스케이프** (§3.3.11) — `\\` `;` `,` 는 역슬래시로, 줄바꿈은 `\\n` 으로
"""

from datetime import UTC, date, datetime
from typing import Final

CRLF: Final = "\r\n"
MAX_OCTETS: Final = 75
PRODID: Final = "-//Vinyl Radar//발매 일정//KO"


def escape_text(value: str) -> str:
    """RFC 5545 §3.3.11 TEXT 이스케이프. 순서가 중요하다 — 역슬래시가 먼저다."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def fold(line: str) -> str:
    """75옥텟을 넘는 줄을 접는다 (§3.1).

    UTF-8 문자를 중간에서 자르면 안 되므로 문자 단위로 붙이며 바이트를 센다.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= MAX_OCTETS:
        return line

    parts: list[str] = []
    current = ""
    # 이어지는 줄은 공백 1옥텟을 먼저 쓰므로 그만큼 여유를 줄인다.
    budget = MAX_OCTETS
    for char in line:
        if len(current.encode("utf-8")) + len(char.encode("utf-8")) > budget:
            parts.append(current)
            current = char
            budget = MAX_OCTETS - 1
        else:
            current += char
    parts.append(current)
    return (CRLF + " ").join(parts)


def _utc_stamp(moment: datetime) -> str:
    """DATE-TIME (UTC). 예: `20260825T050000Z`."""
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _date_stamp(day: date) -> str:
    """DATE. 예: `20260912`."""
    return day.strftime("%Y%m%d")


class CalendarBuilder:
    """VEVENT 를 모아 VCALENDAR 문자열을 만든다."""

    def __init__(self, name: str, description: str = "") -> None:
        self._lines: list[str] = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:{PRODID}",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            # 구독형 캘린더에서 이름이 보이도록 하는 비표준 확장. 널리 쓰인다.
            f"X-WR-CALNAME:{escape_text(name)}",
        ]
        if description:
            self._lines.append(f"X-WR-CALDESC:{escape_text(description)}")

    def add_timed_event(
        self,
        *,
        uid: str,
        start: datetime,
        summary: str,
        stamp: datetime,
        description: str = "",
        url: str = "",
        end: datetime | None = None,
        alarm_minutes_before: int | None = None,
    ) -> None:
        """시각이 있는 일정. 예약 시작처럼 '몇 시'가 중요한 것."""
        self._lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{_utc_stamp(stamp)}",
            f"DTSTART:{_utc_stamp(start)}",
            f"DTEND:{_utc_stamp(end or start)}",
            f"SUMMARY:{escape_text(summary)}",
        ]
        if description:
            self._lines.append(f"DESCRIPTION:{escape_text(description)}")
        if url:
            self._lines.append(f"URL:{escape_text(url)}")
        if alarm_minutes_before is not None:
            # 캘린더 앱이 스스로 알려 주게 한다 — 푸시 인프라 없이 알림이 성립하는 지점이다.
            self._lines += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"TRIGGER:-PT{alarm_minutes_before}M",
                f"DESCRIPTION:{escape_text(summary)}",
                "END:VALARM",
            ]
        self._lines.append("END:VEVENT")

    def add_all_day_event(
        self, *, uid: str, day: date, summary: str, stamp: datetime, url: str = ""
    ) -> None:
        """종일 일정. 발매일처럼 '며칠'만 중요한 것."""
        self._lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{_utc_stamp(stamp)}",
            f"DTSTART;VALUE=DATE:{_date_stamp(day)}",
            f"SUMMARY:{escape_text(summary)}",
        ]
        if url:
            self._lines.append(f"URL:{escape_text(url)}")
        self._lines.append("END:VEVENT")

    def render(self) -> str:
        lines = [*self._lines, "END:VCALENDAR"]
        return CRLF.join(fold(line) for line in lines) + CRLF
