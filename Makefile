# Vinyl Radar — 개발용 태스크
# CLAUDE.md §3 의 명령 목록과 일치시킬 것.

SHELL := /bin/bash
DC    := docker compose
API   := $(DC) exec -T api
COL   := $(DC) exec -T collector

# 로컬(컨테이너 밖) 파이썬. CLAUDE.md §2 규칙 7 — 반드시 프로젝트 venv 를 쓴다.
VENV       := venv
VENV_PY    := $(VENV)/bin/python
PKGS       := packages/core apps/api apps/collector

.DEFAULT_GOAL := help
.PHONY: help up down prod prod-down prod-logs backup-env backup-env-setup restore-env backups-env backup-prune logs ps migrate migrate-down migrate-status revision seed backup restore backups test lint format openapi venv install clean healthz

help:  ## 사용 가능한 타깃 목록
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ─── 컨테이너 ───────────────────────────────────────────────────
.env:
	@test -f .env || { echo "!! .env 가 없습니다. 'cp .env.example .env' 를 먼저 실행하십시오."; exit 1; }

up: .env  ## 로컬 스택 기동 (postgres + api + collector)
	$(DC) up -d --build
	@echo "-- 서비스 준비 대기 중..."
	@$(MAKE) --no-print-directory healthz

down:  ## 스택 종료 (데이터 볼륨은 유지)
	$(DC) down

# ─── 상시 운영 (T-120) ───────────────────────────────────────────
# 개발용 `up` 과 다른 점: 웹이 production 빌드로 올라가고 ENVIRONMENT=production 이라
# settings.py 가 기본 운영자 키를 거부한다. 포트는 어느 쪽이든 127.0.0.1 에만 열린다.
PROD := docker compose -f compose.yaml -f compose.prod.yaml

prod: .env  ## 상시 운영 모드로 기동 (웹 production 빌드)
	$(PROD) up -d --build
	@echo "-- 서비스 준비 대기 중..."
	@$(MAKE) --no-print-directory healthz

prod-down:  ## 상시 운영 스택 종료 (데이터 볼륨은 유지)
	$(PROD) down

prod-logs:  ## 상시 운영 스택 로그
	$(PROD) logs -f --tail=100

logs:  ## 전체 로그 추적
	$(DC) logs -f

ps:  ## 컨테이너 상태
	$(DC) ps

healthz:  ## /healthz 200 확인 (T-001 인수 조건)
	@for i in $$(seq 1 30); do \
		code=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$${API_HOST_PORT:-8000}/healthz || true); \
		if [ "$$code" = "200" ]; then \
			echo "OK  /healthz -> 200"; \
			curl -s http://localhost:$${API_HOST_PORT:-8000}/healthz; echo; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "FAIL /healthz 가 200 을 반환하지 않았습니다 (마지막 코드: $$code)"; \
	$(DC) logs --tail=50 api; \
	exit 1

# ─── DB ────────────────────────────────────────────────────────
migrate:  ## Alembic 마이그레이션 적용 (alembic upgrade head)
	$(API) alembic -c /app/alembic.ini upgrade head

migrate-down:  ## 직전 마이그레이션 1단계 되돌리기
	$(API) alembic -c /app/alembic.ini downgrade -1

migrate-status:  ## 현재 리비전 및 이력
	$(API) alembic -c /app/alembic.ini current
	$(API) alembic -c /app/alembic.ini history --indicate-current

revision:  ## 모델 변경분으로 리비전 자동 생성 (m="메시지")
	@test -n "$(m)" || { echo "사용법: make revision m=\"add xxx\""; exit 1; }
	$(API) alembic -c /app/alembic.ini revision --autogenerate -m "$(m)"

seed:  ## sources 시드 적재 (재실행 가능). 아티스트 별칭은 T-019 에서 추가
	$(COL) collector seed

# ─── 백업 ───────────────────────────────────────────────────────
# 볼륨은 "실수로 안 지워진다"를 보장할 뿐이다. 디스크 고장·인스턴스 삭제·
# 잘못된 마이그레이션은 볼륨으로 막지 못한다. 백업이 유일한 보험이다.
BACKUP_DIR := backups
# .env 를 단일 출처로 삼는다 (compose 와 같은 값).
PG_USER = $(shell sed -n 's/^POSTGRES_USER=//p' .env 2>/dev/null | head -1)
PG_DB   = $(shell sed -n 's/^POSTGRES_DB=//p' .env 2>/dev/null | head -1)

backup: .env  ## DB 전체를 backups/ 에 덤프 (gzip)
	@mkdir -p $(BACKUP_DIR)
	@user="$${PG_USER:-$(PG_USER)}"; db="$${PG_DB:-$(PG_DB)}"; 	 user=$${user:-vinyl}; db=$${db:-vinyl_radar}; 	 file="$(BACKUP_DIR)/$$db-$$(date +%Y%m%d-%H%M%S).sql.gz"; 	 $(DC) exec -T postgres pg_dump -U "$$user" -d "$$db" --clean --if-exists 	   | gzip > "$$file" || { rm -f "$$file"; echo "!! 백업 실패"; exit 1; }; 	 test -s "$$file" || { rm -f "$$file"; echo "!! 백업이 비어 있습니다"; exit 1; }; 	 echo "저장됨: $$file ($$(du -h "$$file" | cut -f1))"

