# ADR-0001: `PREORDER_OPEN` 감지 방식 재정의

- **상태**: **Deferred (보류)** — 2026-08-20 결정. 뼈대(M0) 완성 후 재검토
- **보류 사유**: 워킹 스켈레톤 단계에서 이벤트 모델을 확정할 필요가 없음.
  M0의 목표는 `수집 → DB → API → 화면` 경로 검증이며, 예약 관련 기능은 그 경로에 포함되지 않음
- **작성일**: 2026-08-20
- **관련**: 블루프린트 §3.1 (`StockStatus`, `RawItem`), §4.5 (EventDetector), T-006 / T-013 조사 결과
- **영향 태스크**: T-007, T-012, T-014, T-023

---

> ## ⚠️ 보류 중 — 지금 읽는 사람에게
>
> **당분간 예약(PREORDER) 관련 기능은 구현하지 않습니다.** 본 문서는 조사에서 드러난 사실을
> 잊지 않기 위한 기록이며, **지금 행동을 요구하지 않습니다.**
>
> M0~M2 동안의 취급 방침:
> - `StockStatus` 는 **블루프린트 §3.1 원안 그대로** 둡니다 (`PREORDER` 멤버 유지, `is_preorder` 미도입)
> - 어댑터(T-007/T-014)는 예약 마커를 **판정에 쓰지 않고**, 원문 그대로 `title_raw` 에 보존합니다.
>   `RawItem.extra` 에 관측 사실만 남겨도 무방합니다
> - 예약 전용 고빈도 폴링(§4.3)은 **도입하지 않습니다.** 전 소스 동일 주기로 운영합니다
> - `PREORDER_OPEN` 이벤트는 **생성하지 않습니다.** 예약 상품의 최초 관측은 `NEW_LISTING` 으로 처리됩니다
>
> **재검토 시점**: T-023(EventDetector) 착수 전. 그때 §4의 제안과 §6의 4개 질문을 다시 꺼냅니다.
>
> 데이터는 이미 보존되어 있습니다 — fixture `*_preorder_sold_out_*.html` 4건이
> "예약 ∧ 품절" 상태를 담고 있으므로, 나중에 재조사할 필요가 없습니다.

---

## 1. 배경 — 조사에서 드러난 문제

블루프린트 §4.5는 `PREORDER_OPEN` 을 다음과 같이 정의합니다.

| 조건 | 생성 이벤트 |
|---|---|
| `stock_status`: `COMING_SOON`/`UNKNOWN` → `PREORDER` | `PREORDER_OPEN` |

이 정의는 **"예약 오픈 전에 상품이 이미 관측 가능한 상태로 존재한다"** 를 전제합니다.

**T-006·T-013 실측 결과 이 전제는 성립하지 않습니다.**

| 관측 | 김밥레코즈 | 세컨드트랙 |
|---|---|---|
| `COMING_SOON` 에 해당하는 상태의 상품 | **0건** | **0건** |
| 예약 목록의 상품 상태 | 전부 구매 가능 또는 이미 품절 | 7건 중 4건이 이미 `SOLDOUT` |
| 오픈 전 상품 노출 여부 | Cafe24는 미진열 상품을 HTML에 **노출하지 않음** | 동일 |

즉 **상품은 "어느 날 갑자기, 이미 예약 가능한 상태로" 나타납니다.**

## 2. 결과적으로 무엇이 깨지는가

현행 정의대로 구현하면:

1. 예약 상품의 **최초 관측 시점의 상태는 `PREORDER`** 이다
2. 직전 상태가 존재하지 않으므로 §4.5의 첫 번째 규칙에 걸려 **`NEW_LISTING` 이 발생**한다
3. `COMING_SOON → PREORDER` 전이는 **영원히 발생하지 않는다**
4. 따라서 **`PREORDER_OPEN` 이벤트는 단 한 번도 생성되지 않는다**

그런데 블루프린트 §4.5는 이렇게 못박고 있습니다.

> `PREORDER_OPEN`은 **최우선 알림 등급**으로 즉시 발송합니다. 나머지는 배치 발송합니다.

**본 서비스의 핵심 기능이 조용히 동작하지 않게 되고**, 해당 알림은 `NEW_LISTING` 으로 분류되어
배치 큐로 흘러갑니다. CLAUDE.md §6이 경고한 *"`PREORDER_OPEN` 은 시간에 민감하다"* 가 정확히 무너집니다.

## 3. 두 번째 문제 — `PREORDER` 와 `SOLD_OUT` 은 서로 배타적이지 않다

fixture로 확인된 실제 상태입니다.

| 소스 | 상품 | 예약 여부 | 재고 |
|---|---|---|---|
| 김밥 | `Phoebe Bridgers / Lost Weekend` (32584) | 예약 | **품절** |
| 세컨드트랙 | `[예약판매] Ashmute - Somnia 0:00` (593) | 예약 | **품절** |

현행 `StockStatus` 는 단일 enum이라 **"예약판매인데 품절"을 표현할 수 없습니다.**
어느 쪽을 택해도 정보가 손실됩니다.

- `SOLD_OUT` 을 택하면 → 예약 상품이었다는 사실이 사라져 `PREORDER_OPEN` 판정이 불가능
- `PREORDER` 를 택하면 → 구매 불가한 상품을 구매 가능한 것처럼 알림

또한 두 소스 모두 **예약 여부와 재고를 물리적으로 별개 신호로 제공**합니다.
(김밥: 카테고리·제목 마커 vs `stock_number` / 세컨드트랙: `[예약판매]` 접두어 vs `is_soldout`)
데이터 원천이 2축인데 모델이 1축인 것이 근본 원인입니다.

---

## 4. 제안

### 4.1 `RawItem` 에 `is_preorder: bool` 추가 (2축 분리)

`StockStatus` 는 **구매 가능성만** 표현하고, 예약 여부는 독립 필드로 분리합니다.

```python
class StockStatus(StrEnum):
    IN_STOCK = "IN_STOCK"
    SOLD_OUT = "SOLD_OUT"
    COMING_SOON = "COMING_SOON"   # 유지 (향후 소스 대비, 현 2개 소스에서는 미사용)
    UNKNOWN = "UNKNOWN"

class RawItem(BaseModel):
    ...
    stock_status: StockStatus
    is_preorder: bool          # 신규
```

- `PREORDER` 는 `StockStatus` 에서 제거하고 `is_preorder=True` 로 표현
- "예약 + 품절" = `stock_status=SOLD_OUT, is_preorder=True` 로 **손실 없이 표현 가능**
- `listings` 테이블에 `is_preorder BOOLEAN NOT NULL DEFAULT FALSE` 컬럼 추가 (§4.2)

> 대안으로 enum에 `PREORDER_SOLD_OUT` 을 추가하는 방법도 있으나,
> 축이 2개인 데이터를 enum 조합으로 펼치는 것이라 상태가 곱으로 늘어납니다. 분리를 권합니다.

### 4.2 `PREORDER_OPEN` 정의 변경

| 조건 | 생성 이벤트 |
|---|---|
| 해당 `source_item_id` 의 **최초 관측**이고 `is_preorder == True` | **`PREORDER_OPEN`** (+ `NEW_LISTING`) |
| `is_preorder`: `False` → `True` | `PREORDER_OPEN` |
| `stock_status`: `COMING_SOON` → 구매 가능 AND `is_preorder == True` | `PREORDER_OPEN` (기존 규칙, 향후 소스 대비 유지) |

**핵심 변경**: `PREORDER_OPEN` 은 *상태 전이*가 아니라 **신규 등장 감지**입니다.
`NEW_LISTING` 과 동시에 발생할 수 있으며, 이때 **발송 경로는 `PREORDER_OPEN` 을 따릅니다**(즉시 발송).

`stock_status == SOLD_OUT` 인 채로 최초 관측된 예약 상품에도 `PREORDER_OPEN` 을 생성할지는
**생성하되 발송하지 않음**을 제안합니다. 이미 구매 불가한 알림은 사용자에게 소음입니다.
(이벤트 타임라인 §5.2에는 남겨 이력을 보존)

### 4.3 예약 목록 전용 고빈도 폴링

`PREORDER_OPEN` 의 **탐지 지연 = 폴링 주기** 입니다. 이보다 빠를 수 없습니다.
블루프린트 기본 주기 30분은 조사 결과에 비추어 너무 깁니다
(세컨드트랙 예약 7건 중 4건이 이미 품절).

다행히 두 소스 모두 **예약 전용 목록 URL이 있어 요청 1건이면 충분합니다.**

| 소스 | 예약 전용 URL | 제안 주기 |
|---|---|---|
| `gimbab` | `/product/list.html?cate_no=42` | **300초** |
| `secondtrack` | `/preorder` | **300초** |

비용: 소스당 **0.0033 req/s**. 0.5 req/s 한도의 0.7% 입니다.

> 김밥은 엣지 캐시 TTL이 300초(`x-ttl: 300`)이므로 **300초가 물리적 하한**입니다.
> 더 짧게 폴링해도 동일한 캐시 응답만 받습니다.

전체 카탈로그 크롤(30분)과 **분리된 스케줄**로 운영합니다 (T-012에 반영).

---

## 5. 정직하게 남는 한계

- 예약이 **오픈되기 전에는 알 수 없습니다.** 두 소스 모두 오픈 전 상품을 노출하지 않기 때문입니다.
  "곧 열립니다" 형태의 사전 알림은 **현 소스 구성으로는 구현 불가**입니다.
- 한정반이 5분 이내에 소진되면 알림이 도착해도 이미 늦습니다. 이 경우를 없앨 방법은 없습니다.
- 따라서 §1.3 성공 지표에 `PREORDER_OPEN` 관련 항목이 있다면 **"오픈 후 5분 이내 탐지"** 처럼
  달성 가능한 형태로 표현되어야 합니다.

## 6. 검토 요청 사항

승인이 필요한 결정은 다음 4가지입니다.

1. `StockStatus` 에서 `PREORDER` 를 빼고 `is_preorder: bool` 로 분리하는 데 동의하는가? (§4.1)
2. `PREORDER_OPEN` 을 "최초 관측 시 예약 상태"로 재정의하는 데 동의하는가? (§4.2)
3. 최초 관측이 이미 품절인 예약 상품은 **이벤트는 생성하되 발송하지 않는** 처리에 동의하는가? (§4.2)
4. 예약 목록 300초 전용 폴링을 도입하는 데 동의하는가? (§4.3)

승인 시 **블루프린트 §3.1 / §4.2 / §4.5 를 `.ko` / `.en` 양쪽 동시 수정**해야 합니다 (CLAUDE.md §9).

## 7. 참고 자료

- [`docs/adapters/gimbab.md`](../adapters/gimbab.md) §6
- [`docs/adapters/secondtrack.md`](../adapters/secondtrack.md) §6
- fixture: `apps/collector/tests/fixtures/{gimbab,secondtrack}/detail_preorder_sold_out_*.html`
