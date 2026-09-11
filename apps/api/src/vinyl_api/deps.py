"""FastAPI 의존성."""

import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from vinyl_core.db import get_session_factory
from vinyl_core.settings import get_settings


async def get_session() -> AsyncIterator[AsyncSession]:
    """요청 단위 DB 세션. 예외 시 롤백한다."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    """운영자 인증 (ADR-0005, 블루프린트 §5.2-1).

    헤더 하나로 끝낸다 — 사용자가 1명(운영자)인 단계에서 OAuth 는 과설계다.
    실패 사유를 구분해 알려주지 않는다 (키 존재 여부가 새지 않도록).
    """
    # **상수 시간 비교** (T-130). `!=` 는 첫 불일치 바이트에서 끝나므로, 응답 시간
    # 차이로 키를 한 글자씩 좁혀 나갈 여지가 남는다. 한 줄로 그 여지를 없앤다.
    expected = get_settings().admin_api_key
    if not expected.strip() or not secrets.compare_digest(
        (x_admin_key or "").encode(), expected.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="운영자 인증이 필요합니다.",
            headers={"WWW-Authenticate": "X-Admin-Key"},
        )


SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
AdminDep = Annotated[None, Depends(require_admin)]
