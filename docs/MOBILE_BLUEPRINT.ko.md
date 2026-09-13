# OROT — 모바일 앱 개발 블루프린트

> 작성: 2026-09-13 · 버전 0.2.0 · 상태: T-033 첫 단계 mock 뼈대 구현, 나머지는 계획
> 선택된 방향: React Native + Expo + TypeScript, iOS 우선, Android 확장 가능 구조.
> 서버: 기존 Mac mini + Docker Compose + Tailscale Funnel 유지.
> 검증 기기: 사용자의 iPhone 14와 Mac mini의 iOS Simulator.
> 첫 단계 현황은 [검증 기록](mobile-validation/T-033-scaffold.ko.md)을 따른다. `apps/mobile` mock 앱·로컬 빌드·테스트 기반이 추가되었고, 실제 API·모바일 푸시·TestFlight는 미구현이다. 아래 전체 설계가 완료되었다는 뜻은 아니다.

[기존 한국어 명세](BLUEPRINT.ko.md) · [English blueprint](BLUEPRINT.en.md) · [도메인과 모바일 호스팅](MOBILE_APP_DOMAIN_AND_HOSTING.ko.md) · [모바일 결정 기록](adr/0009-expo-mobile-app.md)

## 0. 에이전트 지침과 문서 사용법

1. 먼저 저장소의 `AGENTS.md`, `CLAUDE.md`와 관련 하위 지침을 읽는다. 이 문서의 모바일 방향은 기존 SwiftUI 계획을 대체한다. 수집·DB·운영의 공통 불변식은 기존 블루프린트를 따른다.
2. 아래 단계는 순서대로 진행한다. 기존 T-033~T-043을 재사용하며, 한 번에 한 작업의 완료 조건을 검증한다. 여러 작업을 함께 완료했다고 추정하지 않는다.
3. 모바일 개발은 M3 자동 수집 또는 M4 계정 구현을 기다리지 않는다. 최초 버전은 로그인 없는 공개 일정 조회와 전체 일정 알림이다. 관심 음반별 알림은 별도 매칭 구현 전에는 제공하지 않는다.
4. 문서 작성은 앱 생성, 유료 계정 가입, EAS 업로드, 실기기 푸시, 서비스 재시작을 실행할 권한과 별개다. 실제 구현 시 그 작업의 사용자 지시 범위에서 실행한다.
5. 테스트는 기본적으로 fixture와 fake sender로 실행한다. 실제 푸시는 사용자가 지정한 테스트 기기와 일정만 대상으로 한다. 기존 전체 구독자로 더미 일정을 방송하지 않는다.
6. `.env`, APNs 키, Expo 접근 토큰, 관리자 키, 기기 등록 비밀을 Git·앱 번들·로그에 넣지 않는다. `EXPO_PUBLIC_*`는 공개 정보다.
7. 기존 DB·Web Push·RSS/ICS ID를 보존한다. 데이터 파괴 또는 복구 덮어쓰기는 별도 승인 대상이다.
8. 환경 기록 → 구현 → 자동 검사 → 시뮬레이터 → iPhone → 결과 기록 순서로 진행한다. 실행하지 못한 단계는 미검증으로 남긴다.
9. 새 기술 방향은 사용자 선택으로 확정되었다. 푸시 제공자·익명 기기 인증 등 세부 설계는 ADR-0009의 초안이며 해당 구현 착수 전에 구체안을 확정한다. 화면 개발과 읽기 API 작업은 이에 의존하지 않는다.

### 문서 탐색

- §1: 제품 목표·최초 출시 범위
- §2~5: 아키텍처·데이터·API·푸시 계약
- §6~7: 코드 구조와 화면 설계
- §8: Mac·Simulator·iPhone 14 준비 및 명령
- §9: 테스트·빌드·TestFlight·운영
- §10: 단계별 백로그와 완료 조건
- §11~13: 위험·후속 로드맵·용어·공식 자료

## 1. 문제 정의와 모바일 MVP

### 1.1 사용자가 수행할 핵심 흐름

발매 임박순/최근 변경순 목록을 확인하고, 상세 일정과 판매처 원문 링크를 열고, 알림을 허용한 뒤 예약 시작 알림을 눌러 같은 상세 화면으로 돌아온다. 앱을 종료해도 서버가 일정을 감시한다.

현재 웹 화면이 있다는 사실은 모바일 UI가 구현되어 있다는 뜻은 아니다. Python 백엔드는 재사용하고 React Native 화면을 새로 만든다. React 웹의 HTML·CSS·Next.js 서버 컴포넌트는 그대로 옮기지 않는다.

### 1.2 최초 출시 범위

| 포함 | 완료 기준 |
|---|---|
| 피드 | 임박순·최근 변경순, 새로고침, 로딩·빈 목록·오류·재시도 |
| 상세 | 제목·아티스트·판본·예약 시간·발매일·판매처 링크, 없는 값의 대체 표시 |
| 알림 설정 | 설명 후 권한 요청, 전체 일정 알림 켜기/끄기, 서버 등록 상태 표시 |
| 알림 이동 | 앱 실행 중·백그라운드·종료 상태에서 유효한 상세 화면으로 이동 |
| 오프라인 읽기 | 마지막 성공 데이터와 갱신 시각, 네트워크 복구 후 재검증 |
| 접근성 | VoiceOver, 큰 글자, 다크 모드, iPhone 14 safe area |
| 운영 | 개인정보·지원 페이지, 오류 기록, 테스트 대상 제한, 기존 웹 회귀 없음 |

계정, 서버 동기화 워치리스트, 검색 API, 개별 음반 구독, 결제, 자동 수집, 위젯, 일간 요약은 최초 버전에서 제외한다. 로컬 즐겨찾기를 추가하더라도 알림 구독이나 계정 동기화로 표현하지 않는다.

### 1.3 성공 지표

다음은 목표이며 실측 SLA가 아니다. 각 측정은 빌드·기기·네트워크·표본 수와 함께 기록한다.

| 지표 | 목표 / 판정 |
|---|---|
| 핵심 흐름 | iPhone 14에서 목록 → 상세 → 원문 → 푸시 → 상세 성공 |
| 데이터 노출 | 초안·운영자 메모 노출 0건 |
| 정상 네트워크 목록 | 최초 요청 후 약 2초 이내 표시를 초기 목표로 측정 |
| 재시도 | 오프라인·502·429 이후 무한 루프 없이 복구 |
| 일정 발송 | 서버 tick과 제공자 수락 시간을 분리 기록; 기존 ±1분 목표 유지 |
| 기기 표시 | 수락 로그와 별개로 실제 수신 시각 확인; OS 지연을 숨기지 않음 |
| 독립 실행 | TestFlight 빌드가 Metro 없이 Wi-Fi와 셀룰러에서 동작 |

## 2. 아키텍처 개요

### 2.1 현재 확인된 구현

