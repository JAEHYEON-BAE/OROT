"""김밥레코즈 어댑터 (T-007).

조사 근거와 함정 목록: `docs/adapters/gimbab.md`
플랫폼은 Cafe24 이며 목록·상세 모두 서버 렌더링이라 JS 렌더링이 필요 없다.

**목록 페이지에서 직접 수집한다** (ADR-0004). 목록이 `RawItem` 의 모든 필드를 담고 있어
상세를 따로 받을 이유가 없다 — 요청 수가 12분의 1(약 5시간 → 약 25분)로 준다.
상세 파싱(`parse_detail`)은 **파서 카나리(T-018)용으로 남겨 둔다** — 하루 1건을 받아
JSON-LD 와 목록 파싱 결과를 대조해 셀렉터 파손을 잡기 위한 것이다.

**이 파일에서 특히 조심할 것** (조사에서 실제로 확인된 함정):

1. 상세 페이지의 `div.soldout` / `SOLD OUT` 문자열은 **재고와 무관하게 항상 존재**한다.
   존재 여부로 판정하면 100% 오탐이다 → 인라인 JS 변수를 쓴다.
2. 목록 페이지의 `.soldout` 클래스는 테마 jQuery 가 **클라이언트에서** 붙인다.
   서버 HTML 에는 없으므로 `img.icon_img[alt="품절"]` 로 판정한다.
3. JSON-LD 의 `image` 는 `https:https://...` 로 스킴이 겹쳐 있다(Cafe24 템플릿 결함).
   썸네일은 `og:image` 에서 얻는다.
4. 가격은 표시가(JSON-LD `offers.price`)를 쓴다. 인라인 `_iPrdtPriceOrg` 는 공급가라 약 10% 낮다.
"""

import json
import re
from collections.abc import AsyncIterator
from decimal import Decimal, InvalidOperation
from typing import Final
from urllib.parse import parse_qs, urljoin, urlparse

import structlog
from pydantic import HttpUrl, ValidationError
from selectolax.parser import HTMLParser, Node

from vinyl_core.adapters.base import PageFetcher, RawItem, StockStatus
from vinyl_core.adapters.registry import register

log = structlog.get_logger(__name__)

BASE_URL: Final = "https://gimbabrecords.com"

# 수집 대상 카테고리. CD 계열(cate_no=24 등)은 서비스 범위(바이닐) 밖이라 제외한다.
# 카테고리 번호 근거는 docs/adapters/gimbab.md §3.
VINYL_CATEGORY_IDS: Final = (
    25,  # Vinyl (최상위)
    42,  # Pre-Order
    43,  # Clearance
)

# 목록 페이지 한 장에 12건. 방어적 상한 — 무한 루프를 막는다.
MAX_LIST_PAGES: Final = 100

# 상세 페이지 인라인 JS 변수 (조사 §6).
_RE_SOLDOUT_ICON: Final = re.compile(r"var\s+is_soldout_icon\s*=\s*'([A-Z])'")
_RE_STOCK_NUMBER: Final = re.compile(r"var\s+stock_number\s*=\s*'(\d*)'")
_RE_PRODUCT_NO: Final = re.compile(r"/product/[^/]+/(\d+)/")

# 제목 안 괄호 — 포맷 후보. 정규화는 T-008 이 한다.
_RE_FORMAT_HINT: Final = re.compile(
    r"\(([^()]*(?:vinyl|lp|cd|inch|rpm|7\"|10\"|12\")[^()]*)\)", re.I
)

_TITLE_SUFFIX: Final = " - 김밥레코즈"
_ARTIST_SEPARATOR: Final = " / "


