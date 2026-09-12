"""김밥레코즈 어댑터 골든 테스트 (T-007).

**저장된 fixture 만 읽는다. 실시간 네트워크 요청이 없다** (CLAUDE.md §2 규칙 2).
fixture 출처와 기대값: `apps/collector/tests/fixtures/README.md`
"""

from decimal import Decimal
from pathlib import Path

import pytest

from orot_core.adapters import StockStatus
from orot_core.adapters.gimbab import VINYL_CATEGORY_IDS, GimbabAdapter

FIXTURES = Path(__file__).resolve().parents[3] / "apps/collector/tests/fixtures/gimbab"


def read_fixture(name: str) -> str:
    path = FIXTURES / name
    if not path.exists():  # pragma: no cover
        pytest.fail(f"fixture 가 없습니다: {path}. 사이트를 다시 긁지 말고 먼저 확인하십시오.")
    return path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture
def adapter() -> GimbabAdapter:
    return GimbabAdapter()


# ─── 인수 조건: fixture 전건이 RawItem 으로 파싱되고 값이 일치한다 ───

# (fixture, product_no, 재고, 가격, 아티스트, 제목 앞부분)
GOLDEN = [
    (
        "detail_in_stock_32359.html",
        "32359",
        StockStatus.IN_STOCK,
        Decimal("52000"),
        "1415",
        "1415 / DEAR : X (180g Solid White Vinyl, 45RPM)",
    ),
    (
        "detail_sold_out_31938.html",
        "31938",
        StockStatus.SOLD_OUT,
        Decimal("56500"),
        "Tortoise",
        "Tortoise / TNT (Clear w/ White Vinyl, 2LP, Indi-Exclusive)",
    ),
    (
        "detail_preorder_32562.html",
        "32562",
        StockStatus.IN_STOCK,
        Decimal("74300"),
        "나플라 Nafla",
        "나플라 Nafla / instinct (Grey Marbled Vinyl, 2LP) *예약상품",
    ),
    (
        "detail_preorder_sold_out_32584.html",
        "32584",
        StockStatus.SOLD_OUT,
        Decimal("58500"),
        "Phoebe Bridgers",
        "Phoebe Bridgers / Lost Weekend",
    ),
]


@pytest.mark.parametrize(
    ("fixture", "product_no", "stock", "price", "artist", "title_prefix"),
    GOLDEN,
    ids=[g[0] for g in GOLDEN],
)
async def test_parse_detail_golden(
    adapter: GimbabAdapter,
    fixture: str,
    product_no: str,
    stock: StockStatus,
    price: Decimal,
    artist: str,
    title_prefix: str,
) -> None:
    url = f"https://gimbabrecords.com/product/detail.html?product_no={product_no}"
    item = await adapter.parse_detail(url, read_fixture(fixture))

    assert item is not None
    assert item.source_id == "gimbab"
    assert item.source_item_id == product_no
    assert item.stock_status is stock
    assert item.price_krw == price
    assert item.artist_raw == artist
    assert item.title_raw.startswith(title_prefix)
    assert item.thumbnail_url is not None
    assert item.fetched_at.tzinfo is not None


# ─── 예약 취급 (ADR-0001 보류) ───────────────────────────────────


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("detail_preorder_32562.html", StockStatus.IN_STOCK),
        ("detail_preorder_sold_out_32584.html", StockStatus.SOLD_OUT),
    ],
)
async def test_preorder_marker_does_not_affect_stock_status(
    adapter: GimbabAdapter, fixture: str, expected: StockStatus
) -> None:
    """예약 여부는 판정에 쓰지 않는다 — ADR-0001 이 보류 중이다.

    재고만으로 판정하고, 예약 표기는 `title_raw` 에 원문 그대로 남긴다.
    ADR-0001 이 승인되면 이 테스트의 기대값이 바뀐다.
    """
    item = await adapter.parse_detail(
        "https://gimbabrecords.com/product/detail.html?product_no=1", read_fixture(fixture)
    )

    assert item is not None
    assert item.stock_status is expected
    assert item.stock_status is not StockStatus.PREORDER
    assert "예약" in item.title_raw  # 원문은 보존된다


# ─── 조사에서 확인된 함정 ────────────────────────────────────────


@pytest.mark.parametrize("fixture", [g[0] for g in GOLDEN])
def test_soldout_markup_is_present_even_when_in_stock(fixture: str) -> None:
    """상세 페이지의 `div.soldout` 은 재고와 무관하게 항상 있다 (조사 §6 함정 A).

    이 마크업의 존재 여부로 판정하는 구현은 100% 오탐이므로, 그런 구현이 들어오면 막아야 한다.
    """
    assert 'class=" soldout "' in read_fixture(fixture)


def test_list_page_has_no_server_rendered_soldout_class() -> None:
    """목록의 `.soldout` 은 테마 jQuery 가 클라이언트에서 붙인다 (조사 §7 함정 B).

    서버 HTML 에는 없으므로 `img.icon_img[alt="품절"]` 로 판정해야 한다.
    """
    html = read_fixture("list_back_in_stock.html")
    assert 'class="soldout"' not in html
    assert 'alt="품절"' in html


