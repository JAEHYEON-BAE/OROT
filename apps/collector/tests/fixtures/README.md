# 어댑터 테스트 fixture

**모두 2026-08-20 수집.** 블루프린트 §3.4를 준수하여 0.5 req/s 이하로 요청했습니다.

> ⚠️ CLAUDE.md §2 규칙 2: **테스트에서 실시간 네트워크 요청 금지.**
> fixture가 없으면 **중단하고 질문할 것.** 조용히 사이트를 긁어서 생성하지 않습니다.
>
> 파일은 응답 원문 그대로입니다. **가공·축약하지 마십시오.**
> 셀렉터가 깨지는 상황을 재현하는 것이 fixture의 존재 이유입니다.

수집 근거와 셀렉터 해설: [`docs/adapters/gimbab.md`](../../../../docs/adapters/gimbab.md),
[`docs/adapters/secondtrack.md`](../../../../docs/adapters/secondtrack.md)

---

## gimbab — `https://gimbabrecords.com`

| 파일 | 원본 URL | `stock_number` | `is_soldout_icon` | 예약 | 가격 |
|---|---|---|---|---|---|
| `detail_in_stock_32359.html` | `/product/detail.html?product_no=32359&cate_no=52` | `4` | `F` | 아니오 | 52,000 |
| `detail_sold_out_31938.html` | `/product/detail.html?product_no=31938&cate_no=1` | `0` | `T` | 아니오 | 56,500 |
| `detail_preorder_32562.html` | `/product/detail.html?product_no=32562&cate_no=42` | `10` | `F` | **예** | 74,300 |
| `detail_preorder_sold_out_32584.html` | `/product/detail.html?product_no=32584&cate_no=42` | `0` | `T` | **예** | 58,500 |
| `list_preorder_cate42.html` | `/product/list.html?cate_no=42` | 상품 12건 | | | |
| `list_vinyl_korean_cate52_p1.html` | `/product/list.html?cate_no=52` | 상품 12건 | | | |
| `list_back_in_stock.html` | `/product/back-in-stock.html` | 상품 200건 | | | |

## secondtrack — `https://secondtrack.kr`

| 파일 | 원본 URL | `is_soldout` | 예약 | 가격 |
|---|---|---|---|---|
| `detail_in_stock_609.html` | `/shop-all/?idx=609` | `false` | 아니오 | 50,000 |
| `detail_sold_out_595.html` | `/shop-all/?idx=595` | `true` | 아니오 | 50,000 |
| `detail_preorder_599.html` | `/shop-all/?idx=599` | `false` | **예** | 57,000 |
| `detail_preorder_sold_out_593.html` | `/shop-all/?idx=593` | `true` | **예** | 50,000 |
| `list_preorder.html` | `/preorder` | 고유 7건 (**HTML상 14회 렌더링**) | | |
| `list_shop_all_p1.html` | `/shop-all/?&page=1&sort=recent` | 고유 12건 | | |

---

## 골든 테스트에서 반드시 다룰 것

1. **`*_preorder_sold_out_*.html` 2건** — 예약 ∧ 품절.
   **예약(PREORDER) 처리는 보류 상태입니다** ([ADR-0001](../../../../docs/adr/0001-preorder-open-detection.md) — Deferred).
   당분간 이 2건은 **`SOLD_OUT` 으로 파싱**하고, 제목의 예약 마커는 `title_raw` 에 원문 그대로 보존합니다.
   예약 여부를 판정에 쓰지 않습니다. T-023 착수 전 재검토합니다.
2. **gimbab 목록 품절 판정** — `.soldout` 클래스는 서버 HTML에 **존재하지 않습니다**(클라이언트 jQuery가 부여).
   `img.icon_img[alt="품절"]` 을 쓸 것.
3. **gimbab 상세 `div.soldout`** — 재고와 무관하게 **4개 fixture 전부에 존재**합니다.
   존재 여부로 판정하는 테스트는 반드시 실패해야 합니다.
4. **gimbab JSON-LD `image`** — `https:https://...` 이중 스킴 버그. `og:image` 를 쓸 것.
5. **gimbab 가격** — JSON-LD `offers.price`(표시가)와 `_iPrdtPriceOrg`(공급가, 약 10% 낮음) 혼동 금지.
6. **secondtrack 가격** — 본문 `KRW` 패턴 두 번째 값은 **배송비**입니다. `span.real_price` 로 특정할 것.
7. **secondtrack 목록 중복** — `idx` 기준 dedupe 없이 세면 정확히 2배가 나옵니다.
