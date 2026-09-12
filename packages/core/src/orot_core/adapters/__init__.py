"""소스 어댑터.

새 소스를 추가하려면 이 디렉터리에 `<source_id>.py` 를 만들고
어댑터 클래스에 `@register` 를 붙인다. 그 외 코드는 건드리지 않는다 (블루프린트 §3.1).
새 소스 추가 절차 전체는 CLAUDE.md §5 를 따른다.
"""

from orot_core.adapters.base import (
    MIN_CRAWL_INTERVAL_SECONDS,
    PageFetcher,
    RawItem,
    SourceAdapter,
    StockStatus,
)
from orot_core.adapters.registry import (
    AdapterRegistrationError,
    available_source_ids,
    get_adapter,
    load_adapters,
    register,
)

__all__ = [
    "MIN_CRAWL_INTERVAL_SECONDS",
    "AdapterRegistrationError",
    "PageFetcher",
    "RawItem",
    "SourceAdapter",
    "StockStatus",
    "available_source_ids",
    "get_adapter",
    "load_adapters",
    "register",
]
