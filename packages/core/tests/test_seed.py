"""시드 데이터 검증 (T-003).

DB 연결이 필요 없다 — `sources.yaml` 의 내용과 로더의 계약만 검사한다.
실제 upsert 동작(운영 상태 보존 등)은 `make seed` 로 컨테이너에서 확인했다.
"""

import pytest
from pydantic import ValidationError

from orot_core.enums import SourceKind
from orot_core.seed import MIN_CRAWL_INTERVAL_SEC, SourceSeed, load_source_seeds

# 블루프린트 §3.2 가 M0~M1 대상으로 지정한 소스.
EXPECTED_SOURCE_IDS = {"gimbab", "secondtrack", "poclanos"}


def test_seed_contains_expected_sources() -> None:
    assert {s.id for s in load_source_seeds()} == EXPECTED_SOURCE_IDS


def test_source_ids_are_unique() -> None:
    ids = [s.id for s in load_source_seeds()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("seed", load_source_seeds(), ids=lambda s: s.id)
def test_crawl_interval_respects_blueprint_minimum(seed: SourceSeed) -> None:
    """블루프린트 §3.1: 크롤 주기는 300초 미만이 될 수 없다."""
    assert seed.crawl_interval_sec >= MIN_CRAWL_INTERVAL_SEC


@pytest.mark.parametrize("seed", load_source_seeds(), ids=lambda s: s.id)
def test_base_url_is_https_without_trailing_slash(seed: SourceSeed) -> None:
    assert seed.base_url.startswith("https://")
    assert not seed.base_url.endswith("/")


def test_poclanos_points_at_the_store_not_the_label_site() -> None:
    """스토어는 레이블 사이트(poclanos.com)가 아니라 b.stage 에 있다.

    레이블 사이트에는 판매 상품이 없어, 그쪽을 가리키면 수집이 0건이 된다.
    """
    poclanos = next(s for s in load_source_seeds() if s.id == "poclanos")
    assert poclanos.base_url == "https://poclanos.bstage.in"
    assert poclanos.kind is SourceKind.DISTRIBUTOR


@pytest.mark.parametrize("bad_id", ["Gimbab", "gimbab-records", "김밥", "gimbab "])
def test_source_id_must_be_lowercase_ascii_slug(bad_id: str) -> None:
    """CLAUDE.md §4 의 명명 규칙을 로더가 강제한다."""
    with pytest.raises(ValidationError):
        SourceSeed(
            id=bad_id,
            display_name="x",
            base_url="https://example.com",
            kind=SourceKind.SHOP,
        )


def test_crawl_interval_below_minimum_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceSeed(
            id="x",
            display_name="x",
            base_url="https://example.com",
            kind=SourceKind.SHOP,
            crawl_interval_sec=60,
        )