| 영역 | 현재 | 모바일에서 필요한 변화 |
|---|---|---|
| 서버 | FastAPI + PostgreSQL + collector | 공통 사용 |
| 공개 진입점 | Funnel → loopback 3000 → Next.js | 허용한 JSON 경로만 추가 |
| JSON API | 내부 `/v1/feed`, `/v1/releases`, `/v1/releases/{id}` | 공개 프록시·계약 검증 |
| 공개 프록시 | `/api/push/*`, RSS/ICS의 고정 경로 | 네이티브 기기용 경로 별도 구현 |
| 알림 | WEB 대상 선택, WebPushSender, 60초 tick | 모바일 대상 선택·sender·receipt 처리 |
| 기기 스키마 | `platform` CHECK는 IOS/WEB만 허용 | Android와 제공자/환경 구분 마이그레이션 |
| 앱 | `apps/mobile` mock 피드/상세/설정 뼈대 추가 | 실제 API·푸시·배포 후속 |
| 계정/워치리스트 | 일부 테이블만 존재, 제품 기능은 후속 | 최초 버전의 의존성으로 두지 않음 |

근거: `apps/api/src/orot_api/routers/{feed,releases,push}.py`, `apps/web/lib/proxy.ts`, `packages/core/src/orot_core/{notifications,enums}.py`, `packages/core/src/orot_core/models/user.py`.

### 2.2 목표 연결 구조

```text
개발 시에만:
iPhone/Simulator ← LAN의 Metro(통상 8081) ← apps/mobile TypeScript

데이터 요청:
iPhone/Simulator/TestFlight
  → HTTPS Funnel 주소
  → Mac mini 127.0.0.1:3000의 Next.js
  → 고정된 /api/mobile/v1/* 프록시 [신규]
  → 내부 http://api:8000/v1/*
  → PostgreSQL

알림 [신규 제공자 경로는 제안]:
collector → WebPushSender → 기존 브라우저 구독
          → ExpoPushSender → Expo Push Service → APNs → iPhone 14
                                            → FCM → Android [후속 검증]
```

Metro는 개발 중 JavaScript를 전달한다. Funnel은 서비스 API를 전달한다. 두 연결은 별개다. Store/preview 빌드는 JS를 포함하므로 Metro가 필요 없지만 API 서버는 필요하다. EAS는 빌드·배포 도구이며 Mac mini 백엔드를 대신 호스팅하지 않는다.

### 2.3 기술 구성

| 영역 | 계획 | 이유 |
|---|---|---|
| 앱 | Expo 지원 조합의 React Native + TypeScript strict | iOS 우선, 양쪽 코드 공유 |
| 화면 이동 | Expo Router | 상세 경로와 알림 이동을 일치 |
| 서버 상태 | TanStack Query 후보 | 요청 상태·재시도·캐시를 UI와 분리 |
| 비밀 저장 | Expo SecureStore | 익명 설치 인증 비밀; 보안 저장도 계정 인증은 아님 |
| 공개 캐시 | AsyncStorage + 명시적 버전/만료 처리 후보 | 작은 공개 일정 캐시 |
| 푸시 | expo-notifications + Expo Push Service 제안 | APNs/FCM 전송 추상화 |
| 테스트 | jest-expo + React Native Testing Library, 선택적 Maestro | 로직·상호작용·설치 앱 동선 검증 |
| 빌드 | 로컬 Xcode 우선, EAS로 서명된 배포 빌드 | 보유 Mac 활용, TestFlight 경로 확보 |

정확한 SDK·Node·Xcode·최소 iOS/Android 버전은 T-033 착수일의 Expo 지원표와 실제 iPhone iOS 버전에 맞춰 고정한다. 웹의 React 버전을 모바일에 강제하지 않는다. Swift 계획의 iOS 17 하한을 그대로 물려받지 않는다.

## 3. 앱 데이터 계층과 API 공개 경계

### 3.1 API 주소

모바일의 공개 기본 주소는 `https://<현재-Funnel-호스트>/api/mobile`로 계획한다. 아래 경로는 아직 없다. `tailscale funnel status`에서 확인한 주소를 사용하고 과거 문서의 호스트명을 무조건 복사하지 않는다.

| 앱 요청 | 프록시가 호출할 내부 경로 | 허용 메서드 |
|---|---|---|
| `/api/mobile/v1/feed` | `/v1/feed` | GET |
| `/api/mobile/v1/releases` | `/v1/releases` | GET |
| `/api/mobile/v1/releases/{id}` | `/v1/releases/{id}` | GET |
| `/api/mobile/v1/devices` | `/v1/devices` [신규] | POST |
| `/api/mobile/v1/devices/{id}` | `/v1/devices/{id}` [신규] | PATCH, DELETE |

처음에는 읽기 세 경로만 구현한다. 기기 경로는 인증·제한·테스트가 준비된 T-040에서 추가한다. 범용 catch-all과 사용자 제공 upstream URL은 금지한다. 숫자 ID, 메서드, 쿼리·본문 크기, timeout, redirect 거부, 허용 헤더를 제한한다. `/admin`, `/docs`, 임의 내부 URL은 통과시키지 않는다.

`API_BASE_URL=http://api:8000`은 웹 컨테이너 전용이다. iPhone의 `localhost`는 iPhone 자신이다. API 8000·DB 5432를 Funnel에 공개하거나 CORS `*`를 설정하는 방식으로 해결하지 않는다. 네이티브 요청에는 브라우저 Origin이 없을 수 있으므로 기존 Web Push의 same-origin 검사에 예외를 추가하지 말고 모바일 전용 인증 경계를 만든다.

### 3.2 실제 계약과 화면 사용

| API | 현재 계약 | 앱 처리 |
|---|---|---|
| `GET /v1/feed?sort=imminent&limit=50` | `{items, generated_at}`; 항목은 `{kind, at, event_type, release}` | 첫 피드, 커서 없음 |
| `GET /v1/feed?sort=recent` | 최근 변경순; limit 최대 100 | 정렬 전환 시 별도 query key |
| `GET /v1/releases?limit=50` | `{items, next_cursor}` | 전체 일정 목록이 필요할 때 커서 사용 |
| 목록 필터 | `from`, `to`는 release_date 기준; `format`, `is_limited` | 예약 시작 월 필터로 오해하지 않음 |
| `GET /v1/releases/{id}` | 공개 상세; 없거나 초안이면 404 | 안전한 빈 상세와 목록 돌아가기 |

피드의 `at`는 항상 발매일이 아니다. 화면 날짜는 `release.preorder_opens_at`, `release.release_date` 등 의도한 필드를 선택한다. `/v1/feed`에 존재하지 않는 cursor를 붙여 무한 스크롤이 된다고 주장하지 않는다. 초기 피드는 최대 100개와 새로고침으로 시작하며 피드 페이지네이션은 별도 계약 확장이다.

### 3.3 타입·오류·시간

