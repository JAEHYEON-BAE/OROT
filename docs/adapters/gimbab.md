# 김밥레코즈 (`gimbab`) 소스 조사 기록

- **조사일**: 2026-08-20
- **관련 태스크**: T-006
- **도메인**: `https://gimbabrecords.com`
- **플랫폼**: **Cafe24** (응답 헤더의 `x-hurl`, `EC-SDE-FLAG`, `hanpda.com` 프록시, `server: openresty`로 확인)
- **JS 렌더링 필요 여부**: **불필요.** 목록·상세 모두 완전 서버 렌더링
- **구조화 데이터**: 상세 페이지에 JSON-LD `Product` 1건 존재 (단, `availability` 없음). OpenGraph 있음

> `source_id` 는 **`gimbab`** 으로 확정되었습니다 (2026-08-20). 도메인 `gimbabrecords.com` 표기와 일치시킨 것입니다.
> 프로젝트 전역(블루프린트 §3.2·§6·§10, CLAUDE.md, fixture 경로)에 반영 완료.

---

## 1. robots.txt (전문)

`https://gimbabrecords.com/robots.txt` — 2026-08-20 수집

```
User-agent: *
Disallow: /admin
Disallow: /api
Allow: /
```

**판단**: 상품 목록(`/product/list.html`)과 상세(`/product/detail.html`)는 모두 허용 경로입니다.
`/api` 가 금지되어 있으므로 **Cafe24 프론트엔드 API 호출은 금지**이며, HTML 파싱만 허용됩니다.

---

## 2. 이용약관 검토

출처: `https://gimbabrecords.com/member/mall_agreement.html` (공정거래위원회 표준 전자상거래 약관 기반)

**자동 수집을 직접 금지하는 조항은 없습니다.** 관련되는 유일한 조항은 다음입니다.

> **제22조(저작권의 귀속 및 이용제한)**
> ② 이용자는 "몰"을 이용함으로써 얻은 정보 중 "몰"에게 지적재산권이 귀속된 정보를 "몰"의 사전 승낙 없이
> 복제, 송신, 출판, 배포, 방송 기타 방법에 의하여 **영리목적으로 이용**하거나 제3자에게 이용하게 하여서는 안됩니다.

**해석 및 대응**:

| 쟁점 | 판단 |
|---|---|
| 금지 범위 | "몰에게 지적재산권이 귀속된 정보"에 한정. 가격·재고·상품명 같은 **사실 정보는 저작물이 아님** |
| 명백한 저작물 | 상세설명 본문(직접 작성한 소개글), 자체 촬영 이미지 |
| 조건 | 금지는 **영리목적**으로 한정됨 |
| 준수 방법 | 블루프린트 §3.4대로 **메타데이터만 저장**, 상세설명 원문·이미지 미저장, 썸네일은 URL만 보관, 원본 아웃링크 필수 |
| 잔여 위험 | 수익화 시 제22조 ② 해당 소지. 블루프린트 §3.4 각주대로 **비공개 운영 + 운영자 사전 동의**가 안전 경로 |

---

## 3. 목록 페이지 및 페이지네이션

### URL 패턴

```
https://gimbabrecords.com/product/list.html?cate_no=<카테고리번호>&page=<N>
```

- **페이지당 12건**, 페이지 간 상품 중복 없음 (검증: `cate_no=52` page 1/2 교집합 공집합)
- 페이징 블록에 **마지막 페이지 번호가 노출**되므로 총 페이지 수를 1회 요청으로 파악 가능
  (예: `cate_no=52`는 71페이지 ≈ 852건)

### 주요 카테고리 번호

| cate_no | 이름 | 용도 |
|---|---|---|
| **42** | Pre-Order | **`PREORDER_OPEN` 감지 전용. 최우선 폴링 대상** |
| 25 | Vinyl (최상위) | |
| 52 | Vinyl > Korean | |
| 32 | Vinyl > Pop/Rock | |
| 33 | Vinyl > Electronic/Dance | |
| 53 / 54 / 55 | R&B·Soul·Funk / Hip Hop / Jazz·Blues | |
| 56 / 57 / 58 | Classical·Crossover / Reggae / Soundtracks | |
| 59 / 60 / 61 / 62 | French / Brazilian / Latin / European·African·Asian | |
| 63 / 93 / 96 / 101 | Holiday / Japanese / ESSENTIAL / Library | |
| 24 | CD (최상위) | 바이닐 외 — 수집 대상에서 제외 판단 필요 |
| 43 | Clearance | |

전체 카테고리 목록은 임의 페이지 HTML의 `<option value="<cate_no>">` 에서 추출할 수 있습니다.

### 특수 목록 페이지

