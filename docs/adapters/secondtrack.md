# 세컨드트랙 (`secondtrack`) 소스 조사 기록

- **조사일**: 2026-08-20
- **관련 태스크**: T-013
- **도메인**: `https://secondtrack.kr` (⚠️ `secondtrack.co.kr` 은 **DNS 미등록**)
- **플랫폼**: **아임웹(Imweb)** (`IMWEBVSSID` 쿠키, `cdn.imweb.me` 자산으로 확인)
- **JS 렌더링 필요 여부**: **불필요.** 목록·상세 모두 완전 서버 렌더링
- **구조화 데이터**: JSON-LD **없음**. OpenGraph는 `og:url` / `og:image` / `og:title`만 (`og:type`은 `website`로 부정확)

> 겉보기에 SPA처럼 동작하지만 HTML에 데이터가 모두 들어 있습니다.
> 단, **홈(`/`)에는 상품이 없으므로** 홈만 보고 "JS 필요"로 오판하지 않도록 주의합니다.

---

## 1. robots.txt (전문)

`https://secondtrack.kr/robots.txt` — 2026-08-20 수집

```
User-agent: *
Allow: /
Disallow: /site_join
Disallow: /site_join_agree
Disallow: /login
Disallow: /logout.cm
Disallow: /shop_cart
Disallow: /?mode*
Disallow: /admin

Sitemap: https://secondtrack.kr/sitemap.xml
```

**판단**:

- 상품 목록(`/shop-all/`, `/preorder`)과 상세(`/shop-all/?idx=<N>`)는 **모두 허용**
- `Disallow: /?mode*` 는 **루트 경로의 `?mode=` 쿼리**에만 해당합니다. `/shop-all/?...` 은 경로가 달라 무관합니다
- 회원가입·로그인·장바구니는 금지 — 어차피 접근할 이유가 없습니다

---

## 2. 이용약관 검토 — ✅ 확인 완료

**결론: 자동 수집을 금지하는 조항이 없습니다. 수집 가능한 소스입니다.**

| 항목 | 내용 |
|---|---|
| 확인 방법 | **사람이 브라우저로 직접 열람** (2026-08-20) |
| 확인자 | 프로젝트 소유자 |
| 결과 | 자동 수집·크롤링·스크래핑 금지 조항 **없음** |

> **크롤러로 가져오지 않은 이유**: 약관 경로가 `/?mode=policy`, 개인정보처리방침이 `/?mode=privacy` 로
> robots.txt 의 `Disallow: /?mode*` 에 정확히 해당합니다. 블루프린트 §3.4 "robots.txt 준수"가
> 조사 편의보다 우선하므로 자동 수집하지 않았습니다.
> 사람이 브라우저로 여는 것은 크롤링이 아니므로 이 규칙과 무관합니다.
>
> 같은 이유로 **본 문서에 약관 전문을 인용하지 않습니다.** 재확인이 필요하면 브라우저로 여십시오.

`/return-policy` 는 허용 경로이나 교환·반품 정책이라 수집 적법성과 무관합니다.

김밥레코즈와 마찬가지로 블루프린트 §3.4의 **메타데이터 한정 저장 원칙은 그대로 적용**합니다
(상세설명 원문·이미지 미저장, 썸네일은 URL만, 원본 아웃링크 필수).

---

## 3. 목록 페이지 및 페이지네이션

### URL 패턴

```
https://secondtrack.kr/shop-all/?&page=<N>&sort=recent   # 전체 상품
https://secondtrack.kr/preorder                          # 예약판매 전용
https://secondtrack.kr/ready-to-ship                     # 즉시 배송 가능
```

- 서버 렌더링 페이징 (`ul.pagination` 내 `<a href='/shop-all/?&page=2&sort=recent'>`)
- **무한 스크롤 아님** — HTML에 `infinite` / `load_more` 문자열이 있으나 페이징 링크가 실제로 동작합니다
- `sort=recent` 지원 → **신규 상품 감지는 page 1만 보면 됩니다**

### 메뉴 구조

| 경로 | 의미 |
|---|---|
| `/preorder` | **예약판매. `PREORDER_OPEN` 감지 전용. 최우선 폴링 대상** |
| `/ready-to-ship` | 즉시 배송 |
| `/shop-all` | 전체 |
| `/parkhyoshin` | 아티스트 전용 기획 페이지 (상시 존재 여부 불확실) |

---

## 4. ⚠️ 목록 HTML에 상품 카드가 2번 렌더링됨

PC/모바일 레이아웃이 **모두 서버에서 출력**되어 동일 상품이 두 번 나타납니다.
조사 시 고유 `idx` 7건에 `NEW` 배지가 14개 관측되었습니다.

**`idx` 기준 중복 제거가 필수입니다.** 하지 않으면 모든 카운트가 정확히 2배가 됩니다.

---

## 5. 상세 페이지 필드 셀렉터 (8개 필드)

상세 URL: `https://secondtrack.kr/shop-all/?idx=<ID>`
`source_item_id` = `idx`

