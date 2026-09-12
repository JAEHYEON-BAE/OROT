"""Bound push bodies before FastAPI's JSON parser allocates them."""

import asyncio

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from orot_api.problems import problem_response

MAX_PUSH_BODY = 8192


class PushBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["path"].rstrip("/") != "/v1/push/subscribe"
            or scope["method"] not in {"POST", "DELETE"}
        ):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        length = headers.get("content-length")
        if length is not None and (
            not length.isascii()
            or not length.isdigit()
            or len(length) > 5
            or int(length) > MAX_PUSH_BODY
        ):
            await problem_response(413, "요청 본문이 너무 큽니다.")(scope, receive, send)
            return
        body = bytearray()
        try:
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > MAX_PUSH_BODY:
                        await problem_response(413, "요청 본문이 너무 큽니다.")(
                            scope, receive, send
                        )
                        return
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await problem_response(408, "요청 본문 읽기 시간이 초과되었습니다.")(
                scope, receive, send
            )
            return

        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, bounded_receive, send)