- T-033에서 `docs/api/openapi.json`으로 TypeScript 타입 생성 도구를 고정한다. 생성 출력과 얇은 fetch 래퍼를 분리한다. 생성 타입은 런타임 JSON 검증을 대신하지 않는다.
- API 계약 변경 시 `make openapi`, 생성 재실행, diff 검사. 모바일에 사용하는 공개 스키마만 의존하고 관리자 기능을 노출하지 않는다.
- UTC datetime은 표시 시 `Asia/Seoul`로 변환하고 KST를 표시한다. 날짜만 있는 `YYYY-MM-DD`는 UTC 시각으로 변환하여 하루가 이동하지 않도록 별도 처리한다.
- `price_krw`는 정수 원화. null과 0을 구분한다. cover_url 실패는 대체 이미지로 처리한다.
- timeout·취소·오프라인·400·404·422·429·502와 예상하지 못한 HTML 응답을 구분한다. JSON 파싱 오류만 사용자에게 보여주지 않는다.
- 429는 Retry-After를 반영하고, 쓰기를 무조건 자동 재전송하지 않는다. 첫 버전은 조건부 요청 없이 시작해도 된다.
- ETag를 사용할 경우 URL·쿼리별 body와 함께 보관한다. 304는 본문이 없으므로 JSON 파싱하지 않는다. 기존 `lib/proxy.ts`는 204만 특별 처리하므로 304 전달을 지원하려면 별도 회귀 검증이 필요하다.

## 4. 데이터 모델과 익명 설치 인증 — 제안 계약

### 4.1 서버 마이그레이션

현재 `device_tokens`는 WEB과 IOS만 허용하며 IOS token은 직접 APNs 토큰이라는 의미다. Expo 토큰을 의미 설명 없이 IOS 칼럼에 넣지 않는다.

T-040에서 다음 설계를 확정하고 Alembic 업그레이드·데이터 보존 테스트를 작성한다.

| 개념 | 제안 |
|---|---|
| OS | platform에 ANDROID 추가; 기존 WEB/IOS 유지 |
| 전송 제공자 | provider = WEB_PUSH / EXPO / APNS / FCM; 초기 활성은 WEB_PUSH·EXPO |
| 앱 구분 | app_id, expo_project_id, environment(dev/preview/production) |
| 설치 | 임의 installation_id와 서버 발급 관리 비밀의 hash |
| 중복 | 제공자·프로젝트·환경·토큰 범위의 유일성; 토큰 갱신은 소유 설치만 |
| 구독 | is_active와 서버 저장 enabled, updated_at; user_id는 nullable 유지 |
| 발송 추적 | 기존 delivery에 연결되는 provider request/ticket/receipt 기록 |

CHECK·유일성·백필은 명시적인 migration으로 처리한다. 기존 WEB 행은 WEB_PUSH로 백필하고 기존 암호화 키와 배송 FK를 보존한다. 실제 SQL 이름과 downgrade 정책은 코드 리뷰에서 확정하며 문서의 후보 필드를 현재 칼럼으로 오해하지 않는다.

### 4.2 기기 등록·갱신·해지

제안 `POST /v1/devices` 입력은 installation_id, platform, provider, token, app_id, expo_project_id, environment다. 앱 값은 신뢰하지 않고 서버 allowlist와 일치하는지 검사한다. 성공 시 device_id와 한 번만 반환되는 관리 비밀을 앱 SecureStore에 저장한다.

이후 PATCH/DELETE는 해당 비밀의 Bearer 인증으로 본인 기기만 변경한다. 단순 token 또는 device_id를 안다는 이유만으로 타 기기의 토큰 교체·해지를 허용하지 않는다. 다른 설치 소유의 동일 토큰 등록은 일반 충돌 응답으로 처리하고 관리 비밀을 다시 발급하지 않는다.

최초 등록은 계정 없는 공개 쓰기다. IP/설치별 제한, 전체 활성 기기 한도, token 형식·프로젝트 검사, 입력 크기 제한이 필요하다. installation_id만으로 토큰 소유를 증명할 수는 없다. 공개 출시 전에는 등록 남용·토큰 소유 검증 또는 앱 증명 도입 필요성을 ADR에서 재평가한다. 테스트 기간에는 허용된 테스트 설치로 제한할 수 있다.

네트워크 응답 유실 후 재시도가 새 행을 계속 만들지 않도록 등록 멱등성 계약도 T-040에서 확정한다. 최초 응답을 잃었을 때 ID만으로 비밀을 재발급하지 않는다. 토큰 갱신 충돌·재설치·SecureStore 잔존 및 초기화 차이에 대한 복구 동선을 테스트한다.

### 4.3 앱 설정과 서버 상태

OS 권한, Expo token 획득, 서버 등록, 서버 enabled는 각각 다르다. UI는 네 상태를 구분한다. 권한은 허용되었지만 서버 등록 실패라면 “등록 재시도”를 표시한다. 해지 요청 실패 시 끄기 완료로 표시하지 않고 pending 상태를 보관한다. 재실행/foreground 시 권한·토큰·서버 상태를 동기화한다.

## 5. 모바일 푸시 설계 — 제공자 결정 전 초안

### 5.1 권장 경로와 제한

초기 제안은 Expo Push Service다. `expo-notifications`의 `getExpoPushTokenAsync({projectId})` 결과를 등록하고 서버가 Expo로 보낸다. `getDevicePushTokenAsync()`의 APNs/FCM 토큰과 섞지 않는다. APNs 자격증명은 Expo 프로젝트의 서버 측 자격증명 저장소에서 관리하고 앱에 포함하지 않는다.

