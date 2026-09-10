"""RFC 9457 Problem Details 오류 응답 (블루프린트 §5.1).

FastAPI 기본 형식은 `{"detail": "..."}` 인데, §5.1 은 RFC 9457 을 요구한다.
차이는 형식만이 아니다 — RFC 9457 은 `status`·`instance` 를 본문에 담아
**로그나 버그 리포트에 응답만 붙여도 어느 요청이 왜 실패했는지 알 수 있게** 한다.
"""

from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger(__name__)

# RFC 9457 §3: 문제 유형을 특정하지 않을 때의 기본값.
DEFAULT_TYPE = "about:blank"
CONTENT_TYPE = "application/problem+json"


def problem_response(
    status_code: int,
    detail: str,
    request: Request | None = None,
    *,
    title: str | None = None,
    problem_type: str = DEFAULT_TYPE,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """RFC 9457 형식의 응답을 만든다."""
    body: dict[str, Any] = {
        "type": problem_type,
        "title": title or HTTPStatus(status_code).phrase,
        "status": status_code,
        "detail": detail,
    }
    if request is not None:
        body["instance"] = request.url.path
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body, media_type=CONTENT_TYPE)


def register_problem_handlers(app: FastAPI) -> None:
    """앱에 오류 핸들러를 등록한다."""

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        response = problem_response(exc.status_code, str(exc.detail), request)
        # 인증 실패의 WWW-Authenticate 같은 헤더를 잃지 않는다.
        headers = getattr(exc, "headers", None)
        if headers:
            response.headers.update(headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 어느 필드가 왜 틀렸는지는 확장 멤버로 싣는다 (RFC 9457 §3.2).
        # 운영자가 폼에서 무엇을 고쳐야 하는지 알아야 하기 때문이다.
        errors = [
            {"field": ".".join(str(p) for p in err["loc"][1:]) or "body", "message": err["msg"]}
            for err in exc.errors()
        ]
        return problem_response(
            422,
            "요청 내용이 올바르지 않습니다.",
            request,
            title="Unprocessable Entity",
            extra={"errors": errors},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # 내부 오류의 상세는 **응답에 넣지 않는다.** 스택 트레이스는 로그로만 남긴다.
        log.exception("api.unhandled_error", path=request.url.path, error=str(exc))
        return problem_response(500, "서버 내부 오류가 발생했습니다.", request)
