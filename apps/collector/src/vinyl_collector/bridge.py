"""`Fetcher` 를 어댑터의 `PageFetcher` 프로토콜에 연결한다.

어댑터는 `packages/core` 에 있어 `vinyl_collector.fetcher` 를 임포트할 수 없다(의존 방향).
그래서 core 는 최소 프로토콜만 선언하고, 실제 연결은 여기서 한다.
"""

import structlog

from vinyl_collector.fetcher import Fetcher, FetchOutcome

log = structlog.get_logger(__name__)


class FetcherPageAdapter:
    """`Fetcher` 를 `vinyl_core.adapters.base.PageFetcher` 로 감싼다.

    본문을 얻지 못한 모든 경우(robots 금지 / 304 / 404)에 `None` 을 돌려주고,
    **사유는 반드시 로그로 남긴다** — 조용한 0건 수집을 막기 위해서다 (CLAUDE.md §2 규칙 5).
    """

    def __init__(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher

    async def fetch_text(self, url: str) -> str | None:
        result = await self._fetcher.fetch(url)
        if result.outcome is FetchOutcome.FETCHED:
            return result.body
        log.info(
            "fetch.no_body",
            source_id=self._fetcher.source_id,
            url=url,
            outcome=result.outcome.value,
        )
        return None
