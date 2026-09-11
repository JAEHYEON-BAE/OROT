"""엣지 케이스를 모든 출력 경로에 통과시킨다.

카탈로그는 `vinyl_core.testing` 한 곳에 있다 — 경로마다 케이스를 따로 만들면
한쪽만 고쳐지고 다른 쪽이 조용히 깨진다.

검사하는 경로:
  1. API 입력 검증 (`ReleaseIn`)
  2. iCalendar 생성 (RFC 5545)
  3. RSS 생성 (RSS 2.0 + RFC 822)
  4. 푸시 페이로드
  5. 알림 표시 — 서비스워커가 그 페이로드로 실제로 무엇을 띄우는가
"""

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError
from vinyl_core.enums import EventType
from vinyl_core.notifications import build_payload
from vinyl_core.testing import ACCEPTED, REJECTED, EdgeCase

from vinyl_api.icalendar import MAX_OCTETS, CalendarBuilder
from vinyl_api.rss import RssBuilder
from vinyl_api.schemas.release import ReleaseIn

NOW = datetime(2026, 10, 1, 5, 0, tzinfo=UTC)


def _ids(cases: tuple[EdgeCase, ...]) -> list[str]:
    return [c.name for c in cases]


# ─── 1. API 입력 검증 ────────────────────────────────────────────


@pytest.mark.parametrize("case", REJECTED, ids=_ids(REJECTED))
def test_invalid_input_is_rejected(case: EdgeCase) -> None:
    """거부되어야 할 입력이 실제로 거부되는가.

    조용히 통과하면 알림이 안 나가거나 시각이 어긋난다 — 그때는 이미 늦다.
    """
    with pytest.raises(ValidationError):
        ReleaseIn.model_validate(case.payload)


@pytest.mark.parametrize("case", ACCEPTED, ids=_ids(ACCEPTED))
def test_valid_input_is_accepted(case: EdgeCase) -> None:
    """받아들여야 할 입력이 거부되지 않는가.

    지나치게 엄격하면 운영자가 아는 만큼만 입력하지 못한다.
    """
    payload = ReleaseIn.model_validate(case.payload)
    assert payload.title


def test_duplicate_links_survive_validation() -> None:
    """중복 URL 은 검증 단계에서 막지 않는다 — 저장 단계에서 합친다."""
    case = next(c for c in ACCEPTED if c.name == "duplicate_links")
    payload = ReleaseIn.model_validate(case.payload)
    assert len(payload.links) == 2
    assert payload.links[0].url == payload.links[1].url


def test_zero_price_is_allowed_but_negative_is_not() -> None:
    """증정품은 0원이 유효하다. 음수만 막아야 한다."""
    zero = next(c for c in ACCEPTED if c.name == "zero_price")
    assert ReleaseIn.model_validate(zero.payload).links[0].price_krw == Decimal(0)


# ─── 공통: 케이스를 Release 유사 객체로 ──────────────────────────


class _Link:
    def __init__(self, shop_name: str, url: str, price: int | None = None) -> None:
        self.id = 1
        self.shop_name = shop_name
        self.url = url
        self.price_krw = price


class _Release:
    """출력 경로 시험용 최소 객체."""

    def __init__(self, case: EdgeCase) -> None:
        payload = ReleaseIn.model_validate(case.payload)
        self.id = 1
        self.title = payload.title
        self.format = payload.format
        self.variant = payload.variant
        self.is_limited = payload.is_limited
        self.release_date = payload.release_date
        self.preorder_opens_at = payload.preorder_opens_at
        self.preorder_closes_at = payload.preorder_closes_at
        self.cover_url = payload.cover_url
        self.primary_artist_id = 1 if payload.artist_name else None
        self.links = [_Link(link.shop_name, link.url) for link in payload.links]
        self.artist_name = payload.artist_name


def _accepted_with_dates() -> list[EdgeCase]:
    """캘린더에 실릴 수 있는(날짜가 있는) 케이스만."""
    return [
        c for c in ACCEPTED if c.payload.get("preorder_opens_at") or c.payload.get("release_date")
    ]


# ─── 2. iCalendar ────────────────────────────────────────────────


