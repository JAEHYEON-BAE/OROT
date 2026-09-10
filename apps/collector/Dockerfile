# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY packages/core /app/packages/core
RUN pip install --no-cache-dir -e /app/packages/core

# 마이그레이션은 저장소 최상위에 있다 (블루프린트 §6). 이미지에 포함시켜야
# `docker compose exec <svc> alembic upgrade head` 가 동작한다.
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations

COPY apps/collector /app/apps/collector
RUN pip install --no-cache-dir -e "/app/apps/collector[dev]"

# 상주 스케줄러 (T-111). 1분마다 시각 기반 이벤트를 만든다.
# `docker compose exec collector collector <명령>` 은 그대로 쓸 수 있다.
CMD ["collector", "scheduler"]