async def test_price_is_display_price_not_supply_price(adapter: GimbabAdapter) -> None:
    """표시가(VAT 포함)를 써야 한다. 공급가 `_iPrdtPriceOrg` 는 약 10% 낮다 (조사 §5)."""
    html = read_fixture("detail_preorder_32562.html")
    item = await adapter.parse_detail(
        "https://gimbabrecords.com/product/detail.html?product_no=32562", html
    )

    assert item is not None
    assert item.price_krw == Decimal("74300")  # 표시가
    assert item.price_krw != Decimal("67545")  # 공급가
    assert "_iPrdtPriceOrg = 67545" in html  # 함정이 실재함을 확인


async def test_thumbnail_avoids_json_ld_double_scheme_bug(adapter: GimbabAdapter) -> None:
    """JSON-LD `image` 는 `https:https://` 로 스킴이 겹친다 (Cafe24 결함, 조사 §5)."""
    html = read_fixture("detail_preorder_32562.html")
    item = await adapter.parse_detail(
        "https://gimbabrecords.com/product/detail.html?product_no=32562", html
    )

    assert item is not None
    assert "https:https://" in html  # 버그가 실재함을 확인
    assert not str(item.thumbnail_url).startswith("https:https")


# ─── 구조적으로 없는 필드 ────────────────────────────────────────


@pytest.mark.parametrize("fixture", [g[0] for g in GOLDEN])
async def test_label_and_release_date_are_none(adapter: GimbabAdapter, fixture: str) -> None:
    """둘 다 구조적 필드가 없다 (조사 §7).

    레이블은 상세설명 본문에만 있는데 §3.4 가 본문 저장을 금지한다.
    예약상품 제목의 날짜는 **배송예정일이지 발매일이 아니다** — 넣으면 안 된다.
    """
    item = await adapter.parse_detail(
        "https://gimbabrecords.com/product/detail.html?product_no=1", read_fixture(fixture)
    )

    assert item is not None
    assert item.label_raw is None
    assert item.release_date_raw is None


def test_artist_split_uses_only_the_first_separator() -> None:
    """제목에 ` / ` 가 두 번 이상 나올 수 있다."""
    assert (
        GimbabAdapter._artist("전인권 / 어찌 사랑 너 뿐이랴 / 맴도는 얼굴 (180g Vinyl)") == "전인권"
    )
    assert GimbabAdapter._artist("Tortoise / TNT") == "Tortoise"
    assert GimbabAdapter._artist("구분자가 없는 제목") is None


# ─── 목록 페이지 기반 수집 (ADR-0004) ────────────────────────────


@pytest.mark.parametrize(
    ("fixture", "expected_count"),
    [
        ("list_preorder_cate42.html", 12),
        ("list_vinyl_korean_cate52_p1.html", 12),
        ("list_back_in_stock.html", 200),
    ],
)
async def test_parse_page_extracts_every_product(
    adapter: GimbabAdapter, fixture: str, expected_count: int
) -> None:
    items = await adapter.parse_page(
        "https://gimbabrecords.com/product/list.html?cate_no=42", read_fixture(fixture)
    )

    assert len(items) == expected_count
    assert len({i.source_item_id for i in items}) == expected_count
    assert all(i.source_id == "gimbab" for i in items)
    assert all(i.title_raw for i in items)
    assert all(str(i.url).startswith("https://gimbabrecords.com/product/") for i in items)


async def test_list_parsing_matches_detail_parsing(adapter: GimbabAdapter) -> None:
    """목록 기반 전환의 근거 (ADR-0004 §2-a).

    목록에서 뽑은 값이 상세에서 뽑은 값과 다르면 전환 전제가 무너진다.
    """
    items = await adapter.parse_page(
        "https://gimbabrecords.com/product/list.html?cate_no=42",
        read_fixture("list_preorder_cate42.html"),
    )
    by_id = {i.source_item_id: i for i in items}

    for fixture, product_no in [
        ("detail_preorder_32562.html", "32562"),
        ("detail_preorder_sold_out_32584.html", "32584"),
    ]:
        detail = await adapter.parse_detail(
            f"https://gimbabrecords.com/product/detail.html?product_no={product_no}",
            read_fixture(fixture),
        )
        listed = by_id[product_no]
        assert detail is not None
        assert listed.title_raw == detail.title_raw
        assert listed.price_krw == detail.price_krw
        assert listed.stock_status is detail.stock_status
        assert listed.artist_raw == detail.artist_raw
        assert listed.format_raw == detail.format_raw