@pytest.mark.parametrize("case", _accepted_with_dates(), ids=lambda c: c.name)
def test_icalendar_survives_edge_cases(case: EdgeCase) -> None:
    """어떤 입력이 와도 RFC 5545 형식이 깨지지 않아야 한다.

    캘린더 앱은 형식이 틀리면 **조용히 무시**한다 — 오류도 안 뜬다.
    """
    release = _Release(case)
    calendar = CalendarBuilder("테스트")
    label = f"{release.artist_name} — {release.title}" if release.artist_name else release.title

    if release.preorder_opens_at:
        calendar.add_timed_event(
            uid=f"preorder-{release.id}@vinyl-radar",
            start=release.preorder_opens_at,
            summary=f"예약 시작 · {label}",
            description="\n".join(f"{x.shop_name}: {x.url}" for x in release.links),
            url=release.links[0].url if release.links else "https://example.com/r/1",
            stamp=NOW,
            alarm_minutes_before=30,
        )
    if release.release_date:
        calendar.add_all_day_event(
            uid=f"release-{release.id}@vinyl-radar",
            day=release.release_date,
            summary=f"발매 · {label}",
            stamp=NOW,
        )

    output = calendar.render()
    raw = output.encode()
    lines = output.split("\r\n")

    assert raw.count(b"\n") == raw.count(b"\r\n"), "CRLF 로만 끝나야 한다"
    assert all(len(line.encode()) <= MAX_OCTETS for line in lines), "75옥텟 초과 줄이 있다"
    assert output.count("BEGIN:VEVENT") == output.count("END:VEVENT")
    assert output.count("BEGIN:VALARM") == output.count("END:VALARM")
    # 접은 줄을 펼치면 원문이 온전해야 한다.
    unfolded = output.replace("\r\n ", "")
    assert "SUMMARY:" in unfolded


def test_icalendar_escapes_special_characters() -> None:
    """`;` `,` `\\` 와 개행이 그대로 들어가면 캘린더 앱이 일정을 버린다."""
    case = next(c for c in ACCEPTED if c.name == "ics_special_chars")
    release = _Release(case)
    calendar = CalendarBuilder("t")
    calendar.add_timed_event(
        uid="u@x",
        start=release.preorder_opens_at,  # type: ignore[arg-type]
        summary=release.title,
        stamp=NOW,
    )
    unfolded = calendar.render().replace("\r\n ", "")
    summary = next(line for line in unfolded.split("\r\n") if line.startswith("SUMMARY:"))
    assert r"\;" in summary
    assert "\\," in summary
    assert "\\\\" in summary


def test_icalendar_has_no_raw_newlines_in_values() -> None:
    """제목에 개행이 들어와도 줄 구조가 깨지면 안 된다."""
    case = next(c for c in ACCEPTED if c.name == "newline_in_text")
    release = _Release(case)
    calendar = CalendarBuilder("t")
    calendar.add_timed_event(
        uid="u@x",
        start=release.preorder_opens_at,  # type: ignore[arg-type]
        summary=release.title,
        stamp=NOW,
    )
    unfolded = calendar.render().replace("\r\n ", "")
    for line in unfolded.split("\r\n"):
        if line.startswith("SUMMARY:"):
            assert "\\n" in line  # 이스케이프됨
    # 구조가 유지되는지 — BEGIN/END 가 짝을 이룬다
    assert unfolded.count("BEGIN:VEVENT") == unfolded.count("END:VEVENT") == 1


def test_multibyte_folding_stays_within_octet_limit() -> None:
    """**글자 수가 아니라 바이트 수**다. 한글은 3바이트, 이모지는 4바이트."""
    for name in ("emoji_and_mixed_scripts", "very_long_title"):
        case = next(c for c in ACCEPTED if c.name == name)
        release = _Release(case)
        calendar = CalendarBuilder("t")
        calendar.add_timed_event(
            uid="u@x",
            start=release.preorder_opens_at,  # type: ignore[arg-type]
            summary=f"예약 시작 · {release.artist_name} — {release.title}",
            stamp=NOW,
        )
        for line in calendar.render().split("\r\n"):
            assert len(line.encode()) <= MAX_OCTETS, f"{name}: {len(line.encode())} octets"


