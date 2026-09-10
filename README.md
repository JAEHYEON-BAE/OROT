# Vinyl Radar

국내 레코드샵·레이블·유통사에 흩어진 바이닐(LP) 발매·재고 정보를 하나의 피드로 모으고,
상태 변화를 감지해 수집가에게 알립니다.

- **전체 명세**: [`docs/BLUEPRINT.ko.md`](docs/BLUEPRINT.ko.md) (원본) / [`docs/BLUEPRINT.en.md`](docs/BLUEPRINT.en.md) (미러)
- **에이전트 컨텍스트**: [`CLAUDE.md`](CLAUDE.md)
- **소스별 조사 기록**: [`docs/adapters/`](docs/adapters/)
- **아키텍처 결정 기록**: [`docs/adr/`](docs/adr/)

현재 마일스톤은 **M0 (Walking Skeleton)** 입니다.

---

## 빠른 시작

### 1) 컨테이너 스택

```bash
cp .env.example .env
make up        # postgres + api + collector 기동 후 /healthz 200 까지 대기
```

| 주소 | 내용 |
|---|---|
| **http://localhost:3000** | **웹 — 피드·캘린더** |
| http://localhost:8000/admin | 운영자 일정 등록 폼 |
| http://localhost:8000/v1/releases.ics | 캘린더 구독 (iCalendar) |
| http://localhost:8000/v1/feed.rss | RSS 구독 |
| http://localhost:8000/docs | OpenAPI 문서 |
| http://localhost:8000/healthz | 헬스체크 (DB 연결 포함) |

```bash
make ps      # 상태
make logs    # 로그 추적
make down    # 종료 (DB 볼륨은 유지)
```

**사전 요구사항**: Docker 엔진과 Compose v2.
macOS 에서 Docker Desktop 없이 쓰려면:

```bash
brew install docker docker-compose
colima start --cpu 2 --memory 4 --disk 60
```

### 2) 컨테이너 밖에서 개발

```bash
make install   # venv 생성 + 3개 패키지를 editable 로 설치
make test      # pytest
make lint      # ruff check + format --check + mypy(core strict)
make format    # 자동 수정
```

`make help` 로 전체 타깃을 볼 수 있습니다.

---

## 저장소 구조

```
apps/
  api/        FastAPI. 현재는 /healthz 만 구현 (T-001)
  collector/  수집기 + CLI. 어댑터는 T-007 부터
    tests/fixtures/<source_id>/   저장된 HTML 골든 fixture
packages/
  core/       API·collector 공용. 설정·DB·로깅 (모델은 T-002)
docs/
  BLUEPRINT.{ko,en}.md   전체 명세 (권위 문서)
  adapters/<source_id>.md  소스별 조사 기록
  adr/NNNN-*.md            아키텍처 결정 기록
```

전체 목표 구조는 블루프린트 §6 을 참조하십시오.
`apps/web` (Next.js) 는 T-011, `apps/ios` 는 T-033 에서 추가됩니다.

---

## 수집 원칙 (블루프린트 §3.4)

이 프로젝트는 타인의 사이트를 읽습니다. 다음은 타협 대상이 아닙니다.

- robots.txt 를 준수합니다
- 소스별 **최대 0.5 req/s**, 동시 연결 2 이하
- User-Agent 로 정체와 연락처를 밝힙니다
- **메타데이터만 저장**합니다. 상세설명 원문·리뷰를 저장하지 않고, 이미지를 재호스팅하지 않습니다
- 모든 화면에서 출처를 표기하고 원본 상품 페이지로 링크합니다
- CAPTCHA·봇 차단 우회, 비공개 내부 API 역공학을 하지 않습니다

앞의 두 항목은 `vinyl_core.settings.Settings` 의 검증기가 강제합니다 —
`CRAWLER_RATE_LIMIT_RPS` 가 0.5 를 넘거나 User-Agent 에 연락처가 없으면 **프로세스가 기동하지 않습니다.**

테스트는 **실시간 네트워크 요청을 하지 않습니다.** 어댑터 테스트는 저장된 fixture 를 읽습니다
([`apps/collector/tests/fixtures/README.md`](apps/collector/tests/fixtures/README.md)).

---

## 작업 방식

한 번에 하나의 태스크(`T-XXX`, 블루프린트 §10)만 진행합니다.
현재 상태와 결정 기록은 [`CLAUDE.md`](CLAUDE.md) §7 에 있습니다.
