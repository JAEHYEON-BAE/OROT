"""커서 기반 페이지네이션 (블루프린트 §5.1).

오프셋을 쓰지 않는 이유: 일정이 계속 추가되므로 페이지를 넘기는 사이 목록이 밀려
같은 항목을 두 번 보거나 건너뛴다. keyset 방식은 그런 어긋남이 없다.

정렬 키가 `preorder_opens_at` 인데 **NULL 이 섞인다.** 날짜 미정 일정도 등록되기 때문이다.
NULL 을 특별 취급하는 대신 PostgreSQL 의 `'infinity'::timestamptz` 로 치환하면
"날짜 미정은 맨 뒤"가 자연스럽게 성립하고 비교식도 단순해진다.
"""

import base64
import binascii
from datetime import datetime
from typing import Final

DEFAULT_LIMIT: Final = 20
MAX_LIMIT: Final = 100  # §5.1

_SEPARATOR: Final = "|"
_INFINITY: Final = "infinity"


class InvalidCursorError(ValueError):
    """커서를 해독할 수 없을 때."""


def encode_cursor(sort_key: datetime | None, row_id: int) -> str:
    """정렬 키와 id 를 불투명한 문자열로 만든다.

    호출자가 내부 구조에 의존하지 않도록 base64 로 감싼다 — §5.1 의 "opaque" 요구사항.
    """
    key = _INFINITY if sort_key is None else sort_key.isoformat()
    raw = f"{key}{_SEPARATOR}{row_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime | None, int]:
    """커서를 (정렬 키, id) 로 되돌린다. 형식이 깨졌으면 예외."""
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        key_text, id_text = raw.rsplit(_SEPARATOR, 1)
        row_id = int(id_text)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        msg = "커서 형식이 올바르지 않습니다."
        raise InvalidCursorError(msg) from exc

    if key_text == _INFINITY:
        return None, row_id
    try:
        return datetime.fromisoformat(key_text), row_id
    except ValueError as exc:
        msg = "커서의 정렬 키를 해석할 수 없습니다."
        raise InvalidCursorError(msg) from exc


def clamp_limit(limit: int) -> int:
    """§5.1: 최대 100."""
    return max(1, min(limit, MAX_LIMIT))