async def test_list_stock_status_uses_icon_not_class(adapter: GimbabAdapter) -> None:
    """목록의 `.soldout` 은 서버 HTML 에 없다 (조사 §7 함정 B).

    `img.icon_img[alt="품절"]` 로 판정해야 하며, 실제로 품절이 섞여 나와야 한다.
    """
    html = read_fixture("list_back_in_stock.html")
    assert 'class="soldout"' not in html  # 함정이 실재함

    items = await adapter.parse_page("https://gimbabrecords.com/product/back-in-stock.html", html)
    sold_out = [i for i in items if i.stock_status is StockStatus.SOLD_OUT]

    assert len(sold_out) == 21  # fixture 실측값
    assert len(items) - len(sold_out) == 179


async def test_parse_page_on_a_page_without_products_returns_empty(
    adapter: GimbabAdapter,
) -> None:
    assert (
        await adapter.parse_page("https://gimbabrecords.com/product/list.html", "<html></html>")
        == []
    )


def test_list_url_pattern() -> None:
    assert (
        GimbabAdapter.list_url(42, 2)
        == "https://gimbabrecords.com/product/list.html?cate_no=42&page=2"
    )


def test_cd_categories_are_not_crawled() -> None:
    """서비스 범위는 바이닐이다. CD 최상위(24)는 대상이 아니다."""
    assert 24 not in VINYL_CATEGORY_IDS
    assert 42 in VINYL_CATEGORY_IDS  # Pre-Order 는 포함


# ─── 실패 처리 ──────────────────────────────────────────────────


async def test_unparseable_html_returns_none_and_does_not_raise(adapter: GimbabAdapter) -> None:
    """예외를 삼키지 않되 파이프라인을 멈추지도 않는다 (CLAUDE.md §2 규칙 5)."""
    item = await adapter.parse_detail(
        "https://gimbabrecords.com/product/detail.html?product_no=1", "<html></html>"
    )
    assert item is None


async def test_discover_without_fetcher_fails_loudly(adapter: GimbabAdapter) -> None:
    """주입을 빠뜨리면 조용히 0건을 수집하는 대신 즉시 실패해야 한다."""
    with pytest.raises(RuntimeError, match="PageFetcher"):
        async for _ in adapter.discover():
            pass


async def test_discover_yields_list_urls_not_detail_urls() -> None:
    """ADR-0004: `discover()` 는 목록 페이지 URL 을 내보낸다.

    상세 URL 을 내보내면 요청 수가 12배가 된다.
    """
    first_pages = {GimbabAdapter.list_url(cid, 1) for cid in VINYL_CATEGORY_IDS}

    class StubFetcher:
        def __init__(self) -> None:
            self.requested: list[str] = []

        async def fetch_text(self, url: str) -> str | None:
            self.requested.append(url)
            if url in first_pages:
                return read_fixture("list_preorder_cate42.html")
            return "<html></html>"

    fetcher = StubFetcher()
    found = [url async for url in GimbabAdapter(fetcher).discover()]

    assert found == sorted(first_pages, key=lambda u: found.index(u) if u in found else 0)
    assert all("list.html" in url for url in found)
    assert not any("detail.html" in url for url in found)
    # 카테고리마다 1페이지(내용 있음) + 2페이지(빈 페이지)까지만 요청한다.
    assert len(fetcher.requested) == 2 * len(VINYL_CATEGORY_IDS)


async def test_long_titles_are_stored_in_full(adapter: GimbabAdapter) -> None:
    """제목을 어디서도 자르지 않는다.

    잘리는 뒷부분에 예약 표기(`*예약상품 (10월 1일 이후 배송 예정)`)와 포맷 힌트가 들어 있어,
    잘리면 정규화(T-008)와 이벤트 감지가 함께 망가진다.
    한때 dry-run CLI 가 표시용으로 56자에서 잘랐으나 **저장 값은 온전했다** — 그 전제를 고정한다.
    """
    items = await adapter.parse_page(
        "https://gimbabrecords.com/product/list.html?cate_no=42",
        read_fixture("list_preorder_cate42.html"),
    )

    by_id = {i.source_item_id: i for i in items}
    nafla = by_id["32562"]
    assert nafla.title_raw == (
        "나플라 Nafla / instinct (Grey Marbled Vinyl, 2LP) *예약상품 (10월 1일 이후 배송 예정)"
    )
    assert nafla.title_raw.endswith("배송 예정)")  # 끝까지 남아 있다

    # 이 페이지에는 100자를 넘는 제목이 실재한다 — 어떤 상한에도 걸리면 안 된다.
    assert max(len(i.title_raw) for i in items) > 100


def test_raw_item_has_no_length_limit_on_text_fields() -> None:
    """`RawItem` 이 조용히 자르지 않는지 확인한다.

    Pydantic 에 `max_length` 가 붙으면 초과분이 오류가 되거나 잘린다.
    DB 쪽은 전부 TEXT 라 제한이 없다.
    """
    from orot_core.adapters.base import RawItem

    long_title = "가" * 5000
    item = RawItem(
        source_id="gimbab",
        source_item_id="1",
        url="https://gimbabrecords.com/product/detail.html?product_no=1",
        title_raw=long_title,
        stock_status=StockStatus.IN_STOCK,
    )
    assert item.title_raw == long_title
    assert len(item.title_raw) == 5000
