# 포크라노스 (`poclanos`) 소스 조사 기록

- **조사일**: 2026-08-20 (초회) / **2026-08-20 재조사** — 초회 결론이 틀려서 정정함
- **관련 태스크**: T-015
- **스토어 도메인**: `https://poclanos.bstage.in` (레이블 사이트 `poclanos.com` 과 **별개**)
- **플랫폼**: **b.stage** (Next.js). 스토어 운영 법인: 마운드미디어 주식회사
- **JS 렌더링 필요 여부**: **불필요** — 상품 상세 페이지는 서버 렌더링됨
- **구조화 데이터**: JSON-LD 없음. **`__NEXT_DATA__` 에 상품 객체가 통째로 들어 있음**

> ⚠️ **초회 조사 정정**: 처음에는 "`curl` 수집 불가, 헤드리스 또는 내부 API 필요"로 결론냈습니다.
> **목록 페이지(`/shop`)만 확인하고 상품 상세 페이지를 확인하지 않은 탓입니다.**
> 목록은 클라이언트 렌더링이 맞지만 **상세는 서버 렌더링**이며, 일반 HTTP 요청으로 전부 얻을 수 있습니다.
> 헤드리스 브라우저도, 내부 API 호출도 필요하지 않습니다 → [ADR-0002](../adr/0002-poclanos-collection-method.md)

---

## 1. robots.txt (전문)

`https://poclanos.bstage.in/robots.txt` — 2026-08-20 수집

```
User-agent: *
Disallow: /assets/
```

`/shop`, `/shop/products/<id>` 모두 허용 경로입니다.

> 레이블 사이트 `poclanos.com` 의 robots.txt 는 별개이며, 그쪽은 상품을 팔지 않으므로 수집 대상이 아닙니다.

---

## 2. 이용약관 검토 — ✅ 확인 완료

**결론: 자동 수집을 금지하는 조항이 없습니다. 수집 가능한 소스입니다.**

| 항목 | 내용 |
|---|---|
| 확인 방법 | **사람이 브라우저로 직접 열람** (2026-08-20) |
| 확인자 | 프로젝트 소유자 |
| 결과 | 자동 수집·크롤링·스크래핑 금지 조항 **없음** |

블루프린트 §3.4 의 메타데이터 한정 저장 원칙은 그대로 적용합니다 —
특히 `description`(약 60KB HTML)은 저장하지 않습니다 (§7).

---

## 3. ⚠️ 목록 페이지는 쓸 수 없다

```
https://poclanos.bstage.in/shop        # 클라이언트 렌더링
https://poclanos.bstage.in/shop/kr     # 동일
```

`__NEXT_DATA__` 의 `pageProps` 에 **상품 데이터가 0건**입니다
(`price` / `stock` / `goods` / `product` 문자열 출현 횟수 전부 0).
`pageProps.shop` 에는 통화·법인 설정만 있고 카테고리 ID 조차 없습니다.
본문 텍스트 노드는 3개(`poclanos`, `Shop`, `Shop`)뿐입니다.

`sitemap.xml` 은 존재하지만 **상품 URL 이 한 건도 없습니다** — `/shop` 과 `/contents/*` 글뿐이고
`lastmod` 도 2023~2024 로 낡았습니다. 레이블 사이트의 `wp-sitemap.xml` 은 404 입니다.

**따라서 상품 URL 발견은 ID 열거로 한다** (§5).

---

## 4. 상품 상세 페이지 — 여기에 전부 있다

```
https://poclanos.bstage.in/shop/products/<product_id>
```

`__NEXT_DATA__` → `props.pageProps.product` 에 구조화된 객체가 들어 있습니다.

```jsonc
{
  "id": 71,
  "name": "Shin Hae Gyeong-In Dreams, In Dreams[LP] (Singned 100 limited (random))",
  "images": ["https://image.static.bstage.in/.../ori.png"],
  "outOfStock": false,
  "saleStatus": "SALE",
  "productType": "PHYSICAL",
  "productItemDetail": {
    "physicalDetail": {
      "representativeOption": {
        "productOptionId": 82,
        "price": { "currencyCode": "KRW", "amount": 52000 },
        "outOfStock": false
      },
      "options": [ /* 동일 구조 */ ]
    }
  },
  "taxIncludedPrice": false,
  "exclusive": false,
  "description": "<figure>...</figure>"   // 약 60KB HTML — 저장 금지 (§3.4)
}
```

**존재하지 않는 ID** 는 `pageProps` 에 `product` 키 자체가 없습니다.
HTTP 상태로는 구분할 수 없습니다 — Next.js 가 **어떤 경로든 200 으로 셸을 반환**하기 때문입니다
(`/shop/kr/goods/1`, `/shop/product/1` 등 아무 경로나 200). **`product` 키 유무로만 판정하십시오.**

---

## 5. 상품 발견 전략 — ID 열거

목록이 없으므로 `product_id` 를 순차 조회합니다. 카탈로그가 작아 비용이 낮습니다.

**관측된 ID 공간** (2026-08-20):

| ID | 결과 |
|---|---|
| 1 | 없음 |
| 70 | `DATE_TICKET` / `OUT_OF_STOCK` |
| 71 | `PHYSICAL` / `SALE` / 52,000원 / LP |
| 72 | `DATE_TICKET` / `OUT_OF_STOCK` |
| 78, 88, 100, 120, 170, 220, 400 | 없음 |

최대 ID 는 **72 초과 78 미만**. 즉 전체 카탈로그가 100건 미만입니다.

**권장 절차:**

1. **최초 백필**: `id = 1..100` 순차 조회. 0.5 req/s 로 약 3분. 1회만 수행
2. **정상 운영**: 알려진 최대 ID + 1 부터 조회하여 **연속 5회 미발견 시 중단**.
   ID 는 단조 증가하므로 주기당 약 5요청이면 충분합니다
