"""시드 데이터 로딩 (T-003).

`sources` 테이블은 소스의 **정적 설정**을 담는다. 시드는 몇 번을 다시 돌려도
같은 결과가 나와야 하며(idempotent), **운영 상태를 덮어써서는 안 된다.**
"""

from importlib import resources
from typing import Any, Final

import structlog
import yaml
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from vinyl_core.enums import SourceKind
from vinyl_core.models import Source

log = structlog.get_logger(__name__)

SOURCES_FILE: Final = "sources.yaml"

# 블루프린트 §3.1: crawl_interval_seconds 최소 300.
MIN_CRAWL_INTERVAL_SEC: Final = 300

# 재시드가 덮어쓰지 않는 컬럼 — 런타임에 바뀌는 운영 상태이기 때문이다.
#   is_enabled / disabled_reason : §3.4 의 차단 대응이 자동으로 끄는 값
#   last_crawled_at              : 스케줄러가 갱신하는 값
_RUNTIME_STATE_COLUMNS: Final = frozenset({"is_enabled", "disabled_reason", "last_crawled_at"})


class SourceSeed(BaseModel):
    """`sources.yaml` 의 한 항목."""

    id: str
    display_name: str
    base_url: str
    kind: SourceKind
    crawl_interval_sec: int = Field(default=1800, ge=MIN_CRAWL_INTERVAL_SEC)

    @field_validator("id")
    @classmethod
    def _slug_only(cls, v: str) -> str:
        """CLAUDE.md §4: source_id 는 소문자 ASCII 슬러그."""
        if not v or not all(c.islower() or c.isdigit() or c == "_" for c in v) or not v.isascii():
            msg = f"source_id 는 소문자 ASCII 슬러그여야 합니다: {v!r}"
            raise ValueError(msg)
        return v

    @field_validator("base_url")
    @classmethod
    def _https_no_trailing_slash(cls, v: str) -> str:
        if not v.startswith("https://"):
            msg = f"base_url 은 https 여야 합니다: {v!r}"
            raise ValueError(msg)
        return v.rstrip("/")


def load_source_seeds() -> list[SourceSeed]:
    """패키지에 동봉된 `sources.yaml` 을 읽어 검증한다."""
    raw = resources.files("vinyl_core").joinpath(SOURCES_FILE).read_text(encoding="utf-8")
    parsed: Any = yaml.safe_load(raw)
    if not isinstance(parsed, list):
        msg = f"{SOURCES_FILE} 최상위는 목록이어야 합니다."
        raise TypeError(msg)

    seeds = [SourceSeed.model_validate(item) for item in parsed]

    ids = [s.id for s in seeds]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        msg = f"{SOURCES_FILE} 에 중복된 source_id 가 있습니다: {sorted(duplicates)}"
        raise ValueError(msg)

    return seeds


async def seed_sources(session: AsyncSession) -> int:
    """`sources` 를 upsert 한다. 반환값은 처리한 행 수.

    이미 존재하는 소스는 **정적 설정만** 갱신한다. `is_enabled` 를 되살리지 않는 것이 중요하다 —
    블루프린트 §3.4 에 따라 429/403 으로 자동 비활성화된 소스를 시드가 다시 켜 버리면
    차단된 사이트를 계속 두드리게 된다.
    """
    seeds = load_source_seeds()
    if not seeds:
        log.warning("seed.sources.empty", file=SOURCES_FILE)
        return 0

    statement = insert(Source).values([s.model_dump(mode="json") for s in seeds])
    updatable = {
        column.name: statement.excluded[column.name]
        for column in Source.__table__.columns
        if column.name != "id" and column.name not in _RUNTIME_STATE_COLUMNS
    }
    await session.execute(
        statement.on_conflict_do_update(index_elements=[Source.id], set_=updatable)
    )

    log.info("seed.sources.done", count=len(seeds), ids=[s.id for s in seeds])
    return len(seeds)
