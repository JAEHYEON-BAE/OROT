"""구매처 링크 계약 (다중 등록).

한 발매를 여러 판매처에서 살 수 있으므로 링크는 여러 개다.
운영자가 같은 URL 을 실수로 두 번 넣는 것은 흔한 일이라 **오류가 아니라 중복 제거**로 다룬다.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from orot_api.schemas.release import ReleaseIn, ReleaseLinkIn, ReleaseLinkOut


def test_release_accepts_multiple_links() -> None:
    payload = ReleaseIn(
        title="Machine Boy",
        links=[
            ReleaseLinkIn(
                shop_name="김밥레코즈", url="https://a.example", price_krw=Decimal(52000)
            ),
            ReleaseLinkIn(
                shop_name="세컨드트랙", url="https://b.example", price_krw=Decimal(54000)
            ),
            ReleaseLinkIn(shop_name="포크라노스", url="https://c.example"),
        ],
    )
    assert len(payload.links) == 3
    assert payload.links[2].price_krw is None  # 가격은 선택이다


def test_links_default_to_empty() -> None:
    assert ReleaseIn(title="X").links == []


def test_price_is_serialized_as_int_not_scientific_notation() -> None:
    """`NUMERIC(12,0)` 을 그대로 내보내면 Postgres 가 `Decimal('5E+4')` 를 준다.

    그대로 직렬화하면 API 에 `"5E+4"` 가 나가 클라이언트가 깨진다.
    원화에 소수 단위가 없으므로 정수가 정직한 타입이다.
    """
    link = ReleaseLinkOut.model_validate(
        {
            "id": 1,
            "shop_name": "김밥레코즈",
            "url": "https://a.example",
            "price_krw": Decimal("5E+4"),
        }
    )
    assert link.price_krw == 50000
    assert '"price_krw":50000' in link.model_dump_json()


@pytest.mark.parametrize("bad", [Decimal("52000.5"), Decimal("-1")])
def test_link_price_rejects_invalid(bad: Decimal) -> None:
    with pytest.raises(ValidationError):
        ReleaseLinkIn(shop_name="X", url="https://a.example", price_krw=bad)


def test_shop_name_is_required() -> None:
    """소스에 등록되지 않은 판매처도 이름만으로 넣을 수 있어야 한다."""
    link = ReleaseLinkIn(shop_name="동네 레코드샵", url="https://a.example")
    assert link.source_id is None


# ─── 공개 생명주기 (운영자 화면 수정 기능) ────────────────────────


def test_release_update_allows_partial_edit() -> None:
    """폼의 '수정 저장'은 보낸 필드만 바꾼다."""
    from orot_api.schemas.release import ReleaseUpdate

    payload = ReleaseUpdate(title="새 제목")
    changed = payload.model_dump(exclude_unset=True)
    assert changed == {"title": "새 제목"}  # 나머지 필드는 건드리지 않는다


def test_update_rejects_naive_datetime() -> None:
    """수정 경로에도 생성과 같은 타임존 규칙이 걸려야 한다."""
    from datetime import datetime

    from orot_api.schemas.release import ReleaseUpdate

    with pytest.raises(ValidationError, match="타임존"):
        ReleaseUpdate(preorder_opens_at=datetime(2026, 9, 10, 0, 0))
