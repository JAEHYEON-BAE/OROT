"""수집기 검증 (T-005).

**실시간 네트워크 요청이 없다** (CLAUDE.md §2 규칙 2) — `httpx.MockTransport` 를 쓴다.
속도 제한 검증도 실제로 기다리지 않는다 — 가짜 시계를 주입해 결정론적으로 확인한다.
"""

import random
from collections.abc import Callable
from itertools import pairwise

import httpx
import pytest

from orot_collector.fetcher import (
    MAX_CONCURRENCY,
    MAX_RATE_LIMIT_RPS,
    Fetcher,
    FetchOutcome,
    InMemoryConditionalCache,
    RateLimiter,
    SourceBlockedError,
    content_hash,
)

USER_AGENT = "OROT/1.0 (+https://example.com/about; contact@example.com)"
ALLOW_ALL_ROBOTS = "User-agent: *\nAllow: /\n"


class FakeClock:
    """`sleep` 이 호출된 만큼만 시간이 흐르는 시계."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def make_fetcher(client: httpx.AsyncClient, **kwargs: object) -> Fetcher:
    """테스트용 수집기. **실시간 대기를 하지 않도록** 가짜 시계를 주입한다.

    속도 제한 자체를 검증하는 테스트만 자기 시계를 따로 만든다.
    """
    clock = FakeClock()
    kwargs.setdefault(
        "rate_limiter",
        RateLimiter(MAX_RATE_LIMIT_RPS, jitter_seconds=0.0, clock=clock, sleep=clock.sleep),
    )
    kwargs.setdefault("sleep", clock.sleep)
    return Fetcher(source_id="t", user_agent=USER_AGENT, client=client, **kwargs)  # type: ignore[arg-type]


def robots_then(handler: Callable[[httpx.Request], httpx.Response], robots: str = ALLOW_ALL_ROBOTS):
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        return handler(request)

    return _handler


# ─── 인수 조건: 0.5 req/s 준수 ───────────────────────────────────


async def test_rate_limiter_enforces_minimum_interval() -> None:
    """T-005 인수 조건: 0.5 req/s 를 넘지 않는다.

    보장의 본질은 **연속 요청 사이의 간격**이다. 간격이 1/rps 이상이면
    어떤 구간을 잘라 봐도 순간 속도가 상한을 넘을 수 없다.
    """
    clock = FakeClock()
    limiter = RateLimiter(MAX_RATE_LIMIT_RPS, jitter_seconds=0.0, clock=clock, sleep=clock.sleep)

    request_count = 5
    timestamps: list[float] = []
    for _ in range(request_count):
        await limiter.acquire()
        timestamps.append(clock.now)

    min_interval = 1.0 / MAX_RATE_LIMIT_RPS
    gaps = [b - a for a, b in pairwise(timestamps)]
    assert gaps, "간격을 검증하려면 요청이 2회 이상이어야 한다"
    assert all(gap >= min_interval - 1e-9 for gap in gaps), gaps
    assert timestamps[-1] - timestamps[0] >= (request_count - 1) * min_interval - 1e-9


async def test_jitter_only_slows_never_speeds_up() -> None:
    """지터가 빼는 방향이면 순간 속도가 상한을 넘는다. 0.5 req/s 는 평균이 아니라 상한이다."""
    clock = FakeClock()
    limiter = RateLimiter(
        MAX_RATE_LIMIT_RPS,
        jitter_seconds=1.0,
        clock=clock,
        sleep=clock.sleep,
        rng=random.Random(0),
    )

    for _ in range(10):
        await limiter.acquire()

    assert all(gap >= 1.0 / MAX_RATE_LIMIT_RPS for gap in clock.sleeps)


@pytest.mark.parametrize("rps", [0.6, 1.0, 10.0])
def test_rate_above_blueprint_cap_is_rejected(rps: float) -> None:
    with pytest.raises(ValueError, match=r"3\.4"):
        RateLimiter(rps)


def test_negative_jitter_is_rejected() -> None:
    with pytest.raises(ValueError, match="지터"):
        RateLimiter(MAX_RATE_LIMIT_RPS, jitter_seconds=-1.0)


def test_concurrency_above_cap_is_rejected() -> None:
    with pytest.raises(ValueError, match="동시 연결"):
        Fetcher(
            source_id="x",
            user_agent=USER_AGENT,
            client=make_client(lambda r: httpx.Response(200)),
            max_concurrency=MAX_CONCURRENCY + 1,
        )


def test_robots_crawl_delay_slows_us_but_never_speeds_us_up() -> None:
    limiter = RateLimiter(MAX_RATE_LIMIT_RPS, jitter_seconds=0.0)
    assert limiter.min_interval == 2.0

    limiter.raise_min_interval(0.1)  # 사이트가 더 빨라도 된다고 해도
    assert limiter.min_interval == 2.0

    limiter.raise_min_interval(10.0)  # 더 느리라고 하면 따른다
    assert limiter.min_interval == 10.0


# ─── robots.txt ────────────────────────────────────────────────


async def test_disallowed_path_is_never_requested() -> None:
    """금지 경로는 요청 자체를 보내지 않아야 한다 — 보내고 버리는 것으로는 부족하다."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /api\nAllow: /\n")
        return httpx.Response(200, text="본문")

    async with make_client(handler) as client:
        fetcher = make_fetcher(client)
        result = await fetcher.fetch("https://example.com/api/secret")

    assert result.outcome is FetchOutcome.DISALLOWED
    assert "/api/secret" not in requested


