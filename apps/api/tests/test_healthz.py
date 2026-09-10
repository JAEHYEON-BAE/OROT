"""`/healthz` 계약 테스트 (T-001).

CLAUDE.md §2 규칙 2 에 따라 외부 네트워크를 사용하지 않는다.
DB 는 실물 대신 `vinyl_core.db.ping` 을 대체하여 두 경로를 모두 검증한다.
실 PostgreSQL 대상 통합 테스트는 블루프린트 §9.3 에 따라 T-010 에서 testcontainers 로 추가한다.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from vinyl_api.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def test_healthz_returns_200_when_database_reachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _ok() -> bool:
        return True

    monkeypatch.setattr("vinyl_api.main.ping", _ok)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "version": "0.1.0"}


def test_healthz_returns_503_when_database_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DB 장애를 200 으로 감추지 않는다 — 배포 검증(§9.5)이 이 동작에 의존한다."""

    async def _fail() -> bool:
        raise ConnectionError("connection refused")

    monkeypatch.setattr("vinyl_api.main.ping", _fail)

    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unavailable"
