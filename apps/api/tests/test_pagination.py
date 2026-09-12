"""커서 페이지네이션 단위 테스트 (T-105).

DB 없이 인코딩·디코딩 계약만 검사한다.
"""

from datetime import UTC, datetime

import pytest

from orot_api.pagination import (
    MAX_LIMIT,
    InvalidCursorError,
    clamp_limit,
    decode_cursor,
    encode_cursor,
)


def test_roundtrip_with_timestamp() -> None:
    when = datetime(2026, 8, 25, 5, 0, tzinfo=UTC)
    assert decode_cursor(encode_cursor(when, 42)) == (when, 42)


def test_roundtrip_with_null_sort_key() -> None:
    """날짜 미정 일정도 커서에 담겨야 한다 — 정렬 맨 뒤에 모여 있기 때문이다."""
    assert decode_cursor(encode_cursor(None, 7)) == (None, 7)


def test_cursor_is_opaque() -> None:
    """§5.1 은 커서를 불투명하게 요구한다. 내부 구조가 그대로 보이면 안 된다."""
    cursor = encode_cursor(datetime(2026, 8, 25, tzinfo=UTC), 42)
    assert "2026" not in cursor
    assert "|" not in cursor


@pytest.mark.parametrize("bad", ["", "!!!", "Zm9vYmFy", "not-base64!!"])
def test_malformed_cursor_is_rejected(bad: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(bad)


@pytest.mark.parametrize(("given", "expected"), [(1, 1), (20, 20), (100, 100), (101, MAX_LIMIT)])
def test_limit_is_clamped(given: int, expected: int) -> None:
    assert clamp_limit(given) == expected
