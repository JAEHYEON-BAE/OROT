"""응답 캐싱 헤더 (블루프린트 §5.1).

> 캐싱: 목록 응답에 `ETag` 및 `Cache-Control: public, max-age=60`
"""

import hashlib
from collections.abc import Sequence

from fastapi import Response
from pydantic import BaseModel

CACHE_CONTROL = "public, max-age=60"


def set_cache_headers(response: Response, payload: BaseModel | Sequence[BaseModel]) -> None:
    """내용 해시로 `ETag` 를 만들고 `Cache-Control` 을 붙인다.

    시각처럼 매 요청 바뀌는 값은 넘기지 않는다 — 넣으면 ETag 가 항상 달라져
    조건부 요청이 무의미해진다.
    """
    if isinstance(payload, BaseModel):
        body = payload.model_dump_json()
    else:
        # Preserve model JSON serializers without constructing a runtime type expression.
        body = "[" + ",".join(item.model_dump_json() for item in payload) + "]"
    etag = hashlib.sha256(body.encode()).hexdigest()[:32]
    response.headers["ETag"] = f'"{etag}"'
    response.headers["Cache-Control"] = CACHE_CONTROL