```
https://gimbabrecords.com/product/back-in-stock.html
```

**재입고 상품 200건을 페이지네이션 없이 한 응답에 반환합니다.** `RESTOCK` 이벤트 보강에 유용합니다.

---

## 4. ⚠️ sitemap.xml 을 사용하지 말 것

`https://gimbabrecords.com/sitemap.xml` 은 **Cafe24 데모 스토어 기본값이 그대로 방치**되어 있습니다.

```xml
<loc>https://ecudemo199138.cafe24.com/product/nylon-backpack/12/</loc>
<loc>https://ecudemo199138.cafe24.com/product/boyfriend-regular-jeans/13/</loc>
```

김밥레코즈 상품이 **단 한 건도 없습니다.** 도메인조차 다릅니다.
URL 발견 경로는 **카테고리 목록 크롤이 유일**합니다.

---

## 5. 상세 페이지 필드 셀렉터 (8개 필드)

상세 URL: `https://gimbabrecords.com/product/detail.html?product_no=<ID>&cate_no=<N>`
SEO 형식(`/product/<슬러그>/<ID>/category/<N>/display/1/`)도 동일 페이지를 반환합니다.

`source_item_id` = `product_no` (URL 쿼리 또는 SEO 경로에서 추출)

| # | 필드 | 획득 방법 | 신뢰도 | 비고 |
|---|---|---|---|---|
| 1 | `title_raw` | JSON-LD `Product.name` → `meta[property="og:title"]` → `<title>` | 높음 | `<title>` 사용 시 ` - 김밥레코즈` 접미사 제거 필요 |
| 2 | `artist_raw` | **구조적 필드 없음.** `title_raw`를 **첫 번째** ` / ` 기준 분리 | 중 | 제목에 ` / `가 2회 이상 등장 가능 (`전인권 / 어찌 사랑 너 뿐이랴 / 맴도는 얼굴`) → 첫 구분자만 사용 |
| 3 | `label_raw` | **없음** | — | 상세설명 본문에만 등장. §3.4에 따라 본문 저장 금지 → 항상 `None` |
| 4 | `price_krw` | `#span_product_price_text` (`"52,000원"`) → JSON-LD `offers.price` | 높음 | **아래 가격 함정 참조** |
| 5 | `stock_status` | 인라인 JS 변수 (아래 §6) | 높음 | |
| 6 | `format_raw` | **구조적 필드 없음.** 제목 괄호 내부에서 추출 | 중 | `(180g Solid White Vinyl, 45RPM)`, `(Vinyl, 2LP)`, `(10" Vinyl)` |
| 7 | `release_date_raw` | **없음** | — | 예약상품 제목의 날짜는 **배송예정일이지 발매일이 아님**. 혼동 금지 → `None` |
| 8 | `thumbnail_url` | `meta[property="og:image"]` | 높음 | **JSON-LD `image` 사용 금지** — 아래 버그 참조 |

### JSON-LD 예시 (product_no=32562)

```json
{"@context":"https://schema.org","@type":"Product",
 "name":"나플라 Nafla / instinct (Grey Marbled Vinyl, 2LP) *예약상품 (10월 1일 이후 배송 예정)",
 "image":["https:https://cafe24img.poxo.com/gimbabrecords/web/product/big/202608/6127....jpg"],
 "description":"","brand":{"@type":"Brand","name":"김밥레코즈"},
 "offers":{"@type":"Offer","url":"https://gimbabrecords.com/product/.../32562/",
           "priceCurrency":"KRW","price":74300}}
```

> 🐞 **JSON-LD `image` 이중 스킴 버그**: 값이 `https:https://...` 로 나옵니다(Cafe24 템플릿 결함).
> 파싱하면 잘못된 URL이 됩니다. `og:image`를 사용하십시오.

> ℹ️ **`availability` 없음**: JSON-LD에 재고 정보가 없습니다. 구조화 데이터만으로는 재고를 알 수 없습니다.

### 💰 가격 함정 — 10% 오차 주의

동일 상품(32562)에서 세 값이 관측됩니다.

| 출처 | 값 | 의미 |
|---|---|---|
| JSON-LD `offers.price` / `meta[product:price:amount]` | `74300` | **표시가(VAT 포함) — 이 값을 사용** |
| 인라인 `var _iPrdtPriceOrg` | `67545` | 공급가(VAT 제외) |
| 인라인 `var _iPrdtPriceTax` | `6755` | 부가세 |

`price_krw`는 **표시가**를 저장합니다. `_iPrdtPriceOrg`를 쓰면 약 10% 낮게 기록됩니다.
`price_krw`는 `NUMERIC(12,0)`이므로 `Decimal`로만 다루고 float를 개입시키지 않습니다.

