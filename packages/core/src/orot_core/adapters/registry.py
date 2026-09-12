"""어댑터 자동 등록 (블루프린트 §3.1, §6).

`adapters/` 에 `<source_id>.py` 를 두고 `@register` 를 붙이면 그것으로 끝이다.
**이 파일을 고칠 필요는 없다** — 블루프린트 §3.1 의 "새 소스 추가 시 이 파일 외의
코드 변경이 없어야 한다"를 지키기 위한 구조다.
"""

import importlib
import pkgutil
from typing import Final

import structlog

from orot_core.adapters.base import MIN_CRAWL_INTERVAL_SECONDS, SourceAdapter

log = structlog.get_logger(__name__)

# 어댑터가 아닌 모듈. 자동 임포트 대상에서 제외한다.
_NON_ADAPTER_MODULES: Final = frozenset({"base", "registry"})

_REGISTRY: dict[str, type[SourceAdapter]] = {}
_loaded = False


class AdapterRegistrationError(Exception):
    """어댑터 등록이 규칙을 어겼을 때."""


def register[AdapterT: type[SourceAdapter]](cls: AdapterT) -> AdapterT:
    """어댑터 클래스를 등록하는 데코레이터.

    잘못된 어댑터는 **임포트 시점에 즉시** 실패시킨다. 크롤이 시작된 뒤
    조용히 0건을 수집하는 것보다 기동이 실패하는 편이 낫다.
    """
    source_id = getattr(cls, "source_id", None)
    if not source_id or not isinstance(source_id, str):
        msg = f"{cls.__name__} 에 source_id 가 없습니다."
        raise AdapterRegistrationError(msg)

    # CLAUDE.md §4: source_id 는 소문자 ASCII 슬러그.
    if not source_id.isascii() or not all(
        c.islower() or c.isdigit() or c == "_" for c in source_id
    ):
        msg = f"source_id 는 소문자 ASCII 슬러그여야 합니다: {source_id!r}"
        raise AdapterRegistrationError(msg)

    if source_id in _REGISTRY and _REGISTRY[source_id] is not cls:
        msg = (
            f"source_id 가 중복되었습니다: {source_id!r} "
            f"({_REGISTRY[source_id].__name__} vs {cls.__name__})"
        )
        raise AdapterRegistrationError(msg)

    interval = getattr(cls, "crawl_interval_seconds", None)
    if not isinstance(interval, int) or interval < MIN_CRAWL_INTERVAL_SECONDS:
        # 블루프린트 §3.4 의 예의 있는 크롤 규칙을 코드가 강제한다.
        msg = (
            f"{source_id}: crawl_interval_seconds 는 "
            f"{MIN_CRAWL_INTERVAL_SECONDS} 이상이어야 합니다 (현재 {interval!r})."
        )
        raise AdapterRegistrationError(msg)

    _REGISTRY[source_id] = cls
    log.debug("adapter.registered", source_id=source_id, adapter=cls.__name__)
    return cls


def load_adapters(*, force: bool = False) -> None:
    """`adapters` 패키지의 모듈을 모두 임포트해 등록을 유발한다.

    어댑터가 하나도 없어도 정상 동작한다 (T-004 인수 조건).
    """
    global _loaded
    if _loaded and not force:
        return

    package = importlib.import_module("orot_core.adapters")
    for module in pkgutil.iter_modules(package.__path__):
        if module.name in _NON_ADAPTER_MODULES or module.name.startswith("_"):
            continue
        importlib.import_module(f"orot_core.adapters.{module.name}")

    _loaded = True
    log.info("adapters.loaded", count=len(_REGISTRY), source_ids=sorted(_REGISTRY))


def available_source_ids() -> list[str]:
    """등록된 소스 ID 목록."""
    load_adapters()
    return sorted(_REGISTRY)


def get_adapter(source_id: str) -> SourceAdapter:
    """소스 ID 로 어댑터 인스턴스를 얻는다."""
    load_adapters()
    try:
        cls = _REGISTRY[source_id]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(없음)"
        msg = f"등록되지 않은 source_id: {source_id!r}. 사용 가능: {known}"
        raise KeyError(msg) from None
    return cls()


def _reset_for_testing() -> None:
    """테스트 전용 — 레지스트리를 비운다."""
    global _loaded
    _REGISTRY.clear()
    _loaded = False
