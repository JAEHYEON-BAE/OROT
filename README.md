# OROT

국내 바이닐의 **발매 일정과 예약판매 기간을 구독하고 알림을 받는 서비스**입니다.
현재는 운영자가 일정을 입력하고, 사용자는 웹 피드·캘린더·RSS·iCalendar·Web Push로 확인합니다.
M1 기능과 M2 시각 기반 알림이 구현되어 있으며, 자동 수집은 M3까지 연결하지 않습니다.

- [한국어 블루프린트](docs/BLUEPRINT.ko.md) / [영어판](docs/BLUEPRINT.en.md)
- [에이전트 지침](AGENTS.md) / [프로젝트 맥락](CLAUDE.md)
- [아키텍처 결정](docs/adr/) / [소스 조사 기록](docs/adapters/)
- [실행 흐름 점검](docs/runtime-review.md) / [문서 정합성 점검](docs/documentation-review.md)

문서와 현재 소스·마이그레이션·실행 설정이 충돌하면 구현을 기준으로 문서를 갱신합니다.
계획된 검색·계정·워치리스트·iOS 앱·클라우드 배포는 아직 없습니다. GitHub Actions CI는 T-012로 구현되어 있습니다.

## 실행

Docker 엔진과 Compose가 필요합니다. 현재 macOS 테스트 환경은 colima를 사용합니다.

```bash
# 최초 설정에만 사용합니다. 기존 .env는 보존합니다.
cp -n .env.example .env
# .env의 ADMIN_API_KEY를 설정한 뒤 실행합니다.
make up        # postgres + api + collector + 개발 웹
make migrate   # 최초 실행 또는 새 마이그레이션 적용 시
make seed      # sources 시드만 적재
```

공개 테스트용 웹 빌드는 `make prod`입니다. 이 명령은 `compose.prod.yaml`을 추가 적용하며
staging/production 설정에서는 기본 관리자 키와 32자 미만 키를 거부합니다.
공개 테스트에는 충분한 무작위성을 가진 비밀 키를 사용합니다.

| 주소 | 내용 |
|---|---|
| http://localhost:3000 | 피드 |
| http://localhost:3000/calendar | 월간 캘린더 |
| http://localhost:3000/subscribe | 푸시·RSS·캘린더 구독 |
| http://localhost:3000/v1/releases.ics | 공개 웹을 통한 iCalendar |
| http://localhost:3000/v1/feed.rss | 공개 웹을 통한 RSS |
| http://localhost:8000/admin | 운영자 등록·편집·공개 관리 |
| http://localhost:8000/docs | API 문서 |
| http://localhost:8000/healthz | DB 연결 포함 헬스체크 |

포트 기본값은 3000/8000/5432이며 모두 loopback에 바인딩됩니다. 현재 공개 시험 주소는
`https://jaehyeonui-macmini.tail598a5f.ts.net`입니다. 실제 Funnel 설정은 `tailscale funnel status`로 확인합니다.
Funnel은 웹 포트만 공개하고 관리자/API·DB 포트는 공개하지 않습니다.

`.env`의 `PUBLIC_WEB_URL`을 공개 웹 주소로 설정해야 알림과 구독 링크가 휴대폰에서 열립니다.
웹 내부 API 호출에는 Compose가 `API_BASE_URL=http://api:8000`을 전달합니다.
`PUBLIC_API_URL`은 사용하지 않습니다. Web Push에는 VAPID 키 쌍과 연락처인 `VAPID_SUBJECT`가 필요합니다.

```bash
make ps
make logs
make prod-logs
make down      # 컨테이너 종료, DB 볼륨 유지
```

API는 두 모드 모두 소스 마운트와 `--reload`를 사용합니다. collector는 소스 편집 후 재시작해야 합니다.
production 웹은 소스 마운트가 없으므로 재빌드해야 합니다. `.env` 변경은 단순 restart로 반영되지 않으며
사용 중인 Compose 오버레이로 컨테이너를 재생성해야 합니다. `make prod`는 재빌드·재생성을 수행합니다.

## 개발과 검증

```bash
make install   # venv/ + 세 Python 패키지 editable 설치
make lint      # Ruff, 포맷, core mypy
make test      # Python fixture/mock 중심 테스트
make openapi   # API 계약 스냅샷 생성

cd apps/web
npm ci
npm run lint
node --test tests/*.test.mjs
npm run build
```

웹 API 타입은 `apps/web/lib/api.ts`의 수기 타입이며 생성 클라이언트는 없습니다.
[T-012 CI](.github/workflows/ci.yml)는 모든 PR·main push·수동 실행에서 다음 두 작업을 수행합니다.

- **Python checks**: Python 3.12, `make install`, `make lint`, `make test`, 임시 PostgreSQL 16 마이그레이션과 9개 격리 통합 시나리오
- **Web checks**: Node 22, `npm ci`, lint·Node 회귀 테스트·production build

