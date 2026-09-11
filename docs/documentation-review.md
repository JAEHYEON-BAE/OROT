# 문서 정합성 점검 — 2026-09-11

현재 작업 트리의 **실행 코드·라우터·ORM·마이그레이션·Compose·Makefile**을 기준으로 문서를 대조했다.
구현을 바꾸어 옛 명세에 맞추지 않고, 문서를 현재 구현에 맞게 수정했다. 미래 계획은 삭제하지 않고
미구현임을 명시했다. 기존 작업 중인 코드 변경은 유지했다.

## 발견한 충돌과 정정

| 주제 | 기존 설명 | 확인한 구현과 정정 | 근거 |
|---|---|---|---|
| 현재 단계 | README의 M0·healthz만 구현 | M1 수동 일정과 M2 Web Push 동작, 자동 수집은 미연결 | [API 진입점](../apps/api/src/vinyl_api/main.py), [스케줄러](../apps/collector/src/vinyl_collector/scheduler.py) |
| 문서 우선순위 | 오래된 블루프린트가 실제 동작보다 우선 | 현재 동작은 소스·마이그레이션·설정 우선, 문서 정정; 계획은 별도 표시 | AGENTS·CLAUDE·블루프린트 §0 |
| 실행 환경 | EC2·GHCR·SSH 배포가 현재 구성처럼 표기 | Mac mini/colima·Compose·Funnel 공개 테스트, CI/CD는 없음 | [Compose](../compose.yaml), [운영 오버레이](../compose.prod.yaml) |
| 리로드·설정 | 모든 웹 소스 마운트, 재시작으로 환경 반영 | 개발 웹만 마운트, production 웹 재빌드, API reload 유지, collector 재시작, 환경은 컨테이너 재생성 | Compose 두 파일 |
| API 계약 | 검색·워치리스트·JWT·metrics까지 구현된 목록, 잘못된 상세 응답 | 구현된 19개 메서드/경로만 현재 API로 표기; 상세는 artist_name·links | [라우터](../apps/api/src/vinyl_api/routers/), [스키마](../apps/api/src/vinyl_api/schemas/release.py) |
| 피드 | 등록순/이벤트순 혼용, RSS와 동일 질의 | recent는 updated_at, imminent는 일정순. RSS와 최신 이벤트 도우미만 공유 | [피드](../apps/api/src/vinyl_api/routers/feed.py), [RSS](../apps/api/src/vinyl_api/routers/rss.py) |
| DB 커밋 | 응답 후 커밋 | 함수 범위 의존성으로 응답 전 커밋 | [deps.py](../apps/api/src/vinyl_api/deps.py) |
| 삭제·저장 정책 | 공개 이력이 있으면 삭제 불가, 이력 무조건 보존 | 비공개 발매 삭제 가능; 연결 listings 등 제한. 삭제 시 이벤트·배송 제거. 일정+links PATCH는 원자적 | [admin.py](../apps/api/src/vinyl_api/routers/admin.py) |
| 배송 보장 | UNIQUE 하나로 중복 발송 완전 방지 | 배송 행 중복 방지+잠금+SENT 재처리 제외. 외부 전송/커밋 사이 장애의 중복 가능성 남음 | [notifications.py](../packages/core/src/vinyl_core/notifications.py) |
| 재시도·우선순위 | T-116 전부 미구현, 별도 우선순위/요약 큐 | 최대 3회 재시도·404/410 비활성화 구현. 공유 60초 tick/500건, 외부 운영자 경보 미구현 | notifications.py, [push_sender.py](../apps/collector/src/vinyl_collector/push_sender.py) |
| 공개 URL | PUBLIC_API_URL·내부 API 주소로 구독 | PUBLIC_WEB_URL을 세 서비스에 전달, 웹 고정 RSS/ICS 중계 | [구독 화면](../apps/web/app/subscribe/page.tsx), [환경 예시](../.env.example) |
| 클라이언트·화면 | 생성 TypeScript 강제, 없는 검색/아티스트/커버 UI | 현재 api.ts는 수기 타입; 피드·상세·캘린더·구독만 구현 | [api.ts](../apps/web/lib/api.ts), [웹 앱](../apps/web/app/) |
| 소스 구조·CLI | 없는 pipeline/resolver/review-merges 등을 현재 구조로 안내 | 실제 구조와 계획 경로 분리, seed는 sources만, dry-run은 실제 네트워크 요청 | [CLI](../apps/collector/src/vinyl_collector/cli.py), [core](../packages/core/src/vinyl_core/) |
| 수집 안전망 | DB 자동 비활성화·운영자 알람·해시 생략이 동작한다고 표기 | 차단 시 CLI 종료, validators 메모리 캐시, 해시 계산만 구현. 나머지는 M3 계획 | [fetcher.py](../apps/collector/src/vinyl_collector/fetcher.py) |
| 테스트·관측 | testcontainers·카나리·Prometheus·Sentry·CI가 현재 구현 | fixture/mock 테스트, 별도 격리 DB 검증, 로그·health만 현재 구현 | [Python 테스트](../apps/api/tests/), [웹 테스트](../apps/web/tests/) |
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

이번 작업은 문서 및 환경 변수 예시 정정이다. 전체 애플리케이션 테스트나 서비스 재빌드·재기동,
실제 DB 조작·푸시 발송은 수행하지 않았다. 운영 중인 호스트 등록 상태와 외부 사이트·법률·요금은
새로 검증했다고 주장하지 않고, 저장소 밖 확인 사항 또는 과거 조사/향후 계획으로 표시했다.