def test_release_without_any_date_produces_no_event() -> None:
    """캘린더에 찍을 자리가 없는 일정은 `.ics` 에 들어가면 안 된다."""
    case = next(c for c in ACCEPTED if c.name == "no_dates_at_all")
    release = _Release(case)
    assert release.preorder_opens_at is None
    assert release.release_date is None
    # 라우터의 필터 조건과 같은 판정.
    assert not (release.preorder_opens_at or release.release_date)


# ─── 3. RSS ──────────────────────────────────────────────────────


@pytest.mark.parametrize("case", ACCEPTED, ids=_ids(ACCEPTED))
def test_rss_stays_well_formed(case: EdgeCase) -> None:
    """어떤 제목이 와도 XML 이 파싱 가능해야 한다.

    한 항목이 깨지면 **피드 전체**를 리더가 못 읽는다.
    """
    release = _Release(case)
    label = f"{release.artist_name} — {release.title}" if release.artist_name else release.title
    feed = RssBuilder(
        title="t",
        link="https://e.com",
        description="d",
        self_url="https://e.com/f.rss",
        build_time=NOW,
    )
    feed.add_item(
        title=f"[새 일정] {label}",
        link=release.links[0].url if release.links else "https://e.com/r/1",
        guid="event-1@vinyl-radar",
        published_at=NOW,
        description=" · ".join(f"{x.shop_name}: {x.url}" for x in release.links) or "정보 없음",
        categories=["새 일정"],
    )
    root = ET.fromstring(feed.render())  # 파싱 실패하면 여기서 터진다
    item = root.find("channel/item")
    assert item is not None
    assert parsedate_to_datetime(item.findtext("pubDate") or "") == NOW


def test_rss_round_trips_xml_special_characters() -> None:
    """이스케이프한 값이 파싱하면 원본으로 돌아와야 한다."""
    case = next(c for c in ACCEPTED if c.name == "xml_special_chars")
    release = _Release(case)
    feed = RssBuilder(
        title="t", link="https://e.com", description="d", self_url="https://e.com/f.rss"
    )
    feed.add_item(
        title=release.title,
        link=release.links[0].url,
        guid="g",
        published_at=NOW,
    )
    item = ET.fromstring(feed.render()).find("channel/item")
    assert item is not None
    assert item.findtext("title") == release.title
    assert item.findtext("link") == "https://e.com/p?a=1&b=2"


# ─── 4. 푸시 페이로드 ────────────────────────────────────────────


class _Event:
    def __init__(self, event_type: str) -> None:
        self.event_type = event_type


@pytest.mark.parametrize("case", ACCEPTED, ids=_ids(ACCEPTED))
def test_push_payload_is_always_displayable(case: EdgeCase) -> None:
    """알림에 제목과 본문이 항상 있어야 한다.

    빈 본문은 사용자에게 **알림이 잘린 것처럼** 보인다.
    """
    release = _Release(case)
    payload = build_payload(
        _Event(EventType.PREORDER_OPEN.value),  # type: ignore[arg-type]
        release,  # type: ignore[arg-type]
        release.artist_name,
        "https://e.com",
    )
    assert payload["title"]
    assert payload["body"]
    assert str(payload["url"]).startswith("https://e.com/releases/")
    assert payload["tag"] == "release-1-PREORDER_OPEN"


def test_push_payload_without_artist_falls_back_to_title() -> None:
    case = next(c for c in ACCEPTED if c.name == "no_artist")
    release = _Release(case)
    payload = build_payload(
        _Event(EventType.SCHEDULE_ADDED.value),  # type: ignore[arg-type]
        release,  # type: ignore[arg-type]
        None,
        "https://e.com",
    )
    assert release.title in str(payload["title"])
    assert "—" not in str(payload["title"])  # 빈 아티스트 자리가 남지 않는다


def test_push_payload_without_links_still_has_a_destination() -> None:
    """구매처가 없어도 누를 곳이 있어야 한다 — 우리 상세 페이지로 보낸다."""
    case = next(c for c in ACCEPTED if c.name == "no_links")
    release = _Release(case)
    assert release.links == []
    payload = build_payload(
        _Event(EventType.PREORDER_OPEN.value),  # type: ignore[arg-type]
        release,  # type: ignore[arg-type]
        release.artist_name,
        "https://e.com",
    )
    assert payload["url"] == "https://e.com/releases/1"


