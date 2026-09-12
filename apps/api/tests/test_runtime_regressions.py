"""Boundary failures must be rejected before SQL or a success response."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from orot_api.deps import SessionDep
from orot_api.pagination import InvalidCursorError, decode_cursor, encode_cursor
from orot_api.schemas.release import ReleaseIn, ReleaseLinkIn, ReleaseUpdate


@pytest.mark.parametrize("payload", [{"title": None}, {"title": "  "}, {"is_limited": None}])
def test_patch_rejects_values_that_violate_not_null(payload):
    with pytest.raises(ValidationError):
        ReleaseUpdate.model_validate(payload)


def test_omitted_patch_fields_remain_omitted():
    assert ReleaseUpdate().model_dump(exclude_unset=True) == {}


def test_blank_create_title_is_rejected():
    with pytest.raises(ValidationError):
        ReleaseIn(title=" \t ")


@pytest.mark.parametrize("price", ["1000000000000", "-1", "0.1", "Infinity"])
def test_prices_fit_the_database(price):
    with pytest.raises(ValidationError):
        ReleaseLinkIn(shop_name="shop", url="https://example.com", price_krw=price)


@pytest.mark.parametrize("url", ["https:", "http://", "https://example.com/\nscript"])
def test_invalid_purchase_url_is_rejected(url):
    with pytest.raises(ValidationError):
        ReleaseLinkIn(shop_name="shop", url=url)


@pytest.mark.parametrize(
    "cursor",
    [
        encode_cursor(datetime(2026, 9, 10), 1),
        encode_cursor(None, 2**63),
        encode_cursor(None, -1),
        "x" * 257,
    ],
)
def test_bad_cursor_never_reaches_asyncpg(cursor):
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor)


def test_commit_failure_cannot_return_success(monkeypatch):
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.commit.side_effect = RuntimeError("commit failed")
    monkeypatch.setattr("orot_api.deps.get_session_factory", lambda: lambda: session)
    app = FastAPI()

    @app.post("/write")
    async def write(db: SessionDep):
        return {"saved": True}

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/write")
    assert response.status_code == 500
    session.rollback.assert_awaited_once()
