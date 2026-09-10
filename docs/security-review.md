# 공개 테스트 전 보안 점검 — 2026-09-10

## 확인 범위와 현재 상태

- 사용자는 Tailscale 서비스 시작과 `tailscale up`까지만 실행했다.
  `tailscale funnel status`도 `No serve config`였다. 공개 URL은 아직 없다.
- 실행 중인 Compose 스택은 production 오버레이를 사용한다. API(8000)와
  PostgreSQL(5432)은 `127.0.0.1`에만 바인딩되어 있다.
- 로컬 설정의 관리자 키는 기본값이 아닌 44자 값이었다. 키 자체는 출력하거나
  수정하지 않았다. 키 길이 검사는 무작위성이나 유출 여부를 증명하지 않는다.
- 기존 작업 트리의 SSRF 허용 목록, 구독 속도 제한, HTML 이스케이프, CSP 등은
  보존했다. 아래 항목은 그 위에 추가한 수정이다.

## 발견 및 수정

| 문제 | 영향 및 전제 | 수정 |
|---|---|---|
| 푸시 HTTP 클라이언트가 리디렉션을 자동 추적 | 허용된 서비스가 외부 주소로 리디렉션하면 최초 URL 허용 목록 밖으로 요청 가능. 실제 서비스의 악성 리디렉션은 확인하지 않음 | 발송 전 검증 유지, 리디렉션 추적 금지, 3xx를 발송 성공으로 처리하지 않음 |
| 모호한 푸시 URL 허용 | 사용자 정보, 비표준 포트, 제어 문자 등 불필요한 URL 형태가 저장됨 | HTTPS 기본 포트, ASCII URL, 사용자 정보·fragment·제어 문자·역슬래시 제한 |
| 잘못된 과거 URL 처리 중 재파싱 | 깨진 URL이 로그 작성 단계에서 예외를 발생시켜 발송 루프를 중단할 수 있음 | 로그에서 URL 재파싱 제거 |
| 구독 본문 무제한 읽기 | 인증 없이 큰 본문 또는 느린 업로드로 메모리·연결 점유 가능 | 웹과 API에서 실제 바이트 기준 8 KiB 제한, 5초 읽기 제한. `Content-Length`가 없거나 거짓이어도 검사 |
| 프록시가 모든 본문을 JSON으로 전달 | 다른 사이트의 `text/plain` 요청도 구독 등록 경로로 전달 가능 | `application/json`만 수락하고 브라우저의 `cross-site` 요청 거부 |
| API 프록시에 시간 제한 없음 | 내부 API가 정지하면 웹 요청도 계속 대기 | 본문 수신까지 10초 제한, 리디렉션 금지, 실패 시 JSON 502, 구독 응답 `no-store` |
| 임의 문자열을 푸시 키로 등록 가능 | 사용할 수 없는 구독이 DB와 발송 실패 큐에 쌓임 | base64url, 실제 비압축 P-256 공개키, 16바이트 auth 검증 |
| 빈 관리자 키 설정 시 누락 헤더와 일치 | 잘못된 설정에서 인증 없는 관리자 요청이 통과 가능. 현재 로컬 키에는 해당하지 않음 | 빈 키 설정 거부, 인증 의존성도 실패하도록 방어, staging/production은 32자 이상 요구 |
| 푸시 예외 문자열 저장·기록 | 라이브러리 예외에 구독 URL이나 키가 포함되면 로그·배송기록에 남을 수 있음 | HTTP 상태 또는 예외 클래스만 기록 |

## 검증

- `make lint`: 통과.
- `make test`: **368 passed, 2 xfailed**. 기존 robots 파서 관련 예상 실패는 유지.
- `cd apps/web && npm run lint`: 통과.
- `cd apps/web && node --test tests/security.test.mjs`: **8 passed**.
- `cd apps/web && npm run build -- --webpack`: production 빌드 및 TypeScript 통과.
- 기본 `npm run build`는 로컬 Turbopack의 `binding to a port: Operation not permitted`
  오류로 실패했다. 권한 재요청 후에도 재현되어 Webpack으로 검증했다.
- `npm audit --omit=dev`: 알려진 취약점 **0건**.
- 현재 프로젝트 venv의 설치 패키지 69개를 임시 `pip-audit`로 검사: 알려진 취약점
  **0건**. 프로젝트 자체인 `vinyl-*` 3개는 공개 패키지 DB 검사에서 제외했다.
- 테스트는 가짜 HTTP 어댑터와 메모리 스트림을 사용했다. 실제 알림 발송, 운영 DB
  변경, Funnel 시작, 컨테이너 재기동은 실행하지 않았다.

## 공개 전 적용과 남은 한계

코드 수정과 실행 중인 이미지 반영은 별개다. 공개하기 전에
`docker compose -f compose.yaml -f compose.prod.yaml up -d --build api collector web`
로 반영하고 `/healthz`, 웹 구독 등록·해지, 실제 기기의 알림을 확인해야 한다.
이 명령은 아직 실행하지 않았다. API의 개발용 소스 마운트와 `--reload`는
오버레이에도 남아 있어 일부 Python 수정은 자동 반영될 수 있지만,
웹 이미지와 상주 수집기는 일괄 반영되었다고 가정하면 안 된다.

공개 대상은 웹 포트만이어야 한다. `/admin`이 있는 API 포트나 DB를 Funnel에
연결하지 않는다. 테스트 목적이어도 외부 노출에는 production 웹 빌드를 사용한다.

구독은 제품 설계상 익명이다. 기존 전역 속도 제한만으로 분산 공격이나 정원
소진을 완전히 막을 수 없으며, 이번 본문 제한은 전체 서비스의 DDoS 방어를
보장하지 않는다. CSP의 `unsafe-inline`, 푸시 재시도 정책(T-116), 컨테이너 OS
취약점 검사는 이번 수정의 미해결 범위다. 공개 후 URL 기반의 경로·헤더 확인과
실기기 검증도 남아 있다. 의존성 검사 0건은 취약점이 없다는 보증이 아니다.

## 참고

- [Tailscale Funnel 공식 문서](https://tailscale.com/docs/features/tailscale-funnel):
  Funnel은 서비스에 대한 인터넷 공개이며 tailnet 내부 연결과 구분된다.
- [Next.js AVIF 취약점 공지](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4):
  현재 프로젝트의 Next.js 16.3.3은 이 공지가 명시한 패치 버전이다.