# ─── 카탈로그 자체의 건강성 ──────────────────────────────────────


def test_every_case_documents_what_and_why() -> None:
    """기대값만 있는 테스트는 나중에 누가 그냥 고쳐 버린다."""
    for case in (*REJECTED, *ACCEPTED):
        assert case.what, case.name
        assert case.why, case.name


def test_case_names_are_unique() -> None:
    names = [c.name for c in (*REJECTED, *ACCEPTED)]
    assert len(names) == len(set(names))


# ─── 5. 알림 표시 (서비스워커) ───────────────────────────────────
# 서비스워커는 페이로드를 그대로 화면에 띄운다. 여기서 걸러지지 않은 값은
# 사용자 눈에 그대로 보인다 — 그리고 알림은 되돌릴 수 없다.

SW_PATH = Path(__file__).resolve().parents[3] / "apps" / "web" / "public" / "sw.js"


def _payload_for(case: EdgeCase, event_type: str = EventType.PREORDER_OPEN.value) -> dict[str, str]:
    release = _Release(case)
    raw = build_payload(
        _Event(event_type),  # type: ignore[arg-type]
        release,  # type: ignore[arg-type]
        release.artist_name,
        "https://e.com",
    )
    return {k: str(v) for k, v in raw.items()}


@pytest.mark.parametrize("case", ACCEPTED, ids=_ids(ACCEPTED))
def test_notification_text_is_single_line(case: EdgeCase) -> None:
    """알림 제목·본문에 개행이나 제어문자가 남으면 안 된다.

    알림은 한 줄 영역이다. 개행을 그대로 넘기면 크롬은 공백으로 접고 일부
    안드로이드 런처는 **거기서 잘라 버려** 뒷부분이 사라진다. 브라우저마다
    다르게 보이는 것을 서버에서 한 번 정리한다.
    """
    payload = _payload_for(case)
    for field in ("title", "body"):
        value = payload[field]
        assert "\n" not in value, f"{field} 에 개행이 남아 있다"
        assert "\r" not in value
        assert "\t" not in value
        assert value == value.strip(), f"{field} 앞뒤에 공백이 남아 있다"
        assert "  " not in value, f"{field} 에 연속 공백이 남아 있다"


@pytest.mark.parametrize("case", ACCEPTED, ids=_ids(ACCEPTED))
def test_notification_url_is_absolute_and_same_origin(case: EdgeCase) -> None:
    """알림을 누르면 갈 곳이 항상 있어야 하고, 그곳은 우리 사이트여야 한다.

    구매처 URL 을 바로 넣으면 판매처가 링크를 바꿨을 때 막다른 길이 된다.
    상세 페이지를 거치면 링크가 여러 개여도, 하나도 없어도 화면이 나온다.
    """
    parsed = urlparse(_payload_for(case)["url"])
    assert parsed.scheme in {"http", "https"}
    assert parsed.netloc == "e.com"
    assert parsed.path.startswith("/releases/")


def test_notification_tag_separates_events_so_history_survives() -> None:
    """서로 다른 알림은 서로를 지우지 않는다 (T-131).

    브라우저는 같은 `tag` 의 알림을 대체한다. 발매 단위로 묶으면 '예약 임박'이
    '예약 시작'에 덮여 **알림 목록에서 사라진다.** 목록은 상태가 아니라 기록이고,
    놓친 알림을 나중에 돌아보는 곳이다.

    피드는 반대로 발매당 하나만 싣는다 (T-118) — 그쪽은 지금 상태를 보는 화면이다.
    두 규칙이 다른 것은 두 화면의 목적이 다르기 때문이다.
    """
    case = next(c for c in ACCEPTED if c.name == "only_preorder")
    soon = _payload_for(case, EventType.PREORDER_OPENS_SOON.value)
    now = _payload_for(case, EventType.PREORDER_OPEN.value)
    assert soon["tag"] != now["tag"]
    assert soon["title"] != now["title"]