@register
class GimbabAdapter:
    """김밥레코즈 (Cafe24)."""

    source_id = "gimbab"
    display_name = "김밥레코즈"
    base_url = BASE_URL
    crawl_interval_seconds = 1800
    requires_javascript = False

    def __init__(self, fetcher: PageFetcher | None = None) -> None:
        # 레지스트리는 인자 없이 인스턴스를 만든다. 실제 수집기는 파이프라인(T-009)이 주입한다.
        self._fetcher = fetcher

    # ─── 발견 ───────────────────────────────────────────────────

    @staticmethod
    def list_url(category_id: int, page: int = 1) -> str:
        """목록 페이지 URL. 조사 §3 의 패턴."""
        return f"{BASE_URL}/product/list.html?cate_no={category_id}&page={page}"

    async def discover(self) -> AsyncIterator[str]:
        """**목록 페이지** URL 을 순회 반환한다 (상세 URL 이 아니다 — ADR-0004).

        빈 목록을 만나면 그 카테고리는 끝난 것으로 보고 다음으로 넘어간다.
        """
        if self._fetcher is None:
            msg = "discover() 를 쓰려면 PageFetcher 를 주입해야 합니다."
            raise RuntimeError(msg)

        for category_id in VINYL_CATEGORY_IDS:
            for page in range(1, MAX_LIST_PAGES + 1):
                url = self.list_url(category_id, page)
                html = await self._fetcher.fetch_text(url)
                if html is None or not self._list_blocks(HTMLParser(html)):
                    break
                yield url

    # ─── 파싱 ───────────────────────────────────────────────────

    @staticmethod
    def _list_blocks(tree: HTMLParser) -> list[Node]:
        """목록 페이지의 상품 블록. id 접미사가 `product_no` 다."""
        return tree.css('li[id^="anchorBoxId_"]')

    async def parse_page(self, url: str, html: str) -> list[RawItem]:
        """목록 페이지에서 상품을 **모두** 뽑는다 (ADR-0004).

        한 건이 깨져도 나머지는 살린다 — 상품 하나 때문에 페이지 12건을 통째로 잃지 않는다.
        """
        tree = HTMLParser(html)
        blocks = self._list_blocks(tree)
        if not blocks:
            log.error("parse_page.no_items", source_id=self.source_id, url=url)
            return []

        items: list[RawItem] = []
        for block in blocks:
            try:
                item = self._parse_list_block(block)
            except Exception:
                log.exception("parse_page.block_failed", source_id=self.source_id, url=url)
                continue
            if item is not None:
                items.append(item)

        if not items:
            log.error("parse_page.all_blocks_failed", source_id=self.source_id, url=url)
        return items

    def _parse_list_block(self, block: Node) -> RawItem | None:
        """목록의 상품 블록 하나를 `RawItem` 으로 만든다."""
        node_id = block.attributes.get("id") or ""
        source_item_id = node_id.removeprefix("anchorBoxId_")
        if not source_item_id.isdigit():
            return None

        link = block.css_first(".description .name a")
        name = block.css_first(".description .name a span")
        if link is None or name is None:
            return None

        href = link.attributes.get("href")
        title_raw = name.text().strip()
        if not href or not title_raw:
            return None

        return RawItem(
            source_id=self.source_id,
            source_item_id=source_item_id,
            url=HttpUrl(urljoin(BASE_URL, href)),
            title_raw=title_raw,
            artist_raw=self._artist(title_raw),
            label_raw=None,  # 구조적 필드 없음 (상세에도 없다)
            price_krw=self._list_price(block),
            stock_status=self._list_stock_status(block),
            format_raw=self._format_hint(title_raw),
            release_date_raw=None,  # 구조적 필드 없음
            thumbnail_url=self._list_thumbnail(block),
            extra={},
        )

    @staticmethod
    def _list_price(block: Node) -> Decimal | None:
        node = block.css_first(".spec li span")
        if node is None:
            return None
        digits = re.sub(r"[^\d]", "", node.text())
        return Decimal(digits) if digits else None

    @staticmethod
    def _list_stock_status(block: Node) -> StockStatus:
        """목록의 품절 판정.

        **`.soldout` 클래스를 쓰면 안 된다** — 테마 jQuery 가 클라이언트에서 붙이므로
        서버 HTML 에는 존재하지 않는다 (조사 §7 함정 B). 아이콘 이미지로 판정한다.

        예약 여부는 판정에 쓰지 않는다 (ADR-0001 보류).
        """
        return (
            StockStatus.SOLD_OUT
            if block.css_first('img.icon_img[alt="품절"]') is not None
            else StockStatus.IN_STOCK
        )

    def _list_thumbnail(self, block: Node) -> HttpUrl | None:
        node = block.css_first(".thumbnail img")
        raw = node.attributes.get("src") if node is not None else None
        if not raw:
            return None
        try:
            return HttpUrl(urljoin(BASE_URL, raw))
        except ValidationError:
            log.warning("parse_page.bad_thumbnail", source_id=self.source_id, value=raw)
            return None

    # ─── 상세 파싱 (파서 카나리 전용 — T-018) ────────────────────

    async def parse_detail(self, url: str, html: str) -> RawItem | None:
        """상세 페이지 1건을 파싱한다. **정상 수집 경로에서는 쓰지 않는다.**

        목록 파싱 결과와 대조해 셀렉터 파손을 잡기 위한 것이다 (ADR-0004 §5).
        상세에는 JSON-LD `Product` 가 있어 목록보다 구조적으로 안정적이다.
        """
        try:
            return self._parse_detail(url, html)
        except Exception:
            log.exception("parse_detail.failed", source_id=self.source_id, url=url)
            return None

    def _parse_detail(self, url: str, html: str) -> RawItem | None:
        tree = HTMLParser(html)

        source_item_id = self._source_item_id(url, html)
        if source_item_id is None:
            log.error("parse_detail.no_product_no", source_id=self.source_id, url=url)
            return None

        product = self._json_ld_product(tree)
        title_raw = self._title(tree, product)
        if not title_raw:
            log.error("parse_detail.no_title", source_id=self.source_id, url=url)
            return None

        stock_status = self._detail_stock_status(html)
        if stock_status is StockStatus.UNKNOWN:
            log.warning("parse_detail.unknown_stock", source_id=self.source_id, url=url)

        return RawItem(
            source_id=self.source_id,
            source_item_id=source_item_id,
            url=HttpUrl(url),
            title_raw=title_raw,
            artist_raw=self._artist(title_raw),
            label_raw=None,
            price_krw=self._detail_price(tree, product),
            stock_status=stock_status,
            format_raw=self._format_hint(title_raw),
            release_date_raw=None,
            thumbnail_url=self._detail_thumbnail(tree, url),
            extra=self._extra(html),
        )

    # ─── 필드별 추출 ─────────────────────────────────────────────

    @staticmethod
    def _source_item_id(url: str, html: str) -> str | None:
        """`product_no`. 쿼리 형식과 SEO 경로 형식을 모두 받는다."""
        query = parse_qs(urlparse(url).query)
        if values := query.get("product_no"):
            return values[0]
        if match := _RE_PRODUCT_NO.search(url):
            return match.group(1)
        # URL 로 못 얻으면 본문의 정규 URL 에서 찾는다.
        if match := _RE_PRODUCT_NO.search(html):
            return match.group(1)
        return None

    @staticmethod
    def _json_ld_product(tree: HTMLParser) -> dict[str, object] | None:
        for node in tree.css('script[type="application/ld+json"]'):
            try:
                data = json.loads(node.text())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                return data
        return None

    @staticmethod
    def _meta(tree: HTMLParser, prop: str) -> str | None:
        node = tree.css_first(f'meta[property="{prop}"]')
        if node is None:
            return None
        content = node.attributes.get("content")
        return content.strip() if content else None

    def _title(self, tree: HTMLParser, product: dict[str, object] | None) -> str | None:
        if product and isinstance(name := product.get("name"), str) and name.strip():
            return name.strip()
        if og_title := self._meta(tree, "og:title"):
            return og_title
        node = tree.css_first("title")
        if node is None:
            return None
        text = node.text().strip()
        return text.removesuffix(_TITLE_SUFFIX).strip() or None

    @staticmethod
    def _artist(title_raw: str) -> str | None:
        """상품명의 **첫** ` / ` 앞부분이 아티스트다.

        제목에 구분자가 두 번 이상 나올 수 있다
        (`전인권 / 어찌 사랑 너 뿐이랴 / 맴도는 얼굴`) — 첫 구분자만 쓴다.
        """
        artist, separator, _ = title_raw.partition(_ARTIST_SEPARATOR)
        if not separator:
            return None
        return artist.strip() or None

    def _detail_price(self, tree: HTMLParser, product: dict[str, object] | None) -> Decimal | None:
        """표시가(VAT 포함)를 쓴다. 인라인 `_iPrdtPriceOrg` 는 공급가라 약 10% 낮다."""
        if product:
            offers = product.get("offers")
            if isinstance(offers, dict):
                raw_price = offers.get("price")
                if isinstance(raw_price, int | float | str):
                    try:
                        return Decimal(str(raw_price))
                    except InvalidOperation:
                        pass

        node = tree.css_first("#span_product_price_text")
        if node is None:
            return None
        digits = re.sub(r"[^\d]", "", node.text())
        return Decimal(digits) if digits else None

    @staticmethod
    def _detail_stock_status(html: str) -> StockStatus:
        """재고 판정.

        `is_soldout_icon` 이 1순위다 — fixture 4건에서 `stock_number == 0` 과 정확히 일치했다.

        **예약 여부는 판정에 쓰지 않는다** (ADR-0001 보류).
        예약 상품이라도 재고가 있으면 `IN_STOCK`, 없으면 `SOLD_OUT` 이며,
        예약 표기는 `title_raw` 에 원문 그대로 남는다.
        """
        if match := _RE_SOLDOUT_ICON.search(html):
            return StockStatus.SOLD_OUT if match.group(1) == "T" else StockStatus.IN_STOCK
        if match := _RE_STOCK_NUMBER.search(html):
            digits = match.group(1)
            if digits:
                return StockStatus.IN_STOCK if int(digits) > 0 else StockStatus.SOLD_OUT
        return StockStatus.UNKNOWN

    @staticmethod
    def _format_hint(title_raw: str) -> str | None:
        """제목 괄호에서 포맷 후보를 뽑는다. 정규화는 T-008 이 한다."""
        match = _RE_FORMAT_HINT.search(title_raw)
        return match.group(1).strip() if match else None

    def _detail_thumbnail(self, tree: HTMLParser, page_url: str) -> HttpUrl | None:
        """`og:image` 를 쓴다. JSON-LD `image` 는 스킴이 겹치는 버그가 있다.

        썸네일이 망가졌다고 상품 전체를 버리지 않는다 — 부가 정보이므로 `None` 으로 두고 넘어간다.
        """
        raw = self._meta(tree, "og:image")
        if not raw:
            return None
        try:
            return HttpUrl(raw)
        except ValidationError:
            log.warning("parse_detail.bad_thumbnail", source_id="gimbab", url=page_url, value=raw)
            return None

    @staticmethod
    def _extra(html: str) -> dict[str, object]:
        """소스 고유 필드. 판정에 쓰지 않되 나중을 위해 관측 사실만 남긴다."""
        extra: dict[str, object] = {}
        if (match := _RE_STOCK_NUMBER.search(html)) and match.group(1):
            extra["stock_number"] = int(match.group(1))
        if match := _RE_SOLDOUT_ICON.search(html):
            extra["is_soldout_icon"] = match.group(1)
        return extra
