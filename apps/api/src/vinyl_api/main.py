"""FastAPI 애플리케이션 진입점.

현재 구현된 것은 헬스체크뿐이다 (T-001).
도메인 엔드포인트는 `/v1` 아래에 T-010 이후 추가된다 (블루프린트 §5.2).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from vinyl_core import __version__ as core_version
from vinyl_core.db import get_engine, ping
from vinyl_core.logging import configure_logging
from vinyl_core.settings import get_settings

from vinyl_api.problems import register_problem_handlers
from vinyl_api.routers import admin, admin_ui, calendar, feed, push, releases, rss

log = structlog.get_logger(__name__)

API_PREFIX = "/v1"  # 블루프린트 §5.1


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """기동 시 로깅을 설정하고, 종료 시 DB 커넥션 풀을 정리한다."""
    configure_logging()
    settings = get_settings()
    log.info("api.startup", environment=settings.environment, core_version=core_version)
    try:
        yield
    finally:
        await get_engine().dispose()
        log.info("api.shutdown")


app = FastAPI(
    title="Vinyl Radar API",
    version=core_version,
    description="국내 바이닐 발매·재고 정보 통합 API",
    lifespan=lifespan,
)


register_problem_handlers(app)

app.include_router(admin.router)
app.include_router(admin_ui.router)
app.include_router(releases.router)
app.include_router(feed.router)
app.include_router(calendar.router)
app.include_router(rss.router)
app.include_router(push.router)


class HealthResponse(BaseModel):
    """`/healthz` 응답 본문."""

    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    version: str


@app.get("/healthz", response_model=HealthResponse, tags=["meta"])
async def healthz() -> JSONResponse:
    """헬스체크. 블루프린트 §5.2 에 따라 **DB 연결까지 확인**한다.

    DB 가 응답하지 않으면 503 을 반환한다. 배포 검증(§9.5)이 이 응답에 의존하므로
    DB 장애를 200 으로 감추지 않는다.
    """
    try:
        await ping()
    except Exception as exc:
        log.error("healthz.database_unavailable", error=str(exc), exc_info=True)
        body = HealthResponse(status="degraded", database="unavailable", version=core_version)
        return JSONResponse(status_code=503, content=body.model_dump())

    body = HealthResponse(status="ok", database="ok", version=core_version)
    return JSONResponse(status_code=200, content=body.model_dump())