def test_same_event_refired_replaces_the_stale_one() -> None:
    """일정이 바뀌어 다시 발생한 알림은 **옛것을 대체해야** 한다 (T-119).

    옛 '예약 시작'은 틀린 시각을 말하고 있다. 두 개가 나란히 남으면
    어느 쪽을 믿어야 할지 알 수 없다 — 그래서 같은 이벤트끼리는 tag 가 같다.
    """
    case = next(c for c in ACCEPTED if c.name == "only_preorder")
    first = _payload_for(case, EventType.PREORDER_OPEN.value)
    refired = _payload_for(case, EventType.PREORDER_OPEN.value)
    assert first["tag"] == refired["tag"]


def test_tag_includes_the_release_id() -> None:
    """다른 발매의 알림이 서로를 지우면 안 된다.

    카탈로그의 시험용 객체는 id 가 모두 1 이라 여기서 직접 만들어 비교한다.
    """
    event = _Event(EventType.PREORDER_OPEN.value)
    base = _Release(next(c for c in ACCEPTED if c.name == "only_preorder"))

    base.id = 7
    seven = str(build_payload(event, base, None, "https://e.com")["tag"])  # type: ignore[arg-type]
    base.id = 8
    eight = str(build_payload(event, base, None, "https://e.com")["tag"])  # type: ignore[arg-type]

    assert seven != eight
    assert seven == "release-7-PREORDER_OPEN"


def test_service_worker_renotifies_on_replaced_notification() -> None:
    """tag 로 묶은 알림은 기본적으로 **소리 없이** 교체된다.

    '예약 임박' 위에 '예약 시작'이 조용히 덮이면 이 제품이 유일하게
    놓치면 안 되는 순간을 놓친다. renotify 로 다시 알려야 한다.
    """
    source = SW_PATH.read_text(encoding="utf-8")
    assert "renotify: true" in source
    # renotify 는 tag 가 있어야 동작한다.
    assert "tag: data.tag" in source


def test_service_worker_reads_exactly_the_keys_the_server_sends() -> None:
    """서버가 보내는 키와 서비스워커가 읽는 키가 어긋나면 **조용히** 기본 문구가 뜬다.

    오류도 로그도 없이 "새 일정이 있습니다"만 계속 나가는 상태가 된다.
    한쪽만 고치는 순간을 여기서 잡는다.
    """
    sent = set(_payload_for(ACCEPTED[0]))
    source = SW_PATH.read_text(encoding="utf-8")
    # `event.data` 는 푸시 이벤트의 원본이지 페이로드가 아니다 — 뒤에 오는
    # `.json()` 을 키로 세지 않도록 제외한다.
    read = set(re.findall(r"(?<!event\.)\bdata\.(\w+)", source))
    # 서비스워커가 읽는 것은 모두 서버가 보내야 한다.
    assert read <= sent, f"서버가 보내지 않는 키를 읽고 있다: {read - sent}"


def test_service_worker_always_shows_a_notification() -> None:
    """페이로드가 깨져도 알림은 떠야 한다.

    `userVisibleOnly` 로 구독했기 때문에, 푸시를 받고 알림을 띄우지 않으면
    브라우저가 대체 알림을 대신 띄우고 **반복되면 푸시 권한을 회수한다.**
    """
    source = SW_PATH.read_text(encoding="utf-8")
    assert "FALLBACK" in source
    # 파싱 실패를 삼키고 기본값으로 넘어가야 한다 (CLAUDE.md §2 규칙 5 와 달리
    # 여기서는 던지면 사용자가 알림을 못 받는다 — 로그는 남긴다).
    assert "catch" in source and "console.error" in source
    # waitUntil 없이 부르면 알림이 뜨기 전에 워커가 종료될 수 있다.
    assert "event.waitUntil(" in source


def test_very_long_title_is_not_truncated_by_us() -> None:
    """길이는 우리가 자르지 않는다 — 어디서 자를지는 OS 가 안다.

    300자 제목을 우리가 100자로 자르면 어떤 기기에서도 그 이상 볼 수 없다.
    """
    case = next(c for c in ACCEPTED if c.name == "very_long_title")
    assert len(_payload_for(case)["title"]) > 300