async def test_unreachable_robots_blocks_fetching() -> None:
    """robots.txt 를 못 가져오면 보수적으로 금지한다.

    네트워크 오류로 규칙이 조용히 사라지는 것이 가장 위험한 실패 방식이다.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(500)
        return httpx.Response(200, text="본문")

    async with make_client(handler) as client:
        fetcher = make_fetcher(client)
        result = await fetcher.fetch("https://example.com/product/1")

    assert result.outcome is FetchOutcome.DISALLOWED


async def test_missing_robots_means_no_restrictions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="본문")

    async with make_client(handler) as client:
        fetcher = make_fetcher(client)
        result = await fetcher.fetch("https://example.com/product/1")

    assert result.outcome is FetchOutcome.FETCHED


# ─── 조건부 요청 ────────────────────────────────────────────────


async def test_conditional_headers_are_sent_on_second_fetch() -> None:
    seen_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers)
        return httpx.Response(
            200,
            text="본문",
            headers={"ETag": '"abc"', "Last-Modified": "Wed, 20 Aug 2026 05:00:00 GMT"},
        )

    async with make_client(robots_then(handler)) as client:
        fetcher = make_fetcher(client)
        await fetcher.fetch("https://example.com/p/1")
        await fetcher.fetch("https://example.com/p/1")

    product_requests = [h for h in seen_headers if "If-None-Match" in h or "user-agent" in h]
    assert seen_headers[-1]["If-None-Match"] == '"abc"'
    assert seen_headers[-1]["If-Modified-Since"] == "Wed, 20 Aug 2026 05:00:00 GMT"
    assert product_requests


async def test_not_modified_returns_no_body() -> None:
    """§3.3: 304 는 본문 없이 스킵하고 last_seen_at 만 갱신한다."""

    async with make_client(robots_then(lambda r: httpx.Response(304))) as client:
        fetcher = make_fetcher(client)
        result = await fetcher.fetch("https://example.com/p/1")

    assert result.outcome is FetchOutcome.NOT_MODIFIED
    assert result.body is None
    assert result.content_hash is None


async def test_fetched_result_carries_content_hash() -> None:
    body = "<html>상품</html>"

    async with make_client(robots_then(lambda r: httpx.Response(200, text=body))) as client:
        fetcher = make_fetcher(client)
        result = await fetcher.fetch("https://example.com/p/1")

    assert result.outcome is FetchOutcome.FETCHED
    assert result.body == body
    assert result.content_hash == content_hash(body)


async def test_404_is_reported_not_raised() -> None:
    """404 는 오류가 아니라 DELISTED 판정의 입력이다 (§4.5)."""

    async with make_client(robots_then(lambda r: httpx.Response(404))) as client:
        fetcher = make_fetcher(client)
        result = await fetcher.fetch("https://example.com/p/1")

    assert result.outcome is FetchOutcome.NOT_FOUND


# ─── 차단 대응 ──────────────────────────────────────────────────


@pytest.mark.parametrize("status", [403, 429])
async def test_blocked_status_retries_then_raises(status: int) -> None:
    """§3.4: 429/403 은 지수 백오프 후에도 계속되면 차단으로 판단한다."""
    clock = FakeClock()
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status)

    async with make_client(robots_then(handler)) as client:
        fetcher = Fetcher(
            source_id="gimbab",
            user_agent=USER_AGENT,
            client=client,
            rate_limiter=RateLimiter(
                MAX_RATE_LIMIT_RPS, jitter_seconds=0.0, clock=clock, sleep=clock.sleep
            ),
            sleep=clock.sleep,
            max_retries=3,
        )
        with pytest.raises(SourceBlockedError) as exc:
            await fetcher.fetch("https://example.com/p/1")

    assert exc.value.source_id == "gimbab"
    assert exc.value.status_code == status
    assert attempts == 3
    # 지수 백오프: 1초, 2초 (마지막 시도 뒤에는 기다리지 않는다)
    assert 1.0 in clock.sleeps and 2.0 in clock.sleeps


async def test_retry_after_header_is_honoured() -> None:
    clock = FakeClock()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "42"})

    async with make_client(robots_then(handler)) as client:
        fetcher = Fetcher(
            source_id="t",
            user_agent=USER_AGENT,
            client=client,
            rate_limiter=RateLimiter(
                MAX_RATE_LIMIT_RPS, jitter_seconds=0.0, clock=clock, sleep=clock.sleep
            ),
            sleep=clock.sleep,
            max_retries=2,
        )
        with pytest.raises(SourceBlockedError):
            await fetcher.fetch("https://example.com/p/1")

    assert 42.0 in clock.sleeps


async def test_transient_block_recovers_without_raising() -> None:
    clock = FakeClock()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429)
        return httpx.Response(200, text="본문")

    async with make_client(robots_then(handler)) as client:
        fetcher = Fetcher(
            source_id="t",
            user_agent=USER_AGENT,
            client=client,
            rate_limiter=RateLimiter(
                MAX_RATE_LIMIT_RPS, jitter_seconds=0.0, clock=clock, sleep=clock.sleep
            ),
            sleep=clock.sleep,
        )
        result = await fetcher.fetch("https://example.com/p/1")

    assert result.outcome is FetchOutcome.FETCHED


# ─── 캐시 ──────────────────────────────────────────────────────


def test_cache_ignores_entries_without_validators() -> None:
    cache = InMemoryConditionalCache()
    cache.set("https://example.com/p/1", None, None)
    assert cache.get("https://example.com/p/1") == (None, None)


# ─── 실제 소스의 robots.txt 회귀 테스트 ──────────────────────────
#
# 아래 전문은 2026-08-20 에 실제로 수집한 것이다 (docs/adapters/*.md 참조).
# robots 판정이 조용히 바뀌면 블루프린트 §3.4 를 위반한 채 크롤하게 되므로 여기서 고정한다.

REAL_ROBOTS = {
    "gimbabrecords.com": "User-agent: *\nDisallow: /admin\nDisallow: /api\nAllow: /\n",
    "secondtrack.kr": (
        "User-agent: *\nAllow: /\nDisallow: /site_join\nDisallow: /site_join_agree\n"
        "Disallow: /login\nDisallow: /logout.cm\nDisallow: /shop_cart\n"
        "Disallow: /?mode*\nDisallow: /admin\n"
    ),
    "poclanos.bstage.in": "User-agent: *\nDisallow: /assets/\n",
}

# `urllib.robotparser` 가 RFC 9309 를 따르지 않아 **잘못 허용하는** 경로.
# 블루프린트 §3.4 의 표기를 유지하기로 한 결정에 따른 알려진 공백이다 — ADR-0003.
# 현재 어댑터는 이 경로를 요청하지 않으므로 실제 위반은 없다.
_KNOWN_ROBOTPARSER_GAP = pytest.mark.xfail(
    strict=True,
    reason=(
        "urllib.robotparser 는 최장 매치(RFC 9309 §2.2.2)와 와일드카드(§2.2.3)를 "
        "지원하지 않는다. ADR-0003 참조. 파서를 교체하면 이 표시를 제거할 것."
    ),
)

REAL_ROBOTS_CASES = [
    # (source_id, url, 허용되어야 하는가)
    ("gimbab", "https://gimbabrecords.com/product/list.html?cate_no=42", True),
    ("gimbab", "https://gimbabrecords.com/product/detail.html?product_no=32562", True),
    ("gimbab", "https://gimbabrecords.com/product/back-in-stock.html", True),
    ("gimbab", "https://gimbabrecords.com/api/products", False),
    ("gimbab", "https://gimbabrecords.com/admin", False),
    ("secondtrack", "https://secondtrack.kr/shop-all/?idx=609", True),
    ("secondtrack", "https://secondtrack.kr/preorder", True),
    # ↓ Allow: / 가 앞에 있어 순서 우선 매칭이 뒤의 Disallow 를 덮는다.
    pytest.param(
        "secondtrack", "https://secondtrack.kr/shop_cart", False, marks=_KNOWN_ROBOTPARSER_GAP
    ),
    # ↓ /?mode* 의 와일드카드를 해석하지 못한다.
    pytest.param(
        "secondtrack", "https://secondtrack.kr/?mode=policy", False, marks=_KNOWN_ROBOTPARSER_GAP
    ),
    ("poclanos", "https://poclanos.bstage.in/shop/products/71", True),
    ("poclanos", "https://poclanos.bstage.in/shop", True),
    ("poclanos", "https://poclanos.bstage.in/assets/app.js", False),
]


@pytest.mark.parametrize(
    ("source_id", "url", "should_allow"), REAL_ROBOTS_CASES, ids=lambda v: str(v)[:40]
)
async def test_real_robots_txt_decisions(source_id: str, url: str, should_allow: bool) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=REAL_ROBOTS[request.url.host])
        return httpx.Response(200, text="본문")

    async with make_client(handler) as client:
        fetcher = make_fetcher(client)
        result = await fetcher.fetch(url)

    allowed = result.outcome is not FetchOutcome.DISALLOWED
    assert allowed is should_allow


def test_adapters_do_not_request_the_paths_robotparser_would_wrongly_allow() -> None:
    """알려진 공백이 지금 문제되지 않는 **이유**를 고정한다 (ADR-0003).

    안전망이 세컨드트랙에서 동작하지 않으므로, 현재 유일한 방어선은
    "어댑터가 그 경로를 만들지 않는다"는 사실이다.
    어댑터가 새 URL 패턴을 만들기 시작하면 이 전제를 다시 확인해야 한다.
    """
    crawled_patterns = {
        "gimbab": ["/product/list.html", "/product/detail.html", "/product/back-in-stock.html"],
        "secondtrack": ["/shop-all/", "/preorder", "/ready-to-ship"],
        "poclanos": ["/shop/products/"],
    }
    wrongly_allowed = ["/shop_cart", "/?mode="]

    for patterns in crawled_patterns.values():
        for pattern in patterns:
            assert not any(pattern.startswith(bad) for bad in wrongly_allowed)


async def test_robots_fetch_is_rate_limited_and_counted() -> None:
    """robots.txt 도 그 소스에 보내는 요청이다 — §3.4 의 0.5 req/s 에 포함되어야 한다.

    이걸 빠뜨리면 실측 속도가 상한을 넘는다. 실제로 첫 라이브 시험에서 0.58 req/s 가 나왔다.
    """
    clock = FakeClock()

    async with make_client(robots_then(lambda r: httpx.Response(200, text="본문"))) as client:
        fetcher = make_fetcher(
            client,
            rate_limiter=RateLimiter(
                MAX_RATE_LIMIT_RPS, jitter_seconds=0.0, clock=clock, sleep=clock.sleep
            ),
        )
        await fetcher.fetch("https://example.com/p/1")
        await fetcher.fetch("https://example.com/p/2")

    # robots 1회 + 상품 2회
    assert fetcher.request_count == 3
    # 간격이 2개이므로 최소 4초가 흘러야 한다.
    assert clock.now >= 2 * (1.0 / MAX_RATE_LIMIT_RPS)


async def test_robots_is_fetched_once_per_host() -> None:
    """호스트당 1회만 조회한다 — 매번 받으면 그만큼 예산을 낭비한다."""
    robots_hits = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal robots_hits
        if request.url.path == "/robots.txt":
            robots_hits += 1
            return httpx.Response(200, text=ALLOW_ALL_ROBOTS)
        return httpx.Response(200, text="본문")

    async with make_client(handler) as client:
        fetcher = make_fetcher(client)
        for i in range(3):
            await fetcher.fetch(f"https://example.com/p/{i}")

    assert robots_hits == 1
    assert fetcher.request_count == 4  # robots 1 + 상품 3