---

## 6. 재고 상태 판정 — 함정 2개

### ✅ 권장: 상세 페이지 인라인 JS 변수

```js
var stock_number = '10';
var is_soldout_icon = 'F';
var single_option_stock_data = '{"use_stock":true,"use_soldout":"T","stock_number":10,"is_reserve_stat":"N"}';
```

fixture 4건 교차 검증 결과 `is_soldout_icon`은 `stock_number == 0` 과 **완전히 일치**했습니다.

| fixture | product_no | `stock_number` | `is_soldout_icon` | 제목 예약 마커 | 판정 |
|---|---|---|---|---|---|
| `detail_in_stock_32359.html` | 32359 | 4 | `F` | 없음 | `IN_STOCK` |
| `detail_sold_out_31938.html` | 31938 | 0 | `T` | 없음 | `SOLD_OUT` |
| `detail_preorder_32562.html` | 32562 | 10 | `F` | `*예약상품 (10월 1일 이후 배송 예정)` | `PREORDER` |
| `detail_preorder_sold_out_32584.html` | 32584 | 0 | `T` | `(예약 상품 - 9월초 배송)` | `PREORDER` ∧ `SOLD_OUT` ← **단일 enum으로 표현 불가** |

### ❌ 함정 A — 상세 페이지의 `.soldout` 은 재고와 무관

재고 10개인 상품에서도 아래 마크업이 **항상** 존재합니다.

```html
<div class=" soldout ">
  <button type="button" class="btnDis gFull sizeL displaynone">SOLD OUT</button>
</div>
```

`.soldout` 또는 `SOLD OUT` 문자열의 **존재 여부로 판정하면 100% 오탐**입니다.
구분되는 것은 `displaynone` 클래스뿐입니다. 인라인 JS 변수를 쓰는 편이 훨씬 안전합니다.

### ❌ 함정 B — 목록 페이지의 `.soldout` 은 서버 HTML에 없음

테마의 jQuery가 **클라이언트에서** 클래스를 부여합니다.

```js
$('.icon_img[alt="품절"]').parent().addClass('soldout');
```

`curl`로 받은 HTML에는 `.soldout`이 존재하지 않으므로 해당 셀렉터는 **영구히 0건**을 반환합니다.
목록에서의 품절 판정은 **`img.icon_img[alt="품절"]` 존재 여부**로 해야 합니다.

### 예약(PREORDER) 판정

Cafe24 네이티브 예약 기능은 **사용하지 않습니다** (`is_reserve_stat` 이 전 fixture에서 `'N'`).
예약 여부는 **`Pre-Order` 카테고리 소속** 또는 **제목의 예약 마커**로만 알 수 있습니다.

관측된 마커 표기 3종 — 공백과 형식이 제각각이므로 정규식은 셋을 모두 흡수해야 합니다.

```
*예약상품 (10월 1일 이후 배송 예정)
*예약 상품 (8월 21일 이후 배송)
(예약 상품 - 9월초 배송)
```

제안 패턴: `\*?\s*\(?\s*예약\s?상품` (대소문자·공백 변형 허용)

> 배송예정일 표기도 `10월 1일 이후`, `9월초` 처럼 비정형입니다. 파싱하더라도 `extra`에 보관하고
> `release_date_raw`로 오인하지 않습니다.

---

## 7. 목록 페이지 마크업

각 상품은 안정적인 컨테이너를 가집니다.

```html
<li id="anchorBoxId_32562" class="xans-record-">
  <div class="prdList__item">
    <div class="thumbnail"><a href="/product/<슬러그>/32562/category/42/display/1/"><img src="..." alt="<상품명>"></a></div>
    <div class="description">
      <div class="name"><a href="..."><span style="...">나플라 Nafla / instinct (...) *예약상품 (...)</span></a></div>
      <ul class="xans-element- xans-product xans-product-listitem spec">
        <li><span style="...">74,300원</span></li>
      </ul>
    </div>
  </div>
</li>
```

| 대상 | 셀렉터 |
|---|---|
| 상품 컨테이너 | `li[id^="anchorBoxId_"]` — id 접미사가 `product_no` |
| 상세 URL | `.description .name a[href]` |
| 상품명 | `.description .name a span` |
| 가격 | `.spec li span` (첫 번째) |
| 품절 여부 | `img.icon_img[alt="품절"]` 존재 여부 |

> ⚠️ 테마 jQuery가 `.name span` 텍스트에서 카테고리 접두어를 **클라이언트에서 제거**합니다
> (`skipTitles` 배열). 서버 HTML 값이 원본이므로 `title_raw`로는 서버 값을 그대로 씁니다.

---

## 8. 수집 계획

