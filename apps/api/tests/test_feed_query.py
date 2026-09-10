"""피드는 발매당 최신 이벤트 하나만, 무효화되지 않은 것만 싣는다 (T-118, T-119).

DB 없이 **생성되는 SQL 의 모양**을 본다. 실제 접힘 동작은 컨테이너에서
실 데이터로 따로 검증한다 — 여기서 고정하려는 것은 규칙이 사라지지 않는다는 점이다.
"""

import re
from pathlib import Path

from sqlalchemy.dialects import postgresql

from vinyl_api.feed_query import latest_event_per_release

REPO_ROOT = Path(__file__).resolve().parents[3]


def _sql(limit: int = 50) -> str:
    return str(latest_event_per_release(limit).compile(dialect=postgresql.dialect()))


def test_collapses_to_one_row_per_release() -> None:
    """`DISTINCT ON (release_id)` 이 없으면 같은 앨범이 피드를 도배한다."""
    assert "DISTINCT ON" in _sql()
    assert "listing_events.release_id" in _sql()


def test_picks_the_newest_event_not_an_arbitrary_one() -> None:
    """`DISTINCT ON` 은 정렬 첫 행을 남긴다 — 정렬이 틀리면 옛 이벤트가 살아남는다.

    동시각이면 `id` 로 가른다. 공개와 동시에 예약이 시작되면 `occurred_at` 이
    같을 수 있고, 그때는 나중에 만들어진 쪽이 더 최신 상태다.
    """
    sql = _sql()
    inner = sql[sql.index("DISTINCT ON") :]
    order = inner[inner.index("ORDER BY") :]
    assert re.search(
        r"release_id,\s*listing_events\.occurred_at DESC,\s*listing_events\.id DESC", order
    ), order


def test_only_published_releases() -> None:
    """초안이 새면 미공지 발매가 유출된다 — 피드의 최우선 필터다."""
    assert "is_published" in _sql()


def test_result_is_ordered_newest_first() -> None:
    """발매별로 고른 뒤 **다시 시간순**으로 정렬해야 피드가 최신순이 된다."""
    sql = _sql()
    assert sql.rstrip().endswith("LIMIT %(param_1)s"), sql[-80:]
    outer_order = sql.rindex("ORDER BY")
    assert "occurred_at DESC" in sql[outer_order:]


def test_limit_is_applied() -> None:
    assert "LIMIT" in _sql(7)


def test_feed_and_rss_use_the_same_query() -> None:
    """두 피드가 다른 것을 보여 주면 어느 쪽이 맞는지 알 수 없다.

    각자 질의를 들고 있으면 한쪽만 고쳐지고 다른 쪽이 조용히 어긋난다.
    """
    for module in ("routers/feed.py", "routers/rss.py"):
        source = (REPO_ROOT / "apps/api/src/vinyl_api" / module).read_text(encoding="utf-8")
        assert "latest_event_per_release" in source, module
        # 예전 질의가 남아 있으면 접힘이 적용되지 않는다.
        assert "select(ListingEvent, Release)" not in source, f"{module} 에 옛 질의가 남아 있다"


def test_superseded_events_are_hidden() -> None:
    """일정이 바뀌어 역할을 잃은 이벤트가 남아 있으면 안 된다 (T-119).

    옛 시각을 말하는 '예약 시작'이 새 시각을 말하는 '일정 변동' 옆에 있으면
    사용자는 어느 쪽을 믿어야 할지 알 수 없다.
    """
    assert "superseded_at IS NULL" in _sql()


def test_supersede_filter_is_inside_the_distinct_on() -> None:
    """무효화 필터가 바깥에만 있으면 **발매가 통째로 사라진다.**

    `DISTINCT ON` 이 무효화된 이벤트를 최신으로 고른 뒤 바깥에서 걸러 내면,
    살아 있는 옛 이벤트가 있어도 그 발매는 피드에 한 줄도 안 나온다.
    """
    sql = _sql()
    distinct_at = sql.index("DISTINCT ON")
    subquery_end = sql.index("GROUP BY") if "GROUP BY" in sql else len(sql)
    inner = sql[distinct_at:subquery_end]
    assert "superseded_at IS NULL" in inner
