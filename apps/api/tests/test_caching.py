"""ETags include actual model fields and respect JSON serialization rules."""

import hashlib
from datetime import UTC, datetime

from fastapi import Response
from pydantic import BaseModel, Field, field_serializer

from orot_api.caching import CACHE_CONTROL, set_cache_headers


class ReleasePayload(BaseModel):
    title: str
    at: datetime
    private_note: str = Field(default="private", exclude=True)


class PricePayload(BaseModel):
    price: int

    @field_serializer("price")
    def serialize_price(self, value: int) -> str:
        return f"{value}원"


def etag(payload: BaseModel | list[BaseModel]) -> str:
    response = Response()
    set_cache_headers(response, payload)
    assert response.headers["Cache-Control"] == CACHE_CONTROL
    return response.headers["ETag"]


def test_empty_list_has_stable_etag() -> None:
    expected = hashlib.sha256(b"[]").hexdigest()[:32]
    assert etag([]) == f'"{expected}"'


def test_single_and_list_match_existing_json_representation() -> None:
    release = ReleasePayload(title="새 음반", at=datetime(2026, 9, 12, tzinfo=UTC))
    cases: list[tuple[BaseModel | list[BaseModel], str]] = [
        (release, release.model_dump_json()),
        ([release], "[" + release.model_dump_json() + "]"),
    ]
    for payload, body in cases:
        expected = hashlib.sha256(body.encode()).hexdigest()[:32]
        assert etag(payload) == f'"{expected}"'
    assert etag(release) == etag(release.model_copy(update={"private_note": "changed"}))


def test_mixed_models_include_later_fields_and_custom_serializers() -> None:
    release = ReleasePayload(title="새 음반", at=datetime(2026, 9, 12, tzinfo=UTC))
    price = PricePayload(price=50000)
    body = '[{"title":"새 음반","at":"2026-09-12T00:00:00Z"},{"price":"50000원"}]'
    expected = hashlib.sha256(body.encode()).hexdigest()[:32]
    assert etag([release, price]) == f'"{expected}"'
    assert etag([release, price]) != etag([release, PricePayload(price=60000)])
