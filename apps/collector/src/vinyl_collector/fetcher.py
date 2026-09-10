"""HTTP 수집기 (블루프린트 §3.3, §3.4).

이 모듈은 **블루프린트 §3.4 의 수집 윤리를 코드로 강제하는 곳**이다.
여기서 규칙이 무너지면 다른 어디에서도 지켜지지 않는다.

| §3.4 규칙 | 구현 |
|---|---|
| robots.txt 준수 | `RobotsPolicy` — `urllib.robotparser`. `Disallow` 경로는 요청하지 않는다 |
| 최대 0.5 req/s | `RateLimiter` — 요청 간 최소 간격 + 양(+)의 지터 |
| 동시 연결 2 이하 | `asyncio.Semaphore` |
| User-Agent 명시 | 생성자에서 필수. 정체·연락처 검증은 `vinyl_core.settings` |
| 조건부 요청 | `If-None-Match` / `If-Modified-Since` → 304 는 본문 없이 스킵 |
| 429/403 대응 | 지수 백오프 후 `SourceBlockedError`. **소스 비활성화는 호출자 책임** |
"""

import asyncio
import hashlib
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog

log = structlog.get_logger(__name__)

# 블루프린트 §3.4 상한. 이 값을 넘기는 설정은 거부한다.
MAX_RATE_LIMIT_RPS: Final = 0.5
MAX_CONCURRENCY: Final = 2

# 차단 응답으로 간주하는 상태 코드 (§3.4).
BLOCKED_STATUS_CODES: Final = frozenset({403, 429})

Clock = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]


class FetchOutcome(StrEnum):
    """요청 결과 분류."""

    FETCHED = "FETCHED"  # 200. 본문과 해시가 있다
    NOT_MODIFIED = "NOT_MODIFIED"  # 304. 본문 없음 — last_seen_at 만 갱신 (§3.3)
    DISALLOWED = "DISALLOWED"  # robots.txt 가 금지 — 요청하지 않았다
    NOT_FOUND = "NOT_FOUND"  # 404. DELISTED 판정의 입력 (§4.5)


class SourceBlockedError(Exception):
    """429/403 이 백오프 후에도 계속될 때.

    **호출자가 해당 소스를 비활성화하고 운영자에게 알려야 한다** (§3.4).
    수집기 계층은 DB 를 건드리지 않는다.
    """

    def __init__(self, source_id: str, url: str, status_code: int) -> None:
        self.source_id = source_id
        self.url = url
        self.status_code = status_code
        super().__init__(f"{source_id}: {url} 에서 {status_code} 가 반복되어 차단으로 판단합니다.")


@dataclass(frozen=True, slots=True)
class FetchResult:
    """한 번의 요청 결과."""

    url: str
    outcome: FetchOutcome
    status_code: int | None = None
    body: str | None = None
    content_hash: str | None = None
    etag: str | None = None
    last_modified: str | None = None


class ConditionalCache(Protocol):
    """URL 별 조건부 요청 검증자(ETag / Last-Modified) 저장소.

    > ⚠️ 블루프린트 §4.2 의 `raw_snapshots` 에는 이 값을 담을 컬럼이 없다.
    > 현재 기본 구현은 프로세스 메모리이며, 재기동하면 사라진다.
    > 영속화는 T-017 에서 스키마와 함께 정한다.
    """

    def get(self, url: str) -> tuple[str | None, str | None]: ...
    def set(self, url: str, etag: str | None, last_modified: str | None) -> None: ...


class InMemoryConditionalCache:
    """프로세스 메모리 기반 기본 구현."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[str | None, str | None]] = {}

    def get(self, url: str) -> tuple[str | None, str | None]:
        return self._entries.get(url, (None, None))

    def set(self, url: str, etag: str | None, last_modified: str | None) -> None:
        if etag or last_modified:
            self._entries[url] = (etag, last_modified)


class RateLimiter:
    """소스별 요청 속도 제한.

    지터는 **항상 더하기만 한다.** 빼는 방향으로 흔들면 순간 속도가 상한을 넘을 수 있는데,
    §3.4 의 0.5 req/s 는 평균이 아니라 상한이다.

    `clock` / `sleep` 을 주입받는 이유는 실제 시간을 기다리지 않고 테스트하기 위해서다.
    """

    def __init__(
        self,
        rps: float,
        *,
        jitter_seconds: float = 0.5,
        clock: Clock | None = None,
        sleep: Sleeper | None = None,
        rng: random.Random | None = None,
    ) -> None:
        if rps <= 0:
            msg = f"rps 는 양수여야 합니다: {rps}"
            raise ValueError(msg)
        if rps > MAX_RATE_LIMIT_RPS:
            msg = f"rps={rps} 는 블루프린트 §3.4 상한 {MAX_RATE_LIMIT_RPS} 를 초과합니다."
            raise ValueError(msg)
        if jitter_seconds < 0:
            msg = "지터는 음수일 수 없습니다 (상한을 넘게 됩니다)."
            raise ValueError(msg)

        self._min_interval = 1.0 / rps
        self._jitter_seconds = jitter_seconds
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._rng = rng or random.Random()
        self._next_allowed_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def min_interval(self) -> float:
        return self._min_interval

    def raise_min_interval(self, seconds: float) -> None:
        """robots.txt 의 `Crawl-delay` 가 우리보다 느릴 때 그쪽을 따른다.

        더 느리게만 조정한다 — 사이트가 더 빨라도 된다고 해도 §3.4 상한을 넘지 않는다.
        """
        if seconds > self._min_interval:
            log.info("ratelimit.slowed_by_robots", from_=self._min_interval, to=seconds)
            self._min_interval = seconds

    async def acquire(self) -> None:
        """다음 요청이 허용될 때까지 기다린다."""
        async with self._lock:
            now = self._clock()
            if self._next_allowed_at is not None and now < self._next_allowed_at:
                await self._sleep(self._next_allowed_at - now)
                now = self._clock()
            jitter = self._rng.uniform(0.0, self._jitter_seconds) if self._jitter_seconds else 0.0
            self._next_allowed_at = now + self._min_interval + jitter


class RobotsPolicy:
    """robots.txt 판정 (§3.4).

    **가져오지 못하면 허용으로 간주하지 않는다.** 네트워크 오류로 규칙이 사라지는 것이
    가장 위험한 실패 방식이므로, 조회 실패 시 보수적으로 금지한다.

    > ⚠️ **알려진 한계 — `urllib.robotparser` 는 RFC 9309 를 완전히 따르지 않는다.**
    >
    > 1. **최장 매치가 아니라 '먼저 나온 규칙' 우선.** `Allow: /` 가 앞에 있으면
    >    뒤의 모든 `Disallow` 가 무시된다 (RFC 9309 §2.2.2 위반)
    > 2. **와일드카드 미지원.** `Disallow: /?mode*` 가 `/?mode=policy` 에 매치되지 않는다 (§2.2.3)
    >
    > 세컨드트랙의 실제 robots.txt 가 두 경우에 모두 해당한다 —
    > `/shop_cart` 와 `/?mode=policy` 를 **허용으로 잘못 판정한다.**
    >
    > 현재 어댑터들이 이 경로를 요청하지 않으므로 실제 위반은 없다. 다만 gimbab·secondtrack 은
    > 상세 URL 을 **사이트 HTML 의 `href` 에서 추출**하므로 요청 URL 이 전적으로 우리 통제 아래
    > 있지는 않다. 즉 이 안전망은 세컨드트랙에서 동작하지 않는 상태다.
    >
    > 블루프린트 §3.4 표기를 유지하기로 결정했다 — `docs/adr/0003-robots-parser-library.md`.
    > 보완책(`discover()` 의 URL 패턴 화이트리스트)은 보류 중이다.
    """

    def __init__(self, user_agent: str) -> None:
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser | None] = {}

    @staticmethod
    def _origin(url: str) -> str:
        parts = urlparse(url)
        return f"{parts.scheme}://{parts.netloc}"

    def is_loaded(self, url: str) -> bool:
        """이미 조회한 호스트인가. 호출자가 불필요한 대기를 피하는 데 쓴다."""
        return self._origin(url) in self._parsers

    async def load(self, client: httpx.AsyncClient, url: str) -> None:
        """해당 호스트의 robots.txt 를 가져와 캐시한다."""
        origin = self._origin(url)
        if origin in self._parsers:
            return

        robots_url = urljoin(origin, "/robots.txt")
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            response = await client.get(robots_url)
        except httpx.HTTPError as exc:
            log.error("robots.fetch_failed", url=robots_url, error=str(exc))
            self._parsers[origin] = None
            return

        if response.status_code == httpx.codes.NOT_FOUND:
            # robots.txt 가 없으면 제한이 없다는 뜻이다 (RFC 9309 §2.3.1.3).
            parser.parse([])
            self._parsers[origin] = parser
            log.info("robots.absent", url=robots_url)
            return

        if response.status_code >= httpx.codes.BAD_REQUEST:
            log.error("robots.fetch_failed", url=robots_url, status=response.status_code)
            self._parsers[origin] = None
            return

        parser.parse(response.text.splitlines())
        self._parsers[origin] = parser
        log.info("robots.loaded", url=robots_url)

    def can_fetch(self, url: str) -> bool:
        parser = self._parsers.get(self._origin(url))
        if parser is None:
            # 미로딩 또는 조회 실패 — 보수적으로 금지한다.
            return False
        return parser.can_fetch(self._user_agent, url)

    def crawl_delay(self, url: str) -> float | None:
        parser = self._parsers.get(self._origin(url))
        if parser is None:
            return None
        delay = parser.crawl_delay(self._user_agent)
        return float(delay) if delay is not None else None


def content_hash(body: str) -> str:
    """본문 해시 (§3.3). `raw_snapshots.content_hash` 와 같은 값이어야 한다."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class Fetcher:
    """소스 하나를 위한 수집기. **소스마다 별도 인스턴스를 만든다** (속도 제한이 소스별이므로)."""

    def __init__(
        self,
        *,
        source_id: str,
        user_agent: str,
        client: httpx.AsyncClient,
        rps: float = MAX_RATE_LIMIT_RPS,
        max_concurrency: int = MAX_CONCURRENCY,
        cache: ConditionalCache | None = None,
        rate_limiter: RateLimiter | None = None,
        max_retries: int = 3,
        sleep: Sleeper | None = None,
    ) -> None:
        if max_concurrency > MAX_CONCURRENCY:
            msg = f"동시 연결은 {MAX_CONCURRENCY} 이하여야 합니다 (§3.4): {max_concurrency}"
            raise ValueError(msg)

        self.source_id = source_id
        self._user_agent = user_agent
        self._client = client
        self._limiter = rate_limiter or RateLimiter(rps)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._cache = cache or InMemoryConditionalCache()
        self._robots = RobotsPolicy(user_agent)
        self._max_retries = max_retries
        self._sleep = sleep or asyncio.sleep
        # 이 수집기가 실제로 보낸 HTTP 요청 수 (robots.txt 포함).
        self.request_count = 0

    async def fetch(self, url: str) -> FetchResult:
        """URL 하나를 가져온다.

        robots.txt 가 금지하면 **요청을 보내지 않고** `DISALLOWED` 를 반환한다.
        """
        if not self._robots.is_loaded(url):
            # robots.txt 도 그 소스에 보내는 요청이다. §3.4 의 0.5 req/s 에 포함시킨다.
            # 호스트당 1회뿐이라 비용은 시작 시 대기 한 번이다.
            await self._limiter.acquire()
            self.request_count += 1
            await self._robots.load(self._client, url)

        if not self._robots.can_fetch(url):
            log.warning("fetch.disallowed_by_robots", source_id=self.source_id, url=url)
            return FetchResult(url=url, outcome=FetchOutcome.DISALLOWED)

        delay = self._robots.crawl_delay(url)
        if delay is not None:
            self._limiter.raise_min_interval(delay)

        async with self._semaphore:
            return await self._fetch_with_backoff(url)

    async def _fetch_with_backoff(self, url: str) -> FetchResult:
        etag, last_modified = self._cache.get(url)
        headers = {"User-Agent": self._user_agent}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        for attempt in range(self._max_retries):
            await self._limiter.acquire()
            self.request_count += 1
            response = await self._client.get(url, headers=headers)

            if response.status_code not in BLOCKED_STATUS_CODES:
                return self._to_result(url, response)

            wait = self._backoff_seconds(response, attempt)
            log.warning(
                "fetch.blocked_response",
                source_id=self.source_id,
                url=url,
                status=response.status_code,
                attempt=attempt + 1,
                wait_seconds=wait,
            )
            if attempt < self._max_retries - 1:
                await self._sleep(wait)

        raise SourceBlockedError(self.source_id, url, response.status_code)

    @staticmethod
    def _backoff_seconds(response: httpx.Response, attempt: int) -> float:
        """지수 백오프. 사이트가 `Retry-After` 를 주면 그쪽을 우선한다."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass  # HTTP-date 형식은 지수 백오프로 대체한다
        return float(2**attempt)

    def _to_result(self, url: str, response: httpx.Response) -> FetchResult:
        if response.status_code == httpx.codes.NOT_MODIFIED:
            # §3.3: 본문을 받지 않는다. last_seen_at 만 갱신하면 된다.
            return FetchResult(
                url=url, outcome=FetchOutcome.NOT_MODIFIED, status_code=response.status_code
            )

        if response.status_code == httpx.codes.NOT_FOUND:
            return FetchResult(
                url=url, outcome=FetchOutcome.NOT_FOUND, status_code=response.status_code
            )

        response.raise_for_status()

        body = response.text
        new_etag = response.headers.get("ETag")
        new_last_modified = response.headers.get("Last-Modified")
        self._cache.set(url, new_etag, new_last_modified)

        return FetchResult(
            url=url,
            outcome=FetchOutcome.FETCHED,
            status_code=response.status_code,
            body=body,
            content_hash=content_hash(body),
            etag=new_etag,
            last_modified=new_last_modified,
        )