CI는 운영 비밀이나 실제 알림 발송을 사용하지 않습니다. GitHub 실행 결과는 Actions/PR에서 확인하며,
병합 필수 체크 지정은 저장소 설정에서 별도로 관리합니다. 자동 배포는 포함하지 않습니다.
DB 검증은 마이그레이션된 DB 안에 별도의 ORM 스키마를 만드는
`apps/api/tests/integration_runtime.py`의 격리·롤백·가짜 발송기 방식입니다.
임시 개발 DB에 `DATABASE_URL`을 지정한 뒤 `venv/bin/python -m alembic upgrade head`,
`venv/bin/python apps/api/tests/integration_runtime.py` 순으로 실행할 수 있습니다.
문서만 수정할 때는 경로·명령·API 계약을 대조하며 서비스 기동이나 실제 알림을 필요로 하지 않습니다.

## 주요 구조

| 경로 | 역할 |
|---|---|
| `apps/api/` | 관리자 CRUD, 공개 조회·피드·RSS·ICS, 푸시 구독 |
| `apps/collector/` | 60초 시각 이벤트/배송 스케줄러, Web Push 발송기, 수동 수집 CLI |
| `apps/web/` | Next.js PWA, 피드·캘린더·상세·구독, 같은 출처 중계 |
| `packages/core/` | 설정·DB·ORM·어댑터·시각 이벤트·배송 계획 |
| `migrations/` | Alembic 리비전 |
| `infra/` | Mac 기동 및 DB/.env 백업 스크립트 |
| `docs/` | 현재 계약과 향후 계획을 구분한 문서 |

## 데이터·알림 정책

- 초안은 공개 조회에서 제외합니다. 공개 취소 후 삭제는 가능하지만 연결된 수집 상품 등이 있으면 거부합니다.
  삭제하면 해당 음반의 이벤트·배송 이력도 제거됩니다. 일정 수정은 삭제 대신 옛 이벤트를 무효화합니다.
- 알림은 60초 주기로 생성·발송하며 실패 시 최대 3회 시도합니다. 구독 전 이벤트와 48시간을 지난 이벤트는 보내지 않습니다.
  푸시 서비스 수락과 실제 기기 표시 확인은 다르며, 전송/DB 커밋 사이의 장애에서는 중복 가능성이 남습니다.
- `SLACK_WEBHOOK_URL`을 설정하면 스케줄러 오류·재시도 소진을 운영자에게 알립니다.
  같은 오류 종류는 기본적으로 프로세스당 성공 전송 1회이며, 프로세스 자체 중단은 감지하지 못합니다.
  자세한 동작은 [ADR-0008](docs/adr/0008-operator-failure-alerts.md)을 참고하십시오.
- 실제 시험 알림은 사용자 승인 범위에서만 보냅니다. 기존 더미 데이터도 임의로 지우지 않습니다.
- `make backup`은 DB, `make backup-env`는 `.env`를 백업합니다. 기본 저장 위치는 프로젝트 내부이므로
  디스크 밖 보관은 별도 설정해야 합니다. 복구는 기존 내용을 덮어쓰므로 승인과 사전 백업이 필요합니다.

## 자동 수집의 현재 범위

Fetcher와 gimbab/secondtrack/poclanos 어댑터는 있으나 주기 수집·DB 적재·정규화·병합은 연결되지 않았습니다.
`collector run --source ... --dry-run`은 **실사이트에 요청하고 결과만 출력**하며, DB를 쓰지 않는다는 뜻입니다.
오프라인 테스트로 실행하지 않습니다. `review-merges` 명령은 없습니다.

수집 시에는 robots 준수, 소스별 0.5 req/s·동시 연결 2 이하, 연락처가 포함된 User-Agent,
메타데이터와 원본 링크만 사용, 차단 우회 금지를 지킵니다. 설정 검증과 Fetcher가 일부를 강제하지만
소스 자동 비활성화·수집 장애 운영자 알림·파서 카나리는 아직 없으며 robots 파서 한계는 ADR-0003에 기록되어 있습니다.

전체 명령은 `make help`, 구현과 계획의 구분은 블루프린트 §2·§5·§6·§9·§10을 참고하십시오.


## 이름 규칙

서비스 표기는 **OROT**, 기술 식별자는 `orot`을 사용합니다. Python 패키지는
`orot_core`·`orot_api`·`orot_collector`, 프로젝트 경로는
`/Users/jaehyeon/PersonalProjects/OROT`입니다.
기존 구독의 고정 UID/GUID와 운영 DB·백업 키체인 식별자는 호환성을 위해 보존합니다.
`vinyl`이 음반 재질이나 외부 사이트 원문을 뜻하는 경우에도 변경하지 않습니다.
