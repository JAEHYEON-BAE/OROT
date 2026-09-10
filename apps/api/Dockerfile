# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 공용 코어를 먼저 설치한다 (변경 빈도가 낮아 레이어 캐시가 잘 맞는다).
COPY packages/core /app/packages/core
RUN pip install --no-cache-dir -e /app/packages/core

# 마이그레이션은 저장소 최상위에 있다 (블루프린트 §6). 이미지에 포함시켜야
# `docker compose exec <svc> alembic upgrade head` 가 동작한다.
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations

COPY apps/api /app/apps/api
RUN pip install --no-cache-dir -e "/app/apps/api[dev]"

EXPOSE 8000

# --reload 는 compose 의 command 에서 로컬 개발 시에만 덧붙인다.
CMD ["uvicorn", "vinyl_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