Expo 전송 API 접근 토큰 보호 기능도 설정하고 서버에만 보관한다. 직접 APNs 발송을 선택하면 sender·환경·자격증명·응답 처리가 바뀌므로 ADR을 갱신한다. [Expo 푸시 개요와 설정](https://docs.expo.dev/push-notifications/push-notifications-setup/)

### 5.2 발송 상태와 receipt

현재 WEB 대상으로만 배송을 생성하는 쿼리와 WebPushSender 주입을 모두 수정해야 한다. 모바일 등록 API만 구현해도 푸시는 발송되지 않는다.

제안 상태 흐름은 모바일 delivery의 PENDING → PROVIDER_ACCEPTED → SENT/FAILED/EXPIRED다. 새 상태는 CHECK와 enum 마이그레이션이 필요하다. 기존 WEB의 SENT 의미는 유지한다. 모바일 SENT는 APNs/FCM 인계 성공 receipt를 의미하며 화면 표시·사용자 열람 확인은 아니다.

Expo ticket 수락 후 ticket_id를 영속화하고 receipt 조회를 후속 tick에서 수행한다. ticket을 받았다는 이유로 최종 성공 처리하지 않는다. 조회 지연, 조회 실패, 프로세스 재시작, receipt 소실을 명시적으로 관리한다. receipt 대기만으로 메시지를 다시 보내지 않는다. Expo는 약 15분 뒤 조회를 권장하고 receipt는 24시간 뒤 제거하므로 그 이전에 확인·오류 기록을 완료한다.

오류별 정책: DeviceNotRegistered는 대상 비활성화, 잘못된 자격증명은 운영자 경고, 429/5xx/일시 네트워크 오류는 제한된 backoff, 잘못된 payload는 수정 전 무한 재시도 금지. 배치는 제공자 제한 내에서 프로젝트별로 나누며 응답과 대상 순서를 정확하게 연결한다. [Expo 발송·ticket·receipt 명세](https://docs.expo.dev/push-notifications/sending-notifications/)

DB 잠금/unique 제약만으로 외부 전송과 DB 커밋을 원자화할 수 없다. 요청 수락 직후 장애에서는 중복 가능성이 남는다. event_id를 앱에 전달하고 알림 탭 처리를 멱등적으로 만들되 OS 알림 중복까지 완전히 보장한다고 설명하지 않는다. superseded·비공개·비활성·만료 이벤트는 보내기 직전에 다시 확인한다. WEB과 모바일의 처리량을 분리하거나 공정하게 제한하여 기존 WEB이 밀리지 않도록 테스트한다.

### 5.3 payload와 상세 이동

아래는 신규 payload의 예시다. 서버가 만든 release_id/event_id만 사용하고 임의 URL 이동을 허용하지 않는다.

```json
{
  "title": "OROT 예약 시작",
  "body": "테스트 음반의 예약이 시작되었습니다.",
  "data": {
    "schema_version": 1,
    "release_id": 1042,
    "event_id": 9001,
    "event_type": "PREORDER_OPEN"
  }
}
```

숫자 범위·payload 버전을 검증하고 앱 내부 `/releases/1042`로 이동한다. cold start에서는 Router와 캐시 초기화 이후 처리한다. 초기 응답과 listener가 같은 알림을 중복 처리하지 않도록 notification identifier로 한 번만 이동한다. 일정이 삭제/비공개면 404 안내를 표시한다.

`orot://releases/1042`를 개발용 scheme으로 사용한다. 웹 상세 경로와 유사하게 복수형 releases로 통일한다. 기존 Swift 계획의 단수 release 예시는 새 계약이 아니다. dev/preview 앱을 동시에 설치한다면 scheme과 bundle ID도 분리해 충돌을 피한다. Universal Links는 후속이며 도메인 구매는 현재 단계의 전제조건이 아니다.

### 5.4 푸시 UX

앱 첫 화면에서 곧바로 권한 팝업을 띄우지 않는다. 설정에서 전체 일정 알림의 의미를 설명한 후 요청한다. 거부 시 반복 팝업 대신 iOS 설정 이동을 제공한다. foreground의 배너·소리 정책을 명시하고 자동 테스트로 확인한다. 백그라운드 JS 또는 silent push를 예약 알림의 필수 조건으로 삼지 않는다.

## 6. 저장소 구조

아래는 목표 구조다. `apps/mobile`과 mock 피드/상세/설정·tests는 생성되었고, features/notifications·lib/api·storage·e2e·eas.json은 후속이다. 앱 루트의 package-lock으로 독립 설치하며 초기에 저장소 전체를 npm workspace로 개편하지 않는다.

```text
apps/mobile/
  src/app/
    _layout.tsx
    (tabs)/index.tsx
    (tabs)/settings.tsx
    releases/[id].tsx
  src/components/             # 화면 공통 UI와 접근성
  src/features/releases/      # query, 화면 모델, fixture
  src/features/notifications/ # 권한, 등록, 탭 처리
  src/lib/api/                # 생성 types + fetch wrapper
  src/lib/storage/            # 공개 cache / SecureStore 분리
  src/lib/config.ts           # 공개 URL 검증, 환경 검증
  tests/                      # 로직 및 컴포넌트 테스트
  e2e/                        # mock 환경의 설치 앱 동선
  assets/
  app.config.ts
  eas.json
  package.json / package-lock.json / tsconfig.json
  .env.example
  AGENTS.md
```

템플릿이 `app/` 구조를 생성하면 T-033에서 `src/app/`로 한 번 정리하고 두 Router 루트를 동시에 두지 않는다. `ios/`, `android/`는 앱 내부에서 Expo prebuild로 생성하는 CNG 산출물로 운영할 것을 제안한다. 직접 수정이 필요하면 config plugin으로 표현한다. `prebuild --clean`은 네이티브 디렉터리를 재생성하므로 수기 변경을 확인하지 않고 실행하지 않는다.

공유 코드 추출은 실제 중복이 생겼을 때 수행한다. Next.js 코드나 서버 비밀을 import하지 않는다. 모바일 네이티브 의존성은 `npx expo install`로 SDK 호환 버전을 맞춘다.

## 7. 화면과 상태 설계

### 7.1 피드와 상세

첫 탭은 피드, 두 번째는 설정으로 시작한다. 달력은 필수 첫 릴리스 범위가 아니며 추가 시 월 경계·KST·페이지 범위를 먼저 확정한다. 피드는 release_id를 안정 키로 사용한다. 정렬 변경·연속 새로고침의 늦은 응답이 최신 화면을 덮지 않도록 한다.

상세는 링크를 OS 브라우저로 열고 https/http만 허용한다. 구매 성공을 앱이 추정하지 않는다. 재호스팅하지 않는 원본 이미지와 판매처 출처를 표시하고 이미지 실패가 화면 전체 실패가 되지 않도록 한다.

### 7.2 오프라인

초기 캐시는 마지막 피드와 방문 상세 중 최근 최대 200개를 목표로 한다. 스키마 버전·저장 시각을 함께 보관하고 앱 업데이트 시 호환되지 않으면 해당 캐시만 초기화한다. 기기 관리 비밀은 공개 캐시와 분리한다. 캐시 유효기간 후보는 24시간이며 초과 데이터는 최신이라고 표시하지 않는다.

온라인에서 404가 확인된 상세는 캐시에서도 제거한다. 서버가 비공개로 바꾼 이미 내려받은 데이터는 오프라인 기기에서 즉시 회수할 수 없으므로 오래된 캐시 표시와 만료 정책을 유지한다. 알림을 눌렀을 때 최신 상세를 우선 조회한다.

### 7.3 기기 검증

iPhone 14의 노치·하단 홈 표시 영역을 고려한다. 큰 글자에서 판매처 버튼이 가려지지 않는지, VoiceOver 읽기 순서와 상태 배지의 텍스트 대체가 맞는지 확인한다. 색만으로 예약 상태를 구분하지 않는다. 작은 화면 Simulator와 다크 모드도 함께 확인한다.

## 8. Mac mini·Simulator·iPhone 14 준비

### 8.1 단계 0 — 도구·계정 확인

저장소 루트에서 읽기 전용으로 기록한다. 도구가 없으면 해당 단계에서 설치 후 다시 확인한다. 이 문서 작성 중에는 실행 여부를 대신 판정하지 않았다.

```sh
cd /Users/jaehyeon/PersonalProjects/OROT
git status --short
node --version
npm --version
xcodebuild -version
xcode-select -p
xcrun simctl list devices available
tailscale funnel status
docker compose ps
```

1. Mac에 정식 Xcode를 설치하고 첫 실행에서 라이선스·추가 구성요소 설치를 마친다.
2. Xcode Settings에서 iOS Simulator runtime과 Command Line Tools를 확인한다. `xcode-select -p`가 CommandLineTools만 가리키면 Xcode 선택을 수정한다.
3. iPhone 14의 실제 iOS 버전을 Settings → General → About에서 확인한다. 그 기기를 지원하는 Xcode와 macOS 조합인지 확인한다. Mac이 Xcode 요구 OS를 충족하지 못하면 호스트 업데이트 또는 EAS 빌드 경로를 검토한다.
4. Node는 선택한 Expo SDK가 지원하는 LTS 버전을 사용한다. SDK·Node·npm·Xcode·macOS·iOS 버전을 검증 기록에 남긴다.
5. Simulator runtime은 Xcode에서 설치한다. 정확한 iPhone 14 프로필이 없다면 사용 가능한 iPhone으로 UI 검증을 시작하고 실제 14에서 최종 확인한다.

| 계정/도구 | 언제 필요한가 |
|---|---|
| Xcode·Simulator | 로컬 iOS 컴파일·UI 검증 |
| Apple Account Personal Team | 지원 기능 범위 내 로컬 실기기 UI 설치 가능; 서명 제한 있음 |
| Apple Developer Program | 이 계획의 APNs 실기기 검증·배포 서명·TestFlight 전 필수 준비 |
| Expo 계정·프로젝트 | EAS 및 Expo Push Service 사용 단계 |
| Firebase 프로젝트 | Android FCM 설정 단계 |
| 유료 자체 도메인 | 필요 없음 |

무료 Personal Team의 UI 설치 가능성과 원격 푸시/TestFlight 가능성을 혼동하지 않는다. 가입·요금은 계정 화면에서 직접 확인한다. [Expo 개발 빌드](https://docs.expo.dev/develop/development-builds/introduction/), [iOS Simulator 준비](https://docs.expo.dev/workflow/ios-simulator/)

### 8.2 단계 1 — 앱 생성과 버전 고정: T-033

2026-09-13 구현: 앱 폴더는 이미 존재한다. 아래 생성 명령을 다시 실행하지 말고 `apps/mobile/README.md`의 npm ci·실행 명령을 사용한다. 현재 Xcode 26.2에 맞춰 Expo 55.0.31 / React Native 0.83.10 / React 19.2.0 / Node 22.23.2를 선택했다. Xcode 업데이트 후 SDK 57+ 이전을 검증한다.

아래 명령은 `apps/mobile`이 아직 없을 때 한 번 실행할 시작점이다. 기존 폴더가 있으면 먼저 내용을 확인하고 덮어쓰지 않는다. 실행일의 create-expo-app 안내에서 development build용 안정 SDK를 확인한다. 생성 직후 package-lock과 사용 버전을 고정하고 이후 재현은 npm ci로 한다.

```sh
cd /Users/jaehyeon/PersonalProjects/OROT
npx create-expo-app@latest apps/mobile
cd apps/mobile
npx expo install expo-dev-client
npx expo-doctor
npx expo install --check
```

기본 TypeScript·Router 템플릿을 확인한다. 이름 OROT, slug orot, scheme orot을 설정한다. bundleIdentifier와 Android package는 본인이 관리하는 고유 reverse-DNS 식별자로 결정한다. 예: `com.<owner>.orot`의 `<owner>`를 실제 고유 값으로 교체한다. 이는 도메인 구입 증명이 필요한 주소가 아니다. production 식별자는 스토어 등록 이후 임의 변경하지 않는다.

T-033에서 lint/typecheck/test/type-generation 스크립트를 정의하고 최소 mock 피드 화면을 만든다. 아래 스크립트들은 새 앱에서 설정할 계약이며 현재 저장소에 존재하는 명령이 아니다.

```json
{
  "scripts": {
    "start": "expo start --dev-client",
    "ios": "expo run:ios",
    "android": "expo run:android",
    "lint": "expo lint",
    "typecheck": "tsc --noEmit",
    "test": "jest"
  }
}
```

jest-expo와 React Native Testing Library 및 필요한 타입을 SDK 호환 버전으로 추가하고 jest preset을 설정해야 test 명령이 동작한다. [프로젝트 생성](https://docs.expo.dev/get-started/create-a-project/), [Expo 단위 테스트](https://docs.expo.dev/develop/unit-testing/)

### 8.3 단계 2 — Simulator 실행

```sh
cd /Users/jaehyeon/PersonalProjects/OROT/apps/mobile
open -a Simulator
npx expo run:ios
```

첫 컴파일은 native 폴더 생성과 CocoaPods 설치를 포함할 수 있다. 오류가 나면 첫 실패 원인을 확인하고 pod·SDK 버전을 기록한다. 이미 실행한 Metro와 중복 실행하지 않는다. JS만 바뀐 다음 개발 세션에는 다음으로 충분하다.

```sh
npx expo start --dev-client
```

mock 목록 표시 → 상세 이동 → 뒤로 가기 → 다크 모드 → 큰 글자를 확인한다. Simulator에서 앱 실행은 무료로 먼저 진행할 수 있다. 원격 푸시의 최종 완료 판정은 Simulator 지원 조합에 기대지 않고 iPhone 14에서 한다. `simctl push` 등 payload 주입은 UI 테스트이며 서버→Expo→APNs 배송의 증거가 아니다.

### 8.4 단계 3 — 공개 읽기 API 연결

T-033에서 §3의 고정 프록시를 구현·검증한 뒤 production 웹을 재빌드하는 배포 단계가 필요하다. 문서만 추가했거나 Python 코드만 수정했다고 공개 경로가 생기지 않는다. 프록시 변경 전에 `apps/web/AGENTS.md`와 설치된 Next.js 문서를 읽는다.

모바일 디렉터리에 `.env.example`과 로컬 `.env.local`을 준비한다. 실제 서버의 루트 `.env`를 복사하지 않는다.

```dotenv
EXPO_PUBLIC_API_BASE_URL=https://YOUR_FUNNEL_HOST/api/mobile
EXPO_PUBLIC_APP_ENV=development
```

YOUR_FUNNEL_HOST를 `tailscale funnel status`에서 확인한 hostname으로 바꾼다. 로컬 파일은 Git에서 제외한다. config.ts에서 URL이 HTTPS인지 검증하고 production에 mock/localhost/미설정 값이 들어가면 빌드를 실패시키도록 구현한다. `EXPO_PUBLIC_*`는 번들에 포함되므로 비밀을 넣지 않는다. [Expo 환경변수](https://docs.expo.dev/guides/environment-variables/)

프록시 배포 후의 읽기 확인 예시다. 첫 줄 URL을 실제 값으로 수정한다.

```sh
OROT_MOBILE_BASE='https://YOUR_FUNNEL_HOST/api/mobile'
curl --fail-with-body --get "$OROT_MOBILE_BASE/v1/feed" --data-urlencode 'limit=1'
```

기대 결과는 HTML이 아닌 JSON, items와 generated_at이다. 없는 경로·admin 경로는 접근 불가, 잘못된 메서드는 거부되어야 한다. Simulator에서 같은 기본 URL로 mock을 끄고 실제 공개 목록을 확인한다. 기존 서비스가 정상 운영 중이면 설치 확인만을 위해 중단하지 않는다.

### 8.5 단계 4 — iPhone 14에 개발 빌드 설치

1. USB로 연결하고 iPhone에서 이 컴퓨터 신뢰를 허용한다.
2. Xcode → Settings → Accounts에서 본인 Apple 계정을 추가한다.
3. Xcode → Window → Devices and Simulators에서 iPhone 14와 준비 상태를 확인한다.
4. iPhone Settings → Privacy & Security → Developer Mode를 켜고 재시작·확인을 완료한다.
5. 앱의 고유 bundle ID와 서명 Team을 확인한다. 처음에는 Xcode에서 서명 오류를 해결해야 할 수 있다.
6. 앱 디렉터리에서 아래를 실행하고 iPhone 14를 선택한다.

```sh
npx expo run:ios --device
```

7. Mac과 iPhone을 같은 LAN에 두고 Metro 주소에 접근하는지 확인한다. iPhone의 로컬 네트워크 권한, Mac 방화벽, Wi-Fi client isolation을 점검한다.
8. 화면 수정이 반영되는지 확인하고 Funnel API 목록·상세·원문 링크를 테스트한다.

API는 Funnel로 열리지만 개발 JS는 LAN의 Metro에서 받는다. 셀룰러 테스트에는 JS가 포함된 preview/TestFlight 빌드를 우선 사용한다. 개발 Metro를 서비스 Funnel의 3000 대신 공개하지 않는다. 필요 시 Expo 개발 tunnel은 별개 기능이며 개발 중에만 사용한다. [Developer Mode](https://docs.expo.dev/guides/ios-developer-mode/)

### 8.6 단계 5 — 푸시 기능이 포함된 개발 빌드

T-040/041의 서버 구현과 제공자 결정을 먼저 완료한다.

```sh
npx expo install expo-notifications expo-device expo-constants expo-secure-store
npx eas-cli@latest login
npx eas-cli@latest init
npx eas-cli@latest build:configure
```

EAS init은 원격 프로젝트를 만들거나 연결한다. 본인의 계정·프로젝트를 확인하고 다른 프로젝트에 연결하지 않는다. 생성된 projectId를 app config에 유지한다. `expo-notifications` config plugin을 설정하고 iOS Push Notifications capability·APNs 자격증명이 올바른 bundle ID/Team에 연결되는지 확인한다. 서비스 키를 채팅으로 전달하지 않는다.

앱은 설명 버튼 → OS 권한 요청 → projectId 기반 Expo token 획득 → 서버 등록 순서로 구현한다. native plugin·capability를 변경했으면 기존 설치 앱을 재빌드한다. Expo Go는 이 원격 푸시 검증에 사용하지 않는다. [푸시 설정 절차](https://docs.expo.dev/push-notifications/push-notifications-setup/)

## 9. 검증·배포·운영

### 9.1 빌드 종류

| 종류 | Metro | 주 검증 | 주의 |
|---|---|---|---|
| 로컬 Simulator development | 필요 | UI·로직·mock | 실기기 푸시 증거가 아님 |
| iPhone development | 필요 | 네이티브 설정·실제 토큰·디버깅 | 서명·Developer Mode |
| preview internal | 불필요 | 셀룰러·재실행·실사용 | iOS ad hoc 등록 기기 필요 |
| production/TestFlight | 불필요 | 배포 환경 푸시·업데이트·최종 흐름 | App Store Connect·배포 서명 |

제안 eas.json이다. 환경별 URL을 EAS 환경에 별도로 정의하고 실제 빌드의 공개 URL을 확인한다. EAS 환경의 민감 정보 보호 설정도 EXPO_PUBLIC 값을 앱 비밀로 만들지는 않는다.

```json
{
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "environment": "development"
    },
    "development-simulator": {
      "extends": "development",
      "ios": { "simulator": true }
    },
    "preview": {
      "distribution": "internal",
      "environment": "preview"
    },
    "production": {
      "autoIncrement": true,
      "environment": "production"
    }
  },
  "submit": { "production": {} }
}
```

[EAS 빌드 프로필](https://docs.expo.dev/build/eas-json/)

### 9.2 자동 테스트 게이트

모바일 스크립트를 T-033에서 만든 후 앱 디렉터리에서 실행한다.

```sh
npm ci
npx expo-doctor
npx expo install --check
npm run lint
npm run typecheck
npm test -- --runInBand
```

| 계층 | 반드시 검증할 사례 |
|---|---|
| fetch/타입 | 정상 JSON·null·시간·date-only·잘못된 body·timeout·취소·429·502·304 사용 시 캐시 |
| 화면 | loading/empty/error/retry, 정렬 경쟁, 상세404, 큰 글자, 링크 scheme |
| 설치 인증 | 본인 갱신·해지, 타인 ID/토큰 공격, 응답 유실·중복 등록·토큰 충돌 |
| sender | WEB 회귀, provider 분기, mixed ticket 결과, receipt 지연·오류·소실, 429 backoff |
| DB | 기존 WEB 데이터 보존, CHECK/unique, rollback, 재시작 후 receipt 재개 |
| 알림 이동 | foreground·cold start·중복 response·잘못된 payload·삭제된 상세 |
| E2E | mock 목록 → 상세 → 오류 복구 → 설정; 실제 외부 발송 없이 실행 |

서버 변경은 루트 `make lint`, `make test`, disposable DB migration 검증을 실행한다. API 계약 변경은 `make openapi`. 웹 프록시 변경은 `apps/web`에서 `npm run lint`, `node --test tests/*.test.mjs`, `npm run build`를 실행한다. 기존 Python 통합 테스트는 `venv/bin/python apps/api/tests/integration_runtime.py`이며 새 모바일 시나리오는 별도로 추가해야 한다.

T-012 CI를 확장해 mobile lint/typecheck/test·생성 타입 drift 검사를 추가한다. iOS 컴파일은 별도 macOS runner 또는 수동/EAS build로 확인한다. Linux의 TypeScript 통과를 iOS 컴파일 성공으로 표현하지 않는다. PR CI에 Apple·Expo production 비밀이나 실기기 토큰을 넣지 않는다.

### 9.3 더미 일정 + 실제 푸시 리허설

아래는 구현 후 사용자가 실기기 전송을 지시했을 때 수행할 수동 절차다. 현재 `collector test-push`는 Web Push 진단이며 그대로 모바일 발송 도구가 되지 않는다. 신규 진단 명령은 T-041에서 구현하고 help·기본 dry-run·정확한 device_id 선택을 검증한다.

1. 등록한 iPhone 14의 device_id, 빌드 환경, provider를 확인한다. 로그에는 원문 토큰을 남기지 않는다.
2. 전용 테스트 DB/별도 Compose 프로젝트와 collector를 사용하거나, 서버가 강제하는 테스트 audience를 먼저 구현한다. 동일 운영 DB에 더미 일정을 publish하면 기존 모든 WEB 구독으로 갈 수 있다.
3. 테스트 환경에서 운영자 UI로 명확한 더미 제목, 예약 시작 현재+5분 이상, 판매처 테스트 링크를 입력한다. 생성된 release_id/event_id/device_id를 기록한다.
4. dry-run에서 대상이 지정 iPhone 한 대인지 확인한다. 대상 제한을 입증하지 못하면 publish/발송하지 않는다.
5. 게시 후 SCHEDULE_ADDED와 시간 도달 PREORDER_OPEN을 별도 확인한다. 예약 시각을 KST로 입력하고 서버 UTC·tick 시각을 기록한다.
6. delivery 생성 → Expo ticket → provider receipt → 기기 표시 → 탭 상세를 각각 기록한다. receipt는 즉시 없을 수 있다.
7. foreground·background·앱 종료를 각각 수행한다. 집중 모드/알림 요약/소리 설정도 함께 기록하고 표시 지연을 서버 실패로 단정하지 않는다.
8. 알림 끄기 후 다음 테스트 이벤트가 그 기기에 발송되지 않는지 확인한다. 권한 거부·서버 등록 실패의 UI도 확인한다.
9. 기내 모드에서 캐시를 확인한 후 온라인 복구를 확인한다. 스케줄러가 정상일 때 macOS 앱을 닫아도 서버가 계속 실행되는지와 Mac 자체 중단은 구분한다.
10. 정리는 격리 스키마 rollback을 우선한다. 공유 DB는 해당 실행의 정확한 ID만 기록하고, 기존 삭제 규칙·승인 범위를 따른다. 제목 패턴으로 일괄 삭제하지 않는다.

테스트 기록의 필수 항목: commit/build ID, SDK·Xcode·iOS, 기기, API host, 앱 환경, release/event/device ID, 예정 시각, tick·ticket·receipt·표시 시각, 앱 상태, 성공/실패, 남은 문제. 비밀 토큰·키는 제외한다.

### 9.4 TestFlight까지

1. iPhone 개발 빌드의 핵심 흐름과 자동 검사가 통과했는지 확인한다.
2. Apple Developer Program과 App Store Connect에서 고유 bundle ID에 맞는 앱 레코드를 만든다. 앱 이름·기본 언어·SKU·지원/개인정보 URL을 준비한다.
3. Expo production 환경의 Funnel API URL, 프로젝트 ID, 앱 환경을 확인한다. dev·preview·production 기기와 푸시 대상이 섞이지 않게 한다.
4. 아래 명령으로 서명된 iOS 빌드를 만든다. EAS는 업로드/빌드 서비스이므로 해당 사용과 비용을 확인한 뒤 실행한다. CLI 버전은 첫 검증 후 고정한다.

```sh
npx eas-cli@latest build --platform ios --profile production
```

5. 빌드 ID·bundle ID·버전·대상 프로젝트를 확인하고, 선택한 빌드 ID를 제출한다. 실수로 다른 최신 빌드를 올리지 않도록 ID로 지정한다.

```sh
npx eas-cli@latest submit --platform ios --id YOUR_BUILD_ID
```

6. App Store Connect에서 처리 상태·수출 규정 질문·테스트 정보를 실제 앱에 맞게 작성하고 내부 테스터로 본인을 추가한다. 외부 테스트는 별도 검토가 필요할 수 있다.
7. iPhone의 TestFlight에서 설치한다. Metro를 종료한 상태에서 실행·셀룰러·알림·앱 종료 후 탭 이동을 검증한다. 개발 빌드에서 받은 토큰을 수기로 복사하지 말고 설치된 앱이 자체 등록하게 한다.
8. 업로드 성공은 TestFlight 설치나 App Store 공개 성공이 아니다. 각 단계를 별도로 기록한다.

로컬 Xcode Archive와 App Store Connect 업로드도 가능하며 EAS 클라우드가 필수는 아니다. 선택한 경로 하나를 재현 가능하게 기록한다. [스토어 제출](https://docs.expo.dev/deploy/submit-to-app-stores/)

### 9.5 운영 유지와 복구

Funnel 호스트가 바뀌면 앱의 API 주소도 바뀐다. 공개 주소는 한 config에서 관리하고 버전별 호환 API를 유지한다. env 수정만으로 설치된 production 번들이 변경되지는 않으므로 새 빌드 또는 검증된 업데이트 전략이 필요하다. EAS Update는 초기 필수 범위에서 제외한다.

Mac mini 전원·네트워크·Colima·Docker·Funnel 중단은 앱 API와 서버 발송에 영향을 준다. 앱 캐시가 서버 가용성을 대신하지 않는다. App Store 검토와 실제 사용 기간에는 서버가 접근 가능해야 한다. Xcode 빌드와 Simulator가 같은 Mac 자원을 사용하므로 메모리·디스크 부족이 collector tick을 지연시키는지 확인한다.

API·DB는 loopback을 유지한다. 프록시 변경은 production web 재빌드, collector 코드 변경은 재시작, 서버 env 변경은 컨테이너 재생성이 필요하다. 모바일 푸시를 feature flag로 끌 수 있도록 구현하고, 장애 시 WEB까지 끄지 않는 복구 절차를 테스트한다. schema 롤백보다 먼저 sender를 비활성화하고 기존 행 보존을 검토한다.

## 10. 단계별 백로그

기존 ID를 유지하되 Swift 전용 산출물을 Expo 산출물로 대체한다. T-033의 환경 확인·mock 뼈대·Simulator 첫 실행은 구현/검증되었다. 그 밖의 항목은 계획이며 T-033 전체 완료는 아니다. M5·M6 숫자 순서보다 다음 의존성 순서로 실행한다.

| 순서 | 기존 ID | 구현 범위 | 완료 조건 |
|---|---|---|---|
| 0 | T-033 준비 | 도구·SDK·식별자·프로젝트 규칙·기록 | 실제 버전과 지원 iOS 확인, 기존 서비스 변경 없음 |
| 1 | T-033 앱/API | Expo 앱·mock 화면·타입 생성·고정 읽기 프록시 | Simulator/iPhone 목록, 비허용 경로 차단, CI 기초 |
| 2 | T-034 | 디자인 토큰·공통 상태 UI | 다크 모드·VoiceOver·큰 글자 실기기 확인 |
| 3 | T-035 | 피드 정렬·새로고침·오류 복구 | 실제 feed 계약 준수, cursor 없는 API의 무한 스크롤 미표방 |
| 4 | T-036 | 상세·판매처 out-link·404 | 실제 기기 링크·뒤로 이동·삭제 상세 정상; 검색은 후속 |
| 5 | T-039 | 공개 데이터 캐시 | 재실행/기내 모드/만료/온라인404 정리 검증 |
| 6 | T-040 | 설치 인증·토큰 등록·마이그레이션 | 재등록·갱신·해지·타 기기 차단, 기존 WEB 보존 |
| 7 | T-041 | 제공자 선택·sender·receipt·진단 | fake 전 시나리오와 지정 iPhone 실제 전송, 재시작 복구 |
| 8 | T-042 | 권한·푸시 탭·cold start | 앱 세 상태와 잘못된 payload 실기기 검증 |
| 9 | T-043 MVP | 전체 일정 알림 on/off·등록 상태 | OS/서버 상태 차이·실패 복구·해지 검증; 일간 요약 제외 |
| 10 | T-012 확장 / T-033 배포 | 모바일 CI·서명·TestFlight | Metro 없이 셀룰러 실행, 배포 환경 푸시, 회귀 PASS |
| 후속 | T-037 | 계정 세션·Sign in with Apple | T-029 API 이후, 보안 저장·갱신·탈퇴 포함 |
| 후속 | T-038 | 서버 워치리스트 | T-030/031 이후, 매칭/권한/다기기 동기화 |

T-033은 앱 뼈대 완료와 배포 준비 항목을 구분해 기록한다. 전체 완료는 관련 하위 항목이 모두 통과한 뒤 선언한다. T-043의 일간 요약과 T-036의 검색은 보류 항목으로 남겨 전체 과거 요구까지 완료했다고 표시하지 않는다.

### 10.1 다음 작업을 시작할 때의 실행 단위

첫 구현 요청은 **T-033의 환경 확인 + 앱 뼈대 + mock 피드 Simulator 실행**으로 시작한다. 이 단계는 푸시 제공자와 유료 계정이 정해지지 않아도 진행할 수 있다. 다음에는 읽기 프록시와 실제 API 연결, 이후 iPhone UI 검증으로 진행한다. 처음부터 계정·관심 목록·APNs·Android 배포를 한꺼번에 구현하지 않는다.

### 10.2 완료 보고 형식

각 단계마다 변경 파일, 적용한 계약, 검사 명령/결과, Simulator 결과, iPhone 결과, 서버 배포 여부, 미검증 항목, 다음 의존성을 남긴다. 스크린샷 또는 짧은 화면 녹화는 실제 기기 UI 검증 증거로 사용하고 서버 로그와 분리한다. 검증 기록 경로는 `docs/mobile-validation/` 아래 단계별 문서로 만들 계획이다.

## 11. 위험과 대응

| 위험 | 대응 / 중단 기준 |
|---|---|
| Expo와 React/Node 버전 불일치 | SDK 호환 설치·doctor·lockfile; 웹 버전 강제 금지 |
| Mac OS/Xcode가 iPhone OS 미지원 | 지원 조합 확인 후 업데이트/빌드 경로 결정 |
| 개인 인증 없는 토큰 관리 남용 | 설치 관리 인증·제한·충돌 테스트; 공개 출시 전 ADR 검토 |
| ticket을 기기 수신으로 오인 | receipt와 실제 표시를 별도 기록 |
| 테스트가 기존 사용자에게 방송 | 격리 DB 또는 서버 측 audience가 없으면 발송하지 않음 |
| 개발 앱은 되지만 TestFlight 실패 | production 토큰·환경·서명·Metro 없는 네트워크 확인 |
| 기존 Web Push 회귀 | provider 분기·마이그레이션·처리량·feature flag 검증 |
| Mac 빌드 부하가 서비스에 영향 | 메모리·디스크·tick 모니터링, 동시 Simulator 수 제한 |
| 주소 변경 후 구버전 앱 단절 | API base 중앙화·호환 기간·배포 계획 |
| 알림 중복 또는 지연 | 멱등 delivery·상태 추적·tap 중복 억제; exactly-once 미보장 |
| 앱 심사 | 실제 유용한 UI·정확한 개인정보 설명·원문 귀속·살아 있는 서버; 승인 보장 없음 |

## 12. v1 이후 로드맵

Android는 개발 초기에 Emulator에서 동일 화면을 실행해 플랫폼 종속 import를 발견한다. 본격 푸시 검증은 Firebase FCM v1 자격증명, Android package, notification channel과 권한 흐름을 설정한 뒤 진행한다. iOS 성공을 Android 푸시 성공으로 대체하지 않는다. Android 실기기가 없으면 실기기 미검증으로 표시하고 외부 출시 전에 확보한다.

그 이후 계정/관심 목록 → 검색 → 캘린더 UX → 앱 링크 → 위젯 순으로 제품 필요에 따라 진행한다. AWS 이전·자체 도메인은 가용성과 주소 안정성이 필요할 때 별도 진행한다. 현재 자동 수집을 모바일 출시의 선행 조건으로 바꾸지 않는다.

## 13. 용어와 공식 참고 자료

| 용어 | 의미 |
|---|---|
| Expo Go | 빠른 기능 체험용 앱; 이 계획의 원격 푸시 검증 대상 아님 |
| Development build | OROT 네이티브 설정과 개발 도구가 포함된 설치 앱 |
| Metro | 개발 JavaScript 번들 서버; OROT API 서버와 별개 |
| CNG / prebuild | app config와 plugin으로 iOS/Android 프로젝트 생성 |
| EAS Build / Submit | 앱 바이너리 빌드 / 스토어 업로드; 백엔드 호스팅 아님 |
| APNs / FCM | Apple / Google 푸시 전달 서비스 |
| Expo token | Expo 프로젝트 범위의 전송 주소; APNs token과 다름 |
| Ticket / Receipt | Expo 접수 / APNs·FCM 인계 결과; 사용자 표시 보장 아님 |
| TestFlight | App Store Connect 기반 iOS 베타 배포 |

공식 문서는 2026-09-13 확인 기준이며 실제 구현 시 선택 SDK 문서를 다시 확인한다. 코드 계약은 저장소 소스와 OpenAPI를 우선한다.

- [Expo 프로젝트 생성](https://docs.expo.dev/get-started/create-a-project/)
- [Development build와 로컬 실행](https://docs.expo.dev/develop/development-builds/introduction/)
- [Simulator](https://docs.expo.dev/workflow/ios-simulator/) · [Developer Mode](https://docs.expo.dev/guides/ios-developer-mode/)
- [푸시 설정](https://docs.expo.dev/push-notifications/push-notifications-setup/) · [발송과 receipts](https://docs.expo.dev/push-notifications/sending-notifications/)
- [환경변수](https://docs.expo.dev/guides/environment-variables/) · [EAS profiles](https://docs.expo.dev/build/eas-json/)
- [단위 테스트](https://docs.expo.dev/develop/unit-testing/) · [스토어 제출](https://docs.expo.dev/deploy/submit-to-app-stores/)
