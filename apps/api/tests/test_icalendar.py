"""iCalendar 생성 규칙 (T-107, RFC 5545).

캘린더 앱은 형식에 엄격하고 **틀려도 조용히 무시**한다.
줄 끝·접기·이스케이프가 정확한지 여기서 고정한다.
"""

from datetime import UTC, date, datetime

import pytest

from orot_api.icalendar import MAX_OCTETS, CalendarBuilder, escape_text, fold

WHEN = datetime(2026, 8, 25, 5, 0, tzinfo=UTC)


def _build() -> str:
    calendar = CalendarBuilder("테스트 달력")
    calendar.add_timed_event(
        uid="preorder-1@vinyl-radar",
        start=WHEN,
        summary="예약 시작 · 실리카겔 — Machine Boy",
        stamp=WHEN,
        description="한정반\n김밥레코즈: https://example.com",
        url="https://example.com",
        alarm_minutes_before=30,
    )
    calendar.add_all_day_event(
        uid="release-1@vinyl-radar", day=date(2026, 9, 12), summary="발매 · Machine Boy", stamp=WHEN
    )
    return calendar.render()


def test_lines_end_with_crlf() -> None:
    """LF 만 쓰면 일부 캘린더 앱이 조용히 거부한다 (§3.1)."""
    raw = _build().encode()
    assert raw.count(b"\n") == raw.count(b"\r\n")


def test_no_line_exceeds_75_octets() -> None:
    """글자 수가 아니라 **바이트 수**다. 한글은 UTF-8 로 3바이트다 (§3.1)."""
    for line in _build().split("\r\n"):
        assert len(line.encode()) <= MAX_OCTETS, line


def test_folded_lines_unfold_back_to_original() -> None:
    """접은 줄을 펼치면 원본과 같아야 한다 — 한글이 중간에서 잘리면 깨진다."""
    original = "SUMMARY:" + "예약 시작 · 실리카겔 — Machine Boy 한정반 " * 3
    folded = fold(original)
    segments = folded.split("\r\n")
    unfolded = segments[0] + "".join(s[1:] for s in segments[1:])
    assert unfolded == original
    assert all(s.startswith(" ") for s in segments[1:])


def test_short_line_is_not_folded() -> None:
    assert fold("VERSION:2.0") == "VERSION:2.0"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a;b", "a\;b"),
        ("a,b", "a\\,b"),
        ("a\\b", "a\\\\b"),
        ("a\nb", "a\\nb"),
        ("a\r\nb", "a\\nb"),
    ],
)
def test_text_escaping(raw: str, expected: str) -> None:
    """§3.3.11. 역슬래시를 **먼저** 처리하지 않으면 이중 이스케이프가 된다."""
    assert escape_text(raw) == expected


def test_structure_is_balanced() -> None:
    output = _build()
    assert output.startswith("BEGIN:VCALENDAR")
    assert output.rstrip().endswith("END:VCALENDAR")
    assert output.count("BEGIN:VEVENT") == output.count("END:VEVENT") == 2
    assert output.count("BEGIN:VALARM") == output.count("END:VALARM") == 1


def test_timed_and_all_day_use_different_date_forms() -> None:
    """예약 시작은 '몇 시'가, 발매일은 '며칠'만 중요하다."""
    output = _build()
    assert "DTSTART:20260825T050000Z" in output  # 시각 있음
    assert "DTSTART;VALUE=DATE:20260912" in output  # 종일


def test_alarm_fires_before_the_event() -> None:
    """한정반은 오픈 직후 매진되므로 '곧 열린다'가 '지금 열렸다'보다 쓸모 있다."""
    assert "TRIGGER:-PT30M" in _build()


def test_uid_is_stable_for_the_same_release() -> None:
    """UID 가 바뀌면 캘린더 앱이 같은 일정을 새 일정으로 또 만든다 (§3.8.4.7)."""
    assert _build().count("UID:preorder-1@vinyl-radar") == 1
    assert _build() == _build()