| # | 필드 | 획득 방법 | 신뢰도 | 비고 |
|---|---|---|---|---|
| 1 | `title_raw` | `h1.view_tit` (텍스트 노드만) → `<title>` | 높음 | `<title>` 사용 시 ` : Secondtrack Korea` 접미사 제거 필요. `h1` 안에 배지 `<div>`가 중첩되므로 텍스트 노드만 취함 |
| 2 | `artist_raw` | **구조적 필드 없음.** `title_raw`를 첫 ` - ` 기준 분리 | 중 | **김밥과 구분자가 다름** (` / ` 아님). 예약 접두어 `[예약판매] ` 를 먼저 제거해야 함 |
| 3 | `label_raw` | **없음** | — | 상세 정보 테이블 자체가 없음 → 항상 `None` |
| 4 | `price_krw` | `span.real_price` (`"50,000 KRW"`) | 높음 | **아래 가격 함정 참조** |
| 5 | `stock_status` | 임베디드 JSON `"is_soldout"` (아래 §6) | 높음 | |
| 6 | `format_raw` | **구조적 필드 없음.** 제목에서 추출 | 낮음 | 표기가 드묾. `(7인치)` 정도만 관측 |
| 7 | `release_date_raw` | **없음** | — | 항상 `None` |
| 8 | `thumbnail_url` | `meta[property="og:image"]` | 높음 | `cdn.imweb.me` 호스트 |

### 💰 가격 함정 — 배송비가 섞여 들어옴

본문에서 `KRW` 패턴을 전부 뽑으면 **상품가 다음에 배송비가 나옵니다**.

```
50,000 KRW   ← 상품가
 3,500 KRW   ← 배송비
 7,000 KRW   ← 배송비(도서산간 등)
```

"마지막 값"이나 "정규식 첫 매치"로 잡지 말고 **`span.real_price` 셀렉터로 특정**해야 합니다.

---

## 6. 재고 상태 판정 — 신호 3개가 모두 일치

김밥과 달리 **함정이 없습니다.** 세 신호가 서버 HTML에서 항상 일관됩니다.

| 신호 | 재고 있음 | 품절 |
|---|---|---|
| 임베디드 JSON | `"is_soldout":false` | `"is_soldout":true` |
| 배지 DOM | (없음) | `<div class='prod_icon sold_out'>SOLDOUT</div>` |
| 구매 버튼 class | `btn buy bg-brand _btn_buy` | `btn buy bg-brand btn-soldout` |

**권장: `"is_soldout"` JSON 값을 1순위로 사용합니다.**

> ⚠️ 버튼 클래스로 판정할 경우 `btn-soldout-before` 라는 별도 클래스가 존재하므로
> 부분 문자열 매칭(`"soldout" in class`)은 의미가 모호해집니다. JSON 필드가 명확합니다.

### fixture 교차 검증

| fixture | idx | `is_soldout` | `prod_icon` | 제목 접두어 | 판정 |
|---|---|---|---|---|---|
| `detail_in_stock_609.html` | 609 | `false` | 없음 | 없음 | `IN_STOCK` |
| `detail_sold_out_595.html` | 595 | `true` | `SOLDOUT` | 없음 | `SOLD_OUT` |
| `detail_preorder_599.html` | 599 | `false` | 없음 | `[예약판매] ` | `PREORDER` |
| `detail_preorder_sold_out_593.html` | 593 | `true` | `SOLDOUT` | `[예약판매] ` | `PREORDER` ∧ `SOLD_OUT` ← **단일 enum으로 표현 불가** |

### 예약(PREORDER) 판정

재고 상태와 **독립된 축**입니다. 판정 근거는 둘뿐입니다.

1. `/preorder` 목록 소속 여부
2. 제목의 **`[예약판매] ` 접두어** — 김밥과 달리 표기가 일관되어 파싱이 쉽습니다

조사 시점 `/preorder` 7건 중 **4건이 이미 `SOLDOUT`** 이었습니다.
한정반이 빠르게 소진된다는 근거이며, 폴링 주기 결정에 반영했습니다 → [ADR-0001](../adr/0001-preorder-open-detection.md)

---

## 7. 수집 계획

| 항목 | 값 |
|---|---|
| `requires_javascript` | `False` |
| `crawl_interval_seconds` (`/shop-all`) | `1800` (30분) |
| `crawl_interval_seconds` (`/preorder`) | **`300` (5분)** |
| 요청 속도 | 0.5 req/s 이하 |
| 조건부 요청 | `ETag` / `Last-Modified` 미관측 → `content_hash` 스킵(T-017)에 의존 |

> 상세 페이지가 건당 **약 360KB**로 김밥(약 80KB)의 4배 이상입니다.
> 전체 카탈로그 크롤 시 트래픽이 상당하므로 `content_hash` 스킵이 특히 중요합니다.

---

## 8. 저장한 fixture

`apps/collector/tests/fixtures/secondtrack/` — 전부 2026-08-20 수집

| 파일 | 내용 |
|---|---|
| `detail_in_stock_609.html` | 재고 있음 (`Otis Lim - 사생아`) |
| `detail_sold_out_595.html` | 품절 (`brb. - the blueprint`) |
| `detail_preorder_599.html` | 예약판매 (`[예약판매] Jungle - Sunshine`) |
| `detail_preorder_sold_out_593.html` | 예약판매 + 품절 (엣지 케이스) |
| `list_preorder.html` | `/preorder` 목록 7건 (중복 렌더링 포함) |
| `list_shop_all_p1.html` | `/shop-all` 1페이지 12건 |

---

## 9. 미해결 사항

1. `/shop-all` 총 페이지 수 미확인 — 크롤 예산 산정 필요
2. `/parkhyoshin` 같은 기획 페이지가 상시 존재하는지, `/shop-all`이 이를 포함하는지 미확인
3. 페이지당 상품 수 미확정 (1페이지에서 고유 12건 관측)

> ✅ 이용약관 확인(§2) 완료로 **T-014 착수를 막는 선행 조건은 없습니다.**