| 항목 | 값 |
|---|---|
| `requires_javascript` | `False` |
| `crawl_interval_seconds` (일반 카테고리) | `1800` (30분) |
| `crawl_interval_seconds` (Pre-Order `cate_no=42`) | **`300` (5분)** — 사유는 [ADR-0001](../adr/0001-preorder-open-detection.md) |
| 요청 속도 | 0.5 req/s 이하, 동시 연결 2 이하 (블루프린트 §3.4) |
| User-Agent | `VinylRadar/1.0 (+https://<도메인>/about; contact@<도메인>)` |
| 조건부 요청 | 응답에 `Last-Modified` 존재 → `If-Modified-Since` 사용 가능. `ETag`는 미관측 |

> 응답 헤더에 `cache-control: no-store, no-cache` 가 있으나 `x-cache: HIT` / `x-ttl: 300` 으로
> 엣지 캐시가 300초 동작합니다. **5분보다 짧은 폴링은 캐시된 동일 응답을 받을 뿐이므로 무의미합니다.**

---

## 9. 저장한 fixture

`apps/collector/tests/fixtures/gimbab/` — 전부 2026-08-20 수집

| 파일 | 내용 |
|---|---|
| `detail_in_stock_32359.html` | 재고 있음 (stock 4) |
| `detail_sold_out_31938.html` | 품절 (stock 0) |
| `detail_preorder_32562.html` | 예약판매 (stock 10) |
| `detail_preorder_sold_out_32584.html` | 예약판매 + 품절 (엣지 케이스) |
| `list_preorder_cate42.html` | Pre-Order 목록 12건 |
| `list_vinyl_korean_cate52_p1.html` | 일반 카테고리 목록 12건 |
| `list_back_in_stock.html` | 재입고 목록 200건 |

---

## 9-1. 구현 상태 (T-007 완료)

어댑터: `packages/core/src/vinyl_core/adapters/gimbab.py`
골든 테스트: `packages/core/tests/test_adapter_gimbab.py` (29건)

수집 카테고리는 `cate_no` **25(Vinyl) / 42(Pre-Order) / 43(Clearance)** 로 확정했습니다.
CD 계열(24)은 서비스 범위(바이닐) 밖이라 제외합니다.

### ⚡ 목록 페이지에서 직접 수집합니다 ([ADR-0004](../adr/0004-list-page-collection.md))

**상세 페이지를 받지 않습니다.** 목록이 `RawItem` 의 모든 필드를 담고 있어 받을 이유가 없습니다.

| | 요청 수 | 소요 시간 |
|---|---|---|
| 상세 전량 (약 9,072건) | 9,072 | 약 5시간 |
| **목록만 (756페이지)** | **756** | **약 25분** |

목록 기반 셀렉터:

| 필드 | 셀렉터 |
|---|---|
| `source_item_id` | `li[id^="anchorBoxId_"]` 의 id 접미사 |
| `url` | `.description .name a[href]` |
| `title_raw` | `.description .name a span` |
| `price_krw` | `.spec li span` |
| `stock_status` | `img.icon_img[alt="품절"]` 유무 |
| `thumbnail_url` | `.thumbnail img[src]` |

> **조건부 요청은 이 사이트에서 무의미합니다.** `ETag` 가 없고 `Last-Modified` 는
> 응답 생성 시각이 찍혀, `If-Modified-Since` 를 붙여도 200 에 전체 본문을 돌려줍니다 (실측).
>
> **`content_hash` 는 목록에서만 안정적입니다.** 상세 페이지에는
> `var qrcode_class = 'EC_Qrcode...'` 가 요청마다 난수로 들어가 해시가 매번 바뀝니다.
> 상세 기반을 유지했다면 §3.3 의 해시 스킵이 영영 동작하지 않았을 것입니다.

`parse_detail()` 은 지웠지 않고 **파서 카나리(T-018)용으로 남겨** 두었습니다 —
하루 1건을 받아 JSON-LD 와 목록 파싱 결과를 대조해 셀렉터 파손을 잡습니다.

> 예약 상품은 **재고만으로 판정**합니다 (ADR-0001 보류).
> `*예약상품` 표기는 `title_raw` 에 원문 그대로 남고 `stock_status` 에는 영향을 주지 않습니다.

---

## 10. 미해결 사항

1. CD 카테고리(`cate_no=24` 계열) 수집 여부 — 서비스 범위가 "바이닐"이므로 제외가 자연스러우나 블루프린트에 명시 없음
2. `ETag` 미관측 → `content_hash` 기반 스킵(T-017)에 더 의존하게 됨
3. 블루프린트 §3.4의 "사전 고지" 항목: 운영자에게 목적 설명 메일 미발송
