# 문서 정합성 점검 — 2026-09-11

현재 작업 트리의 **실행 코드·라우터·ORM·마이그레이션·Compose·Makefile**을 기준으로 문서를 대조했다.
구현을 바꾸어 옛 명세에 맞추지 않고, 문서를 현재 구현에 맞게 수정했다. 미래 계획은 삭제하지 않고
미구현임을 명시했다. 기존 작업 중인 코드 변경은 유지했다.

## 발견한 충돌과 정정

| 주제 | 기존 설명 | 확인한 구현과 정정 | 근거 |
|---|---|---|---|
| 현재 단계 | README의 M0·healthz만 구현 | M1 수동 일정과 M2 Web Push 동작, 자동 수집은 미연결 | [API 진입점](../apps/api/src/orot_api/main.py), [스케줄러](../apps/collector/src/orot_collector/scheduler.py) |
| 문서 우선순위 | 오래된 블루프린트가 실제 동작보다 우선 | 현재 동작은 소스·마이그레이션·설정 우선, 문서 정정; 계획은 별도 표시 | AGENTS·CLAUDE·블루프린트 §0 |
| 실행 환경 | EC2·GHCR·SSH 배포가 현재 구성처럼 표기 | Mac mini/colima·Compose·Funnel 공개 테스트, T-012 CI 구현·자동 배포 없음 | [Compose](../compose.yaml), [운영 오버레이](../compose.prod.yaml) |
| 리로드·설정 | 모든 웹 소스 마운트, 재시작으로 환경 반영 | 개발 웹만 마운트, production 웹 재빌드, API reload 유지, collector 재시작, 환경은 컨테이너 재생성 | Compose 두 파일 |
| API 계약 | 검색·워치리스트·JWT·metrics까지 구현된 목록, 잘못된 상세 응답 | 구현된 19개 메서드/경로만 현재 API로 표기; 상세는 artist_name·links | [라우터](../apps/api/src/orot_api/routers/), [스키마](../apps/api/src/orot_api/schemas/release.py) |
| 피드 | 등록순/이벤트순 혼용, RSS와 동일 질의 | recent는 updated_at, imminent는 일정순. RSS와 최신 이벤트 도우미만 공유 | [피드](../apps/api/src/orot_api/routers/feed.py), [RSS](../apps/api/src/orot_api/routers/rss.py) |
| DB 커밋 | 응답 후 커밋 | 함수 범위 의존성으로 응답 전 커밋 | [deps.py](../apps/api/src/orot_api/deps.py) |
| 삭제·저장 정책 | 공개 이력이 있으면 삭제 불가, 이력 무조건 보존 | 비공개 발매 삭제 가능; 연결 listings 등 제한. 삭제 시 이벤트·배송 제거. 일정+links PATCH는 원자적 | [admin.py](../apps/api/src/orot_api/routers/admin.py) |
| 배송 보장 | UNIQUE 하나로 중복 발송 완전 방지 | 배송 행 중복 방지+잠금+SENT 재처리 제외. 외부 전송/커밋 사이 장애의 중복 가능성 남음 | [notifications.py](../packages/core/src/orot_core/notifications.py) |
| 재시도·우선순위 | T-116 전부 미구현, 별도 우선순위/요약 큐 | 최대 3회 재시도·404/410 비활성화 구현. 공유 60초 tick/500건, Slack 운영자 경보 구현(ADR-0008) | notifications.py, [push_sender.py](../apps/collector/src/orot_collector/push_sender.py) |
| 공개 URL | PUBLIC_API_URL·내부 API 주소로 구독 | PUBLIC_WEB_URL을 세 서비스에 전달, 웹 고정 RSS/ICS 중계 | [구독 화면](../apps/web/app/subscribe/page.tsx), [환경 예시](../.env.example) |
| 클라이언트·화면 | 생성 TypeScript 강제, 없는 검색/아티스트/커버 UI | 현재 api.ts는 수기 타입; 피드·상세·캘린더·구독만 구현 | [api.ts](../apps/web/lib/api.ts), [웹 앱](../apps/web/app/) |
| 소스 구조·CLI | 없는 pipeline/resolver/review-merges 등을 현재 구조로 안내 | 실제 구조와 계획 경로 분리, seed는 sources만, dry-run은 실제 네트워크 요청 | [CLI](../apps/collector/src/orot_collector/cli.py), [core](../packages/core/src/orot_core/) |
| 수집 안전망 | DB 자동 비활성화·운영자 알람·해시 생략이 동작한다고 표기 | 차단 시 CLI 종료, validators 메모리 캐시, 해시 계산만 구현. 나머지는 M3 계획 | [fetcher.py](../apps/collector/src/orot_collector/fetcher.py) |
| 테스트·관측 | testcontainers·카나리·Prometheus·Sentry·CI가 현재 구현 | fixture/mock 테스트, 격리 DB 검증과 T-012 CI, 로그·health·Slack 장애 알림 구현 | [Python 테스트](../apps/api/tests/), [웹 테스트](../apps/web/tests/) |
| 백업·호스트 상태 | 디스크 밖 백업·LaunchAgent 등록을 저장소의 보장으로 서술 | 기본 백업은 프로젝트 내부. 자동 실행 등록은 호스트에서 별도 확인. 복구는 압축 검사 후 단일 SQL 트랜잭션 | [Makefile](../Makefile), [infra](../infra/) |
| 데이터 정리 | 제목 LIKE '__%'로 테스트 데이터 삭제 예시 | `_`는 와일드카드이므로 위험한 예시 제거. 격리/롤백 우선, 해당 실행의 정확한 ID로 제한 | CLAUDE §2, AGENTS |
| 과거 점검 기록 | 보안 보고서의 '아직 미공개'가 현재처럼 읽힘 | 당시 기록으로 표시하고 후속 실행 보고서로 연결 | [보안 보고서](security-review.md), [실행 보고서](runtime-review.md) |

