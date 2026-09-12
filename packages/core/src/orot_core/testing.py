"""엣지 케이스 카탈로그 — 모든 출력 경로에서 재사용한다.

한 곳에 모아 두는 이유: 같은 입력이 **API 검증 · iCalendar · RSS · 푸시 페이로드 ·
웹 화면**을 모두 통과한다. 경로마다 따로 케이스를 만들면 한쪽만 고쳐지고 다른 쪽이
조용히 깨진다.

각 케이스는 **무엇을 시험하는지**와 **왜 그렇게 기대하는지**를 함께 적는다.
기대값만 있는 테스트는 나중에 누가 "이건 왜 이렇지?" 하며 그냥 고쳐 버린다.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal

# 케이스 제목에 붙이는 접두사. 검증 데이터를 골라 지울 때 쓴다 (CLAUDE.md §2 규칙 10).
EDGE_PREFIX: Final = "__EDGE__"

_NOW: Final = datetime(2026, 10, 1, 5, 0, tzinfo=UTC)


def _kst(offset: timedelta) -> str:
    """KST 오프셋이 붙은 ISO 문자열. 폼이 보내는 형태와 같다."""
    return (_NOW + offset).astimezone(UTC).isoformat().replace("+00:00", "+00:00")


Expectation = Literal["ACCEPT", "REJECT"]


@dataclass(frozen=True, slots=True)
class EdgeCase:
    """하나의 시험 입력."""

    name: str
    what: str
    """무엇을 시험하는가."""
    why: str
    """왜 그 결과를 기대하는가."""
    expect: Expectation
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return str(self.payload.get("title", ""))


def _case(name: str, what: str, why: str, expect: Expectation, **payload: Any) -> EdgeCase:
    payload.setdefault("title", f"{EDGE_PREFIX}{name}")
    return EdgeCase(name=name, what=what, why=why, expect=expect, payload=payload)


# ─── 거부되어야 하는 입력 ────────────────────────────────────────
# 조용히 받아들이면 나중에 알림이 안 가거나 시각이 어긋난다.

REJECTED: Final[tuple[EdgeCase, ...]] = (
    _case(
        "missing_title",
        "앨범 이름 없음",
        "제목이 없으면 알림에 표시할 것이 없다. 빈 알림은 노이즈다.",
        "REJECT",
        title=None,
    ),
    _case(
        "empty_title",
        "앨범 이름이 빈 문자열",
        "None 과 빈 문자열을 다르게 다루면 한쪽만 막히는 구멍이 생긴다.",
        "REJECT",
        title="",
    ),
    _case(
        "window_inverted",
        "예약 마감이 시작보다 앞섬",
        "구매 가능 구간이 음수다. 캘린더에 그릴 수 없고 알림 순서가 뒤집힌다.",
        "REJECT",
        preorder_opens_at=_kst(timedelta(days=5)),
        preorder_closes_at=_kst(timedelta(days=1)),
    ),
    _case(
        "window_zero_length",
        "예약 시작과 마감이 같음",
        "0초짜리 구간은 실수다. 경계를 열어 두면 '마감 == 시작'이 통과한다.",
        "REJECT",
        preorder_opens_at=_kst(timedelta(days=3)),
        preorder_closes_at=_kst(timedelta(days=3)),
    ),
    _case(
        "naive_datetime",
        "타임존 없는 시각",
        "몇 시인지 알 수 없다. 통과시키면 알림이 9시간 어긋난다 (CLAUDE.md §6).",
        "REJECT",
        preorder_opens_at="2026-10-01T14:00:00",
    ),
    _case(
        "fractional_price",
        "가격에 소수점",
        "원화에 소수 단위가 없다. NUMERIC(12,0) 이 조용히 반올림한다.",
        "REJECT",
        links=[{"shop_name": "샵", "url": "https://e.com/a", "price_krw": "52000.5"}],
    ),
    _case(
        "negative_price",
        "음수 가격",
        "가격 비교와 표시가 모두 깨진다.",
        "REJECT",
        links=[{"shop_name": "샵", "url": "https://e.com/a", "price_krw": "-1"}],
    ),
    _case(
        "link_without_url",
        "구매처 URL 없음",
        "링크 없는 구매처는 누를 수 없다. 알림에서 막다른 길이 된다.",
        "REJECT",
        links=[{"shop_name": "샵", "url": ""}],
    ),
    _case(
        "link_without_shop_name",
        "판매처 이름 없음",
        "어디서 파는지 모르는 링크는 사용자가 신뢰하지 않는다.",
        "REJECT",
        links=[{"shop_name": "", "url": "https://e.com/a"}],
    ),
)


# ─── 받아들이되 안전하게 처리해야 하는 입력 ──────────────────────
# 거부하면 운영자가 아는 만큼만 입력하지 못한다. 빠진 정보는 화면에서 접어야 한다.

ACCEPTED: Final[tuple[EdgeCase, ...]] = (
    _case(
        "no_artist",
        "아티스트 이름 없음",
        "컴필레이션·사운드트랙은 아티스트가 없다. 제목만으로 표시되어야 한다.",
        "ACCEPT",
        preorder_opens_at=_kst(timedelta(days=2)),
    ),
    _case(
        "no_links",
        "구매처 없음",
        "예약 공지만 뜨고 판매 링크가 아직 없는 경우가 실제로 있다. "
        "이때 캘린더·알림은 우리 상세 페이지로 보내야 한다.",
        "ACCEPT",
        artist_name=f"{EDGE_PREFIX}아티스트",
        preorder_opens_at=_kst(timedelta(days=2)),
    ),
    _case(
        "no_cover",
        "커버 이미지 없음",
        "부가 정보가 없다고 항목 전체를 버리면 안 된다.",
        "ACCEPT",
        artist_name=f"{EDGE_PREFIX}아티스트",
        cover_url=None,
        preorder_opens_at=_kst(timedelta(days=2)),
    ),
    _case(
        "no_dates_at_all",
        "예약 시각도 발매일도 없음",
        "정보가 아직 없는 단계에서도 등록은 되어야 한다. "
        "다만 **캘린더에는 찍을 자리가 없으므로 .ics 에서 빠져야 한다.**",
        "ACCEPT",
        artist_name=f"{EDGE_PREFIX}아티스트",
    ),
    _case(
        "only_release_date",
        "발매일만 있고 예약 시각 없음",
        "예약 없이 발매만 하는 경우다. 종일 일정으로만 나가야 한다.",
        "ACCEPT",
        artist_name=f"{EDGE_PREFIX}아티스트",
        release_date="2026-12-25",
    ),
    _case(
        "only_preorder",
        "예약 시각만 있고 발매일 없음",
        "가장 흔한 경우다. 발매일 미정이어도 알림은 나가야 한다.",
        "ACCEPT",
        artist_name=f"{EDGE_PREFIX}아티스트",
        preorder_opens_at=_kst(timedelta(days=2)),
    ),
    _case(
        "already_closed",
        "예약 시작·마감이 모두 과거",
        "지난 일정도 기록으로 남는다. 다만 백필 상한에 걸려 알림은 나가지 않아야 한다.",
        "ACCEPT",
        artist_name=f"{EDGE_PREFIX}아티스트",
        preorder_opens_at=_kst(timedelta(days=-30)),
        preorder_closes_at=_kst(timedelta(days=-20)),
    ),
    _case(
        "xml_special_chars",
        "제목에 XML 특수문자",
        "RSS 에서 이스케이프하지 않으면 피드 전체가 파싱 실패한다. "
        "역슬래시를 먼저 처리하지 않으면 이중 이스케이프가 된다.",
        "ACCEPT",
        title=f"{EDGE_PREFIX}난춘 <7\"> & '단독'",
        artist_name="새소년 & Friends",
        preorder_opens_at=_kst(timedelta(days=2)),
        links=[{"shop_name": "김밥 & 레코즈", "url": "https://e.com/p?a=1&b=2"}],
    ),
    _case(
        "ics_special_chars",
        "제목에 iCalendar 특수문자 (; , \\)",
        "RFC 5545 §3.3.11 이스케이프. 빠뜨리면 캘린더 앱이 일정을 조용히 버린다.",
        "ACCEPT",
        title=f"{EDGE_PREFIX}A;B,C\\D",
        artist_name="세미콜론;쉼표,역슬래시\\",
        preorder_opens_at=_kst(timedelta(days=2)),
    ),
    _case(
        "newline_in_text",
        "제목에 개행",
        "iCalendar 는 줄 단위 형식이라 개행이 그대로 들어가면 구조가 깨진다.",
        "ACCEPT",
        title=f"{EDGE_PREFIX}첫 줄\n둘째 줄",
        artist_name="개행\r\n아티스트",
        preorder_opens_at=_kst(timedelta(days=2)),
    ),
    _case(
        "emoji_and_mixed_scripts",
        "이모지와 다국어 혼용",
        "UTF-8 다중바이트다. **75옥텟 접기를 글자 수로 세면 규격을 넘는다.**",
        "ACCEPT",
        title=f"{EDGE_PREFIX}🎵 春 spring 봄 ばる",
        artist_name="実験室 🔬 Lab",
        preorder_opens_at=_kst(timedelta(days=2)),
    ),
    _case(
        "very_long_title",
        "아주 긴 제목 (300자)",
        "저장 경로 어디에도 길이 제한이 없어야 하고, iCalendar 는 접어야 한다.",
        "ACCEPT",
        title=EDGE_PREFIX + ("가" * 150) + ("A" * 150),
        artist_name="긴" * 60,
        preorder_opens_at=_kst(timedelta(days=2)),
    ),
    _case(
        "duplicate_links",
        "같은 URL 을 두 번 입력",
        "운영자의 흔한 실수다. 오류가 아니라 중복 제거로 다뤄야 한다 "
        "(UNIQUE(release_id,url) 때문에 막지 않으면 500 이 난다).",
        "ACCEPT",
        artist_name=f"{EDGE_PREFIX}아티스트",
        preorder_opens_at=_kst(timedelta(days=2)),
        links=[
            {"shop_name": "김밥레코즈", "url": "https://e.com/dup", "price_krw": "52000"},
            {"shop_name": "다른이름", "url": "https://e.com/dup", "price_krw": "99999"},
        ],
    ),
    _case(
        "many_links",
        "구매처 10곳",
        "한 발매를 여러 곳에서 판다. 알림 본문과 캘린더 설명이 감당해야 한다.",
        "ACCEPT",
        artist_name=f"{EDGE_PREFIX}아티스트",
        preorder_opens_at=_kst(timedelta(days=2)),
        links=[
            {"shop_name": f"판매처{i}", "url": f"https://e.com/s{i}", "price_krw": str(50000 + i)}
            for i in range(10)
        ],
    ),
    _case(
        "far_future",
        "먼 미래 발매일",
        "연도 자릿수나 정렬이 깨지지 않는지 본다.",
        "ACCEPT",
        artist_name=f"{EDGE_PREFIX}아티스트",
        release_date="2099-12-31",
        preorder_opens_at=_kst(timedelta(days=365)),
    ),
    _case(
        "zero_price",
        "가격 0원",
        "증정품·무료 배포가 있다. 음수와 달리 0 은 유효한 값이다.",
        "ACCEPT",
        artist_name=f"{EDGE_PREFIX}아티스트",
        preorder_opens_at=_kst(timedelta(days=2)),
        links=[{"shop_name": "샵", "url": "https://e.com/free", "price_krw": "0"}],
    ),
)


ALL_CASES: Final[tuple[EdgeCase, ...]] = REJECTED + ACCEPTED
