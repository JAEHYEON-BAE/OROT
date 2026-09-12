"""structlog 기반 JSON 로깅 설정.

블루프린트 §9.4: 파서의 무음 실패 감지가 핵심 요구사항이므로
로그는 기계가 읽을 수 있어야 한다.
"""

import logging
import sys

import structlog

from orot_core.settings import get_settings


def configure_logging() -> None:
    """프로세스 시작 시 1회 호출한다."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    # 로컬은 사람이 읽기 쉽게, 그 외에는 JSON.
    if settings.environment == "local":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