## 수정 문서

- [CLAUDE.md](../CLAUDE.md), [AGENTS.md](../AGENTS.md)
- [한국어 블루프린트](BLUEPRINT.ko.md), [영어 블루프린트](BLUEPRINT.en.md)
- [README](../README.md), [.env.example](../.env.example)
- [ADR-0005](adr/0005-manual-curation-first.md), [ADR-0006](adr/0006-web-push-first.md), [ADR-0007](adr/0007-same-origin-push-proxy.md)
- [보안 점검 기록](security-review.md)

ADR의 결정 배경은 보존하면서 공개 트리거·M3 시점·Web Push 확정·배송 한계 등 현재와 충돌하는 설명을 정정했다.
웹의 중첩 AGENTS와 CLAUDE는 설치된 Next.js 문서 참조 지침이므로 변경할 충돌이 없었다.

## 검증 방법

- 현재 FastAPI OpenAPI와 양쪽 문서의 API 표를 비교: **19개 메서드/경로 일치** (`/admin` HTML 포함).
- 양쪽 공개 상세 JSON 예시를 현재 ReleaseOut 모델로 검증.
- 양쪽 DDL의 **13개 테이블과 컬럼 집합**을 현재 ORM 메타데이터와 비교.
- 양쪽 현재 디렉터리 트리와 백로그 태스크 ID 순서 일치 확인.
- 문서의 Make 명령 **24개 타깃**, 로컬 링크·현재/미구현 경로·Markdown 코드 블록·섹션 번호와 diff 공백 오류 확인.
- 현재 FastAPI에서 생성한 OpenAPI와 저장된 스냅샷 일치 확인 (서버 기동 없음).

위 최초 점검은 문서 및 환경 변수 예시 정정이었다. 전체 애플리케이션 테스트나 서비스 재빌드·재기동,
실제 DB 조작·푸시 발송은 수행하지 않았다. 운영 중인 호스트 등록 상태와 외부 사이트·법률·요금은
새로 검증했다고 주장하지 않고, 저장소 밖 확인 사항 또는 과거 조사/향후 계획으로 표시했다.


## 후속 갱신: T-012 및 Slack 구현 반영 — 2026-09-11

- [CI 워크플로](../.github/workflows/ci.yml) 추가: PR/main push/수동 실행, Python 3.12와 Node 22의
  독립 작업, PostgreSQL 16 서비스, 작업별 15분 제한, 읽기 권한, 동일 ref의 이전 실행 취소.
- 블루프린트 한·영판의 §2·§6·§9·§10·§11, README, CLAUDE와 ADR-0008을 현재 구현에 맞췄다.
  Slack 장애 알림을 미구현으로 적었던 문구와 구독 만료도 경보를 보낸다는 문구를 정정했다.
  경보 억제·재전송·호스트 중단 감지의 한계를 기록했다. 기존 작업 트리 변경은 보존했다.
- `make lint` 통과. `make test`: **412 passed, 2 xfailed**, 기존 Starlette/httpx 사용 중단 예정 경고 1건.
- 이번 작업 전용 임시 PostgreSQL에서 Alembic head 적용, 통합 시나리오 **9개** 및 스키마 롤백 통과.
  운영 DB와 분리하고 영구 볼륨 없이 실행했다. 실제 Push/Slack 발송은 없다.
- 웹 lint 및 Node 테스트 **19개** 통과. 호스트 `npm run build`는 Turbopack의 로컬 포트 생성 제한으로
  실패했으나, 현재 소스로 만든 별도 Linux/Node 22 컨테이너에서 네트워크 없이 lint·19개 테스트·
  `npm run build`를 재실행하여 모두 통과했다. 운영 웹은 재빌드·재기동하지 않았다.
- actionlint로 워크플로 문법·식 검증 통과. 양쪽 백로그 ID 순서, 수정 문서의 로컬 링크와
  `git diff --check`를 확인했다.
- GitHub hosted runner 실행은 아직 확인하지 않았다. 커밋·push·배포·필수 체크 설정은 수행하지 않았다.

워크플로 작성 기준: [GitHub PostgreSQL 서비스 안내](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers),
[checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python),
[setup-node](https://github.com/actions/setup-node)의 공식 문서.


## OROT 이름 통일 — 2026-09-12

서비스명·화면/PWA·Push/Slack 제목·RSS/ICS 표시명·OpenAPI·Python 패키지·Docker/CI 기본값·
Makefile·운영 스크립트·문서 경로를 OROT/orot 기준으로 통일했다. 소스 패키지는
`orot_core`, `orot_api`, `orot_collector`이며, 운영 스크립트는 `orot-start.sh`, `orot-backup.sh`다.
최종 프로젝트 경로는 `/Users/jaehyeon/PersonalProjects/OROT`이다.

두 번째 전체 검색에서 이전 서비스명은 기존 RSS GUID/iCalendar UID 호환성 상수와 해당
회귀 테스트에만 남는다(추적 소스 기준). 음반 재질·외부 사이트의 vinyl 표현과 원본 fixture는 보존한다.
기존 DB 이름·사용자·물리 볼륨·키체인 식별자는 비공개 로컬 설정으로 계속 연결하고,
신규 설치 기본값과 Compose 프로젝트 이름은 orot으로 사용한다. VAPID 키·공개 URL은 보존한다.

검증: Python lint·core mypy·412 tests 통과(기존 2 xfailed), 웹 lint·19 tests 통과,
Docker Linux production build 통과. 호스트 Turbopack 빌드는 로컬 포트 제한으로 실패했다.
OROT 임시 DB 마이그레이션·통합 시나리오 9개·롤백, actionlint·Compose config·셸 구문·
문서 링크·한영 백로그 ID 대조도 통과했다. 운영 DB는 이동 전에 별도 백업했다.
폴더 이동에는 venv 절대 경로·호스트 LaunchAgent 경로와 이름·Compose 마운트의 갱신이 필요하다.
이름 변경은 유지보수 작업이며 새 백로그 ID를 만들지 않는다.

폴더 이동 후 Python import·collector CLI, 운영 healthz·API 제목·PWA 이름·웹 제목을 확인했다.
Compose 프로젝트와 컨테이너는 orot으로 전환했으며 기존 DB 볼륨·등록 일정/구독 수가 보존되었다.
호스트 자동 시작·백업 LaunchAgent도 com.orot 이름과 새 경로로 갱신했다.
기존 DB의 테스트 발매 제목 2건에는 과거 서비스명이 있으나 등록 데이터이므로 수정하지 않았다.


## 이름·의존성 재점검 및 caching 타입 오류 수정 — 2026-09-12

추적 소스·설정·문서와 설치된 Python 패키지/실행 스크립트의 경로를 다시 확인했다.
이전 서비스명은 구독 ID 호환성 상수·그 테스트와 설명, 비공개 기존 DB/백업 연결 설정에만 남는다.
음반 재질·외부 원문과 과거 백업 데이터는 이름 변경 대상이 아니다.

`caching.py`의 `list[type(payload[0])]`는 실행 시 계산한 타입을 타입 인수에 사용하여
mypy의 `Type expected within [...]` 오류를 일으켰다. 각 모델의 `model_dump_json()`으로
JSON 배열을 구성하도록 수정했다. 빈 목록, 기존 JSON/ETag 유지, 제외 필드,
서로 다른 모델의 필드 및 사용자 지정 직렬화에 대한 회귀 테스트 3개를 추가했다.
기존 core 전용 mypy와 별도로 해당 API 파일도 검사해 통과했다.

- 로컬 venv와 운영 API/collector의 `pip check` 모두 통과. 이전 이름의 Python 배포 패키지 없음.
- `make lint`, Python **415 passed / 2 xfailed**, 웹 lint·**19 tests**, 호스트·Linux 빌드 통과.
  초기 호스트 검증의 캐시/.next 쓰기 제한은 실행 권한을 조정해 재검증했다.
- `npm ci` 성공. 누락/버전 충돌은 없으나 선택적 sharp/WASM 관련 패키지 6개가 `extraneous`로
  표시된다. 깨끗한 재설치 후에도 재현되어 폴더 이동 잔여물로 보지 않는다.
  의존성 버전과 잠금 파일은 변경하지 않았다.
- Starlette의 httpx 사용 중단 예정 경고와 ESLint 9 지원 종료 설치 경고는 남아 있다.
  이번 작업은 이름/호환성 점검이며 의존성 메이저 업그레이드는 수행하지 않았다.
- 호스트 Node는 25, CI·Docker는 22이므로 개발 환경도 Node 22 사용을 권장한다.
  com.orot.stack/com.orot.backup의 새 경로 등록을 확인했고, 운영 컨테이너들은 실행 중이다.


## 타입 정보·피드 ID 갱신 및 실제 Push 검증 — 2026-09-12

대중 배포 전 사용자의 명시적 결정에 따라 위 점검에서 보존했던 RSS GUID/iCalendar UID의
namespace도 `OROT`으로 변경했다. 이후 생성되는 ID는 `event-52@OROT`,
`release-35@OROT`과 같은 namespace를 사용한다. DB 마이그레이션은 필요하지 않으며,
기존 구독 클라이언트에서는 ID 변경으로 항목을 새 항목으로 인식할 수 있다.
앞선 절의 이전 namespace 보존 설명은 당시 점검 기록이며 현재 동작은 이 절을 따른다.

API와 collector에 `py.typed` 및 setuptools package-data 설정을 추가했다. core는 이미
marker가 있었다. 정상 wheel을 빌드하여 두 marker가 배포 파일에도 포함됨을 확인했다.
테스트의 `import-untyped` 진단을 재현한 뒤 해소했으며, 확장 검사에서 발견한 SQLAlchemy
타입 좁히기, Pydantic 입력 타입, 캐시 테스트 입력 타입 등도 정정했다.

- `make lint` 통과, Python **418 passed / 2 xfailed**. 기존 Starlette/httpx 경고는 남는다.
- API·collector·core 테스트 파일 **25개**의 mypy 검사 통과
  (`--follow-imports=silent`, 전체 애플리케이션의 strict 타입 검사를 의미하지 않음).
- 소스·문서·설정 재검색에서 이전 서비스명 잔여 없음. 비공개 기존 DB/볼륨/백업 연결 설정,
  과거 저장 데이터, 의존성·빌드 캐시 및 음반 재질/외부 원문은 구분하여 보존했다.
- 실행 중 서비스의 RSS GUID 3개와 ICS UID 4개 모두 `@OROT`임을 HTTP 응답으로 확인했다.
- 사용자 승인으로 새 더미 일정 **#35** (`OROT 더미 전송 테스트 — 20260912T055455Z`)을
  실제 관리 API로 생성·공개했다. 이벤트 **#52**, 활성 구독 **224·225** 모두 정상 스케줄러를
  통해 **SENT**, 각 **1회 시도**로 기록됐다(2026-09-12 05:55:30 UTC).
  이는 Push 서비스 전송 성공이며 기기 화면의 알림 표시는 별도 확인 대상이다.
- 후속 날짜 알림을 방지하도록 더미에는 발매/예약 날짜를 지정하지 않았다. 알림 링크 확인을 위해
  일정은 유지했다. 생성 기록은 로컬 `backups/orot-live-dummy-20260912.jsonl`에 남겼다.
  Slack 테스트 발송은 수행하지 않았다.


## 운영 식별자까지 OROT 이전 — 2026-09-12

사용자가 서비스 일시 중단과 DB·볼륨·백업·키체인 이전을 명시적으로 승인했다.
앞선 기록의 기존 식별자 보존 방침은 이 이전으로 대체한다.

- `.env`의 DB 사용자/이름은 `orot`, 볼륨은 `orot_postgres_data`, 백업 키체인 서비스는
  `orot-env-backup`, iCloud 백업 폴더는 `OROT`으로 변경했다. DB 비밀번호는 새 무작위
  값으로 교체하고 DATABASE_URL에 반영했다. VAPID·관리자·Slack 키는 유지했다.
- 쓰기 서비스를 중단하고 DB를 덤프한 뒤 새 볼륨에 복원했다. 이전 전후 **14개 테이블**의
  행 수가 모두 일치했다(발매 4, 아티스트 7, 기기 토큰 4, 이벤트 16, 배송 기록 24).
  이후 이전 이름이 남은 테스트 아티스트 1건의 표시명/정규화 이름을 수정했다.
- API·collector·web을 새 환경으로 재생성했다. Postgres/API healthy, 웹 HTTP 200,
  `/healthz`의 DB 연결 정상. 실행 컨테이너 환경과 `.env`의 이전 이름 잔여 없음.
- 새 키체인·새 경로로 `.env` 암호화 백업 성공. 복호화 결과가 현재 `.env`와 바이트 단위로
  일치함을 확인했다. 비밀 값은 출력하지 않았다.
- 소스·문서·로컬 도구 설정·LaunchAgents·venv 실행 파일과 설치 메타데이터를 점검했다.
  `.claude/settings.local.json`에 남은 이전 프로젝트 경로를 수정했다. 로컬/API/collector
  `pip check`와 `git diff --check` 통과. 현재 Git 원격 URL에도 이전 브랜드 잔여 없음.
- 기존 볼륨·키체인 항목·과거 백업은 복구 자료로 보존한다. 이전 직전 설정(권한 600),
  DB 덤프 및 행 수 대조는 로컬 `backups/orot-env-migration-20260912-175532/`에 있다.
  현재 서비스는 새 식별자만 사용한다. 음반 재질과 외부 사이트 원문 속 vinyl은 유지한다.
- 이번 검증에서는 실제 Push/Slack 시험 알림을 추가 발송하지 않았다.


## 외부 라이브러리 타입 진단 및 검사 범위 확대 — 2026-09-12

APScheduler의 두 import와 pywebpush의 `import-untyped`를 확인했다. 루트 `mypy.ini`에서
두 라이브러리만 `follow_untyped_imports`로 실제 소스를 분석하도록 했다. 전체 오류 무시나
site-packages 변경은 하지 않았다. 편집기는 같은 설정과 프로젝트 환경의 mypy를 사용한다.
개발 의존성에 mypy 최소 버전 1.15와 collector의 types-requests를 명시했다.

확장 검사에서 발견한 requests Session 재정의, pywebpush의 문자열 반환 가능성,
SQLAlchemy 페이지네이션 비교, 어댑터 생성자 계약을 정정했다. 리다이렉트 차단은
PreparedRequest 전송 단계에서 유지한다. core strict 검사에서 DB ping의 bool 반환도 명시했다.
`make lint`와 이를 호출하는 CI는 이제 전체 소스·테스트 및 별도 core strict를 검사한다.
전체 77개 파일의 mypy, core 21개 파일 strict, Ruff 및 Python 418개 테스트 통과
(2 xfailed, 기존 Starlette/httpx 경고). 실제 외부 알림은 시험 발송하지 않았다.