3. **기존 상품**: 일반 크롤 주기로 재조회하여 가격·재고 변화를 감지

> ID 열거는 다소 투박하지만 우회 행위가 아닙니다 — 공개된 상품 페이지를 순번대로 요청할 뿐입니다.
> 0.5 req/s 상한을 지키면 대상 사이트 부담은 무시할 만합니다.

---

## 6. ⚠️ 상품 종류가 섞여 있다

`productType` 이 두 가지입니다.

| 값 | 내용 | 수집 대상 |
|---|---|---|
| `PHYSICAL` | 실물 상품 (LP·CD·굿즈) | **예** |
| `DATE_TICKET` | 리스닝 세션 등 공연 티켓 | **아니오 — 반드시 제외** |

관측 표본 3건 중 2건이 `DATE_TICKET` 이었습니다. 필터링하지 않으면 티켓이 바이닐 피드에 섞입니다.

⛔ **결정 (2026-08-20): `productType != "PHYSICAL"` 인 상품은 수집하지 않습니다.**
`discover()` 단계에서 걸러 `RawItem` 자체를 만들지 않습니다.
`PHYSICAL` 중에서도 LP 여부는 상품명(`[LP]` 등)으로 다시 걸러야 하나, 이는 별도 논점입니다.

---

## 7. 필드 셀렉터 (8개 필드)

`source_item_id` = `product.id`

| # | 필드 | 획득 경로 | 신뢰도 |
|---|---|---|---|
| 1 | `title_raw` | `product.name` | 높음 |
| 2 | `artist_raw` | **구조적 필드 없음.** 상품명에서 분리 | **낮음** — 아래 주의 |
| 3 | `label_raw` | 사실상 `Poclanos` 고정 (자사 유통) | 중 |
| 4 | `price_krw` | `productItemDetail.physicalDetail.representativeOption.price.amount` | 높음 |
| 5 | `stock_status` | `outOfStock` + `saleStatus` (§8) | 높음 |
| 6 | `format_raw` | 상품명의 `[LP]` / `[CD]` 표기 | 중 |
| 7 | `release_date_raw` | `description` 안의 `Release date 26.08` | 낮음 |
| 8 | `thumbnail_url` | `images[0]` | 높음 |

> ⛔ **아티스트 파싱은 보류하기로 결정했습니다 (2026-08-20).** `artist_raw` 는 **항상 `None`** 으로 둡니다.
>
> 관측된 상품명: `Shin Hae Gyeong-In Dreams, In Dreams[LP] (Singned 100 limited (random))`
> 구분자 `-` 에 공백이 없고, 제목 자체(`In Dreams, In Dreams`)에도 같은 단어가 반복됩니다.
> 김밥의 ` / ` 나 세컨드트랙의 ` - ` 같은 안정적 구분자가 **없습니다.**
> 추측 파싱은 잘못된 병합으로 이어지며, 이는 §4.4 의 정밀도 우선 원칙에 정면으로 어긋납니다.
> 병합은 보류되고(`release_id` NULL) 상품은 `title_raw` 그대로 피드에 남습니다.

> ⚠️ **`description` 은 저장하지 않습니다** (§3.4 — 상세설명 원문 저장 금지). 약 60KB 입니다.
> 발매일 같은 **사실 메타데이터만 추출**하고 본문은 버립니다.

---

## 8. 재고 상태 판정

| `saleStatus` | `outOfStock` | 판정 |
|---|---|---|
| `SALE` | `false` | `IN_STOCK` |
| `OUT_OF_STOCK` | `true` | `SOLD_OUT` |

두 신호가 관측 표본에서 일치했습니다. 다만 **표본이 3건뿐**이라
`SALE`/`OUT_OF_STOCK` 외의 `saleStatus` 값이 더 있을 수 있습니다.
알 수 없는 값은 CLAUDE.md §2 규칙 5 에 따라 **`UNKNOWN` 으로 두고 로그를 남깁니다** — 임의로 추측하지 않습니다.

옵션이 여러 개인 상품은 `options[]` 각각에 `outOfStock` 이 붙습니다.
현재 표본은 단일 옵션이지만, 다옵션 상품이 나오면 판정 규칙을 정해야 합니다 (미해결).

---

## 9. 수집 계획

| 항목 | 값 |
|---|---|
| `requires_javascript` | **`False`** |
| `crawl_interval_seconds` | `1800` (30분) |
| 요청 속도 | 0.5 req/s 이하 |
| 응답 크기 | 상세 1건 약 220KB (`description` 이 대부분) |

---

## 10. fixture

**아직 저장하지 않았습니다.** §2(이용약관) 확인 후 T-015 에서 저장합니다.
최소 3건: `PHYSICAL`+`SALE`, `PHYSICAL`+`OUT_OF_STOCK`, 존재하지 않는 ID(= `product` 키 부재).
`DATE_TICKET` 1건도 필터링 테스트용으로 함께 저장하는 것을 권합니다.

---

## 11. 미해결 사항

1. `saleStatus` 의 전체 값 목록 미확인 (표본 3건) — 미지 값은 `UNKNOWN` + 로그
2. 다옵션 상품의 재고 판정 규칙 미정
3. 카탈로그 중 LP 비중 미확인 — 전체 100건 미만이고 티켓이 섞여 있어 실제 LP 는 소수일 수 있음
4. 아티스트 파싱 — 보류 중. 재개하려면 안정적 구분자를 찾거나 외부 메타데이터(MusicBrainz 등)가 필요

> ✅ 이용약관 확인(§2) 완료로 **T-015/T-016 착수를 막는 선행 조건은 없습니다.**
