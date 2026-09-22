# 2026-09-15 이슈 검토와 조치

원본: [issue-review-20260915.md](issue-review-20260915.md).
정적 코드·오프라인 검증과 운영 상태를 구분한다. M3 자동 수집은 변경하지 않는다.

| 항목 | 판단 | 조치와 남은 범위 |
|---|---|---|
| 1 스택 중단·외부 감시 부재 | 타당. Colima 및 Docker API 중단을 재확인 | 정상 start/stop으로 복구 실패. 강제 정지는 승인 대기. 실패 전용 launchd 재시도 정의·호스트 감시 구현, 등록은 보류 |
| 2 백업 공백 | 타당. 다만 로컬 backups만 보고 모든 목적지 부재를 단정할 수 없음 | 실제 설정의 iCloud 경로도 산출물 0개. 키체인 항목은 존재하지만 SSH에서 암호 읽기 실패. 독립 백업·실패 exit·성공 기록·36시간 감시·복호화 검증 구현. 사용자 외부 경로 미정 |
| 3 평문 롤백 사본 | 부분 타당 | 권한 600·Git 제외이며 유출 증거는 없음. `.env` 원본도 호스트에 있으므로 P0 단정은 과함. 현재 백업만으로 과거 원본 삭제는 부적절. 과거 파일 자체 암호화 검증 전까지 보존 |
| 4 단일 트랜잭션 순차 발송 | 타당. 수치는 측정치가 아닌 상한 계산 | 계획/건별 결과 커밋, HTTP 시 트랜잭션 종료, 5개 병렬·동일 구독 순차, 45초 admission 제한. PREORDER_OPEN 우선. 500건/주기 용량 한계와 진행 중 전송의 중복 공백은 남음 |
| 5 production reload·mount | 타당 | API reload 제거, API와 공유 core를 사용하는 collector 모두 production source mount 제거. 재빌드 필요. 운영 적용은 복구·검증 후 |
| 6 실제 DB 검증 없음 | 표현은 부정확, 핵심 지적 타당 | CI는 이미 PostgreSQL 통합 검사를 실행했음. ORM create_all을 실제 migration chain으로 교체하고 alembic check 추가. CHECK·CASCADE·정렬·쿼리 수·실제 발송 커밋 검사 추가. check가 모든 드리프트를 잡는다는 주장은 틀림 |
| 7 모바일 CI 부재 | 타당 | mobile lint/typecheck/test·생성 타입 drift, Python OpenAPI snapshot drift 검사 추가 |
| 8 아티스트 N+1 | 타당 | primary_artist selectin 관계와 serializer 사용. 생성/수정 시 관계도 갱신. DB에서 30개 아티스트 응답에 최대 3 SELECT 검사 추가 |
| 9 커밋 규약 | 개선 타당, 이력 추적 불가능하다는 주장은 과장 | git log -S/파일 이력으로 추적은 가능. 과거 이력 보존, 유지보수에는 임의 T-ID를 만들지 않도록 규칙 명시. 이번 작업에서 커밋하지 않음 |
| 10 위생·문서 드리프트 | 타당 | 14개 임시·AppleDouble 산출물 Git 추적 제외(디스크 파일 보존), ignore 추가. 피드/푸시 태그 근거 수정, 양언어 blueprint와 CLAUDE·모바일 CI 설명 갱신 |

## 확인한 결과

- Python Ruff·format·mypy 전체 및 core strict 통과.
- Python 437 passed, 2 xfailed. 기존 Starlette deprecation warning 1개.
- 모바일 lint/typecheck, 5 suites / 16 tests 통과. 생성 API 타입 차이 없음.
- 웹 회귀 24개 통과. OpenAPI snapshot 차이 없음.
- 새 발송 경계 테스트 4개 통과.
- 새 호스트 감시/백업 테스트 6개: 실서비스·실제 키 없이 임시 파일과 가짜 명령으로 통과.
- production Compose 병합 결과: API reload 없음, API·collector·웹 소스 마운트 없음.
- launchd 생성물 3개 `plutil -lint`, 셸 스크립트 `bash -n` 통과.
- 호스트 dry check: api/web/collector down, DB/env backup stale. Slack 발송 없음.

## 아직 완료하지 못한 운영·검증

Colima는 `vz driver is running but host agent is not` 오류로 중단 상태다.
자동 승인 검토가 강제 종료를 DB 비정상 종료/손상 가능성과 명시적 승인 부족으로 거절했다.
사용자 승인 전에는 강제 종료·VM 삭제·볼륨 삭제를 하지 않는다.
이로 인해 새 PostgreSQL 통합 테스트 및 `alembic check`의 로컬 실행, DB 백업,
새 production 이미지 빌드·적용은 아직 검증하지 못했다. GitHub CI 실행 성공도 주장하지 않는다.

환경 백업은 설정된 키체인 항목이 존재하나 암호 접근이 실패하여 완료되지 않았다.
현재 파일과 과거 `original.env`를 보존했다. 외부 백업 목적지는 사용자 응답대로 미정이다.
호스트 감시/재시도 정의는 생성·검증했으나 실제 launchd 교체 및 Slack 활성화는 보류했다.

구체적인 재개·설정 방법: [운영 보강 안내](operations-reliability.ko.md).