restore: .env  ## FILE=backups/xxx.sql.gz 에서 복구 — **기존 데이터를 덮어씁니다**
	@test -n "$(FILE)" || { echo "사용법: make restore FILE=backups/xxx.sql.gz"; 	  ls -1t $(BACKUP_DIR)/*.sql.gz 2>/dev/null | head -5 | sed 's/^/  후보: /'; exit 1; }
	@test -f "$(FILE)" || { echo "!! 파일이 없습니다: $(FILE)"; exit 1; }
	@echo "!! $(FILE) 로 복구하면 현재 DB 내용을 덮어씁니다."
	@printf '   계속하려면 yes 를 입력하세요: '; read ans; test "$$ans" = "yes" || { echo "취소함"; exit 1; }
	@user="$${PG_USER:-$(PG_USER)}"; db="$${PG_DB:-$(PG_DB)}"; 	 user=$${user:-vinyl}; db=$${db:-vinyl_radar}; 	 gunzip -c "$(FILE)" | $(DC) exec -T postgres psql -U "$$user" -d "$$db" -q 	 && echo "복구 완료: $(FILE)"

# ─── .env 암호화 백업 (T-120) ────────────────────────────────────
# `backup` 은 DB 만 덤프한다. 그 DB 를 쓸모 있게 만드는 VAPID 개인키는 .env 에만
# 있어서, 디스크가 죽으면 **등록된 푸시 구독이 전부 무효**가 된다.

backup-env-setup: ## .env 백업 암호를 맥 키체인에 저장 (최초 1회, 직접 입력)
	@echo "이 암호로 .env 백업을 암호화합니다."
	@echo "**반드시 비밀번호 관리자에도 같이 저장하십시오** — 키체인은 이 디스크에"
	@echo "있으므로, 디스크가 죽으면 키체인도 함께 사라집니다."
	@security add-generic-password -U -s vinyl-radar-env-backup -a "$$USER" -w
	@echo "키체인에 저장했습니다."

backup-env: ## .env 를 암호화해 백업 (내용이 안 바뀌었으면 건너뜀)
	@infra/env-backup.sh

restore-env: ## FILE=<...env.enc> 에서 .env 복구 — **기존 .env 를 덮어씁니다**
	@test -n "$(FILE)" || { echo "!! 사용법: make restore-env FILE=backups/env/xxx.env.enc"; exit 1; }
	@infra/env-restore.sh "$(FILE)"

backups-env: ## .env 백업 목록
	@dir="$$(infra/env-backup.sh --where)"; \
	 ls -lht "$$dir"/*.env.enc 2>/dev/null || echo "백업이 없습니다 ($$dir)"

backup-prune: ## 백업을 최근 30개만 남기고 정리 (자동 백업이 디스크를 채우지 않도록)
	@ls -1t $(BACKUP_DIR)/*.sql.gz 2>/dev/null | tail -n +31 | while read f; do \
	   echo "삭제: $$f"; rm -f "$$f"; \
	 done; echo "남은 백업: $$(ls -1 $(BACKUP_DIR)/*.sql.gz 2>/dev/null | wc -l | tr -d ' ')개"

backups: ## 저장된 백업 목록
	@ls -1lht $(BACKUP_DIR)/*.sql.gz 2>/dev/null | awk '{print "  "$$5"\t"$$9}' \
	  || echo "  백업이 없습니다. 'make backup' 을 먼저 실행하세요."

# ─── 로컬 개발 (컨테이너 밖) ──────────────────────────────────────
venv:  ## 프로젝트 venv 생성
	@test -d $(VENV) || python3.12 -m venv $(VENV)
	@echo "생성됨: $(VENV)  —  'source $(VENV)/bin/activate'"

install: venv  ## 모든 패키지를 editable 로 설치
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e "packages/core[dev]"
	$(VENV_PY) -m pip install -e "apps/api[dev]"
	$(VENV_PY) -m pip install -e "apps/collector[dev]"

test:  ## pytest (packages/core, apps/api, apps/collector)
	$(VENV_PY) -m pytest $(PKGS) -q

lint:  ## ruff check + format --check + mypy(core strict)
	$(VENV_PY) -m ruff check $(PKGS)
	$(VENV_PY) -m ruff format --check $(PKGS)
	$(VENV_PY) -m mypy packages/core/src

format:  ## ruff format 적용
	$(VENV_PY) -m ruff format $(PKGS)
	$(VENV_PY) -m ruff check --fix $(PKGS)

openapi:  ## docs/api/openapi.json 재생성 (T-010 에서 의미를 갖는다)
	@mkdir -p docs/api
	$(VENV_PY) -c "import json,pathlib; from vinyl_api.main import app; \
pathlib.Path('docs/api/openapi.json').write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False))"
	@echo "생성됨: docs/api/openapi.json"

clean:  ## 캐시 정리
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache
