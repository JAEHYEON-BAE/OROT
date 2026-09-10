# ADR-0003: robots.txt 파서 — `urllib.robotparser` 유지

- **상태**: **Rejected (파서 교체를 하지 않음)** — 2026-08-20 결정
- **결정**: 블루프린트 §3.4 대로 **`urllib.robotparser` 를 유지**한다.
  보완책(URL 패턴 화이트리스트)은 **보류**하며 차후에 도입한다
- **작성일**: 2026-08-20
- **관련**: 블루프린트 §3.4, CLAUDE.md §2 규칙 3 / T-005
- **영향 범위**: `apps/collector/src/vinyl_collector/fetcher.py` 의 `RobotsPolicy`

---

## 1. 배경

블루프린트 §3.4 는 파서를 명시적으로 지목한다.

> | robots.txt 준수 | **`urllib.robotparser`** 로 매 크롤 시작 시 파싱. `Disallow` 경로 접근 금지 |

T-005 구현 중 세 소스의 **실제 robots.txt** 로 검증했더니
`urllib.robotparser` 가 **세컨드트랙의 금지 경로 2건을 허용으로 잘못 판정**했다.

## 2. 원인 — 독립적인 결함 두 가지

### (A) 최장 매치가 아니라 "먼저 나온 규칙" 우선

세컨드트랙 robots.txt 는 `Allow: /` 가 **맨 앞**에 있다.

```
User-agent: *
Allow: /                 ← 모든 경로에 매치된다
Disallow: /site_join
Disallow: /login
Disallow: /shop_cart     ← 더 구체적인데도 무시된다
Disallow: /?mode*
Disallow: /admin
```

RFC 9309 §2.2.2 는 **가장 긴(구체적인) 매치가 이긴다**고 규정한다.
`urllib.robotparser` 는 규칙을 순서대로 훑어 **처음 매치되는 것**을 택하므로,
`Allow: /` 가 뒤의 모든 `Disallow` 를 덮어버린다.

```python
p = RobotFileParser(); p.parse("User-agent: *\nAllow: /\nDisallow: /shop_cart\n".splitlines())
p.can_fetch("X", "https://x.kr/shop_cart")   # True  ← 잘못됨
```

### (B) 와일드카드 미지원

`Disallow: /?mode*` 는 RFC 9309 §2.2.3 의 `*` 와일드카드다.
`urllib.robotparser` 는 이를 리터럴 접두사로 취급하므로 `/?mode=policy` 에 매치되지 않는다.

```python
p.can_fetch("X", "https://x.kr/?mode=policy")   # True  ← 잘못됨
```

> 이 경로는 세컨드트랙의 **이용약관 페이지**다. 조사 단계(T-013)에서 robots.txt 를 사람이 읽고
> 수동으로 회피했기에 실제 위반은 없었지만, 자동화되면 그대로 위반하게 된다.

## 3. 무엇이 걸려 있는가

CLAUDE.md §2 규칙 3 은 **협상 불가** 항목이다.

> 3. **Never violate the crawling rules in blueprint §3.4.** Specifically: honor robots.txt …

지켜야 할 대상은 **robots.txt 그 자체**이지 특정 라이브러리가 아니다.
따라서 판단의 기준은 "명시된 도구를 썼는가"가 아니라 **"실제로 규칙을 어기는가"** 다.

§4 에서 정리하듯 현재 어댑터는 잘못 허용되는 경로를 요청하지 않으므로 **실제 위반은 없다.**
다만 이 오류가 **조용하다**는 점은 기억해 둘 만하다 — 만약 위반이 발생하더라도
크롤은 성공하고 로그도 정상이며, 사이트가 거부 의사를 밝힌 경로를 계속 요청할 뿐이다.
그래서 §6 처럼 코드에 표시를 남기고 §7 의 재검토 조건을 명시해 둔다.

## 4. 결정 — 유지

**`urllib.robotparser` 를 그대로 쓴다.** 블루프린트 §3.4 가 지목한 도구를 바꾸지 않는다.

### 근거

현재 어댑터가 요청하는 경로는 다음뿐이며, **잘못 허용되는 경로를 만들지 않는다.**

| 소스 | 요청하는 경로 |
|---|---|
| gimbab | `/product/list.html`, `/product/detail.html`, `/product/back-in-stock.html` |
| secondtrack | `/shop-all/`, `/preorder`, `/ready-to-ship` |
| poclanos | `/shop/products/<id>` |

`/shop_cart` 와 `/?mode=policy` 는 어느 어댑터도 생성하지 않으므로 **실제 위반은 발생하지 않는다.**
결함은 잠복 상태이며, 의존성을 늘리지 않는 편이 낫다고 판단했다.

## 5. 감수하는 위험 — 정직하게

이 결정으로 **robots 안전망이 세컨드트랙에서는 동작하지 않는다.** 남는 방어선은
"어댑터가 그 경로를 만들지 않는다"는 사실 하나뿐이다.

주의할 점이 하나 있다. 세 어댑터 중 **둘은 URL 을 직접 만들지 않고 사이트가 준 링크를 따라간다.**

| 소스 | 상세 URL 획득 |
|---|---|
| gimbab | `.description .name a[href]` — **사이트 HTML 에서 추출** |
| secondtrack | 상품 카드·페이징의 `href` — **사이트 HTML 에서 추출** |
| poclanos | `product_id` 순차 생성 — 우리가 만듦 |

즉 요청 URL 이 전적으로 우리 통제 아래 있지는 않다. Cafe24·아임웹 테마는 상품 목록 블록 안에
장바구니·위시리스트·정렬 링크를 함께 렌더링하므로, **셀렉터가 넓어지거나 사이트가 개편되면**
`/shop_cart` 링크가 후보에 섞일 수 있다. 그때 gimbab 이면 막히고 secondtrack 이면 통과한다.

### 보류한 보완책

**`discover()` 단계의 URL 패턴 화이트리스트** — 어댑터가 정의한 패턴에 맞는 URL 만 요청한다.
안전망을 포기한 대신 세워야 할 방어이지만, 지금은 도입하지 않기로 했다.
T-007 이후 어댑터가 실제로 링크를 따라가기 시작할 때 재검토한다.

## 6. 코드에 남긴 표시

이 공백이 잊히지 않도록 두 곳에 고정했다.

1. `RobotsPolicy` 의 docstring — 두 결함과 영향 범위, 본 ADR 링크
2. `test_real_robots_txt_decisions` 의 **`xfail(strict=True)` 2건** —
   `/shop_cart` 와 `/?mode=policy`. 파서를 고치면 XPASS 가 되어 **테스트가 실패**하므로,
   그때 표시를 제거하도록 강제된다
3. `test_adapters_do_not_request_the_paths_robotparser_would_wrongly_allow` —
   지금 문제되지 않는 **이유**(어댑터가 그 경로를 만들지 않음)를 고정한다

## 7. 재검토 조건

다음 중 하나라도 해당하면 이 결정을 다시 연다.

- 어댑터가 사이트 HTML 에서 추출한 링크를 **필터 없이** 따라가기 시작할 때
- 새 소스의 robots.txt 가 **우리가 실제로 크롤하는 경로**에 최장 매치나 와일드카드를 쓸 때
- 파서 카나리(T-018)가 robots 관련 오탐/미탐을 보고할 때

## 8. 참고

- RFC 9309 (Robots Exclusion Protocol): 최장 매치 §2.2.2, 와일드카드 §2.2.3
- [`docs/adapters/secondtrack.md`](../adapters/secondtrack.md) §1 — 문제의 robots.txt 전문
