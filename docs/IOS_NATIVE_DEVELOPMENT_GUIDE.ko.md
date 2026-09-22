# OROT — 혼자 만드는 Swift iOS 네이티브 앱 가이드

> 작성일: 2026-09-22
> 대상: TypeScript·React 개발 경험이 있고 Swift·Xcode는 처음인 개발자
> 목표: 기존 OROT 서버를 이용해 피드 → 상세 → 판매처 링크 → 알림 → 상세 이동을 직접 구현한다.
> 문서 성격: 학습과 구현을 위한 제안서. 기존 Expo 앱, ADR, 블루프린트의 확정 상태를 변경하지 않는다.

이 문서는 새 문서 한 개만 추가하는 요청에 맞춰 작성했다. 아래 폴더, Swift 파일, API 확장, Xcode 설정은 **앞으로 직접 만들 내용**이다. 이 문서 작성으로 앱 프로젝트나 네이티브 푸시가 생성되지는 않는다. 현재 저장소에는 다른 작업의 수정 사항이 있으므로, 실제 개발을 시작할 때도 변경 범위를 먼저 확인한다.

처음부터 모든 항목을 이해할 필요는 없다. 1~6장을 읽고 개발 환경을 준비한 다음, 7~9장의 예제로 실제 목록과 상세를 띄워 본다. 그 뒤 일정 표시, 디자인, 캐시, 알림을 한 단계씩 보완한다. 각 단계 끝의 완료 기준을 통과하면 다음 단계로 넘어간다.

**문서 검증 기록:** 7~8장의 최소 앱 Swift 파일 6개를 임시 디렉터리로 추출해 Xcode 27.0의 iOS Simulator SDK, Swift 6 모드, iOS 17 deployment target으로 `swiftc -typecheck`를 실행했고 통과했다. 로컬 문서 링크와 목차 연결도 확인했다. 이는 타입 검사이며 Xcode 프로젝트의 빌드·서명·Simulator 실행·실서버 연결·실기기 푸시 검증은 아니다. 후반부의 확장 예제와 테스트 예제는 이 6개 파일 검사에 포함되지 않는다.

## 목차

1. [현재 구현과 목표 범위](#1-현재-구현과-목표-범위)
2. [TypeScript에서 Swift로 넘어가기](#2-typescript에서-swift로-넘어가기)
3. [전체 시스템과 데이터 흐름](#3-전체-시스템과-데이터-흐름)
4. [Xcode 준비와 프로젝트 생성](#4-xcode-준비와-프로젝트-생성)
5. [파일과 폴더 구조](#5-파일과-폴더-구조)
6. [화면 상태와 책임 나누기](#6-화면-상태와-책임-나누기)
7. [첫 구현: 모델과 API](#7-첫-구현-모델과-api)
8. [첫 구현: 피드와 상세 화면](#8-첫-구현-피드와-상세-화면)
9. [예제 실행과 확장 순서](#9-예제-실행과-확장-순서)
10. [OROT 일정과 가격을 정확하게 표시하기](#10-orot-일정과-가격을-정확하게-표시하기)
11. [디자인과 접근성](#11-디자인과-접근성)
12. [캐시와 오프라인](#12-캐시와-오프라인)
13. [네이티브 푸시의 전체 흐름](#13-네이티브-푸시의-전체-흐름)
14. [테스트와 디버깅](#14-테스트와-디버깅)
15. [실기기와 TestFlight](#15-실기기와-testflight)
16. [혼자 진행하는 단계별 작업표](#16-혼자-진행하는-단계별-작업표)
17. [문제 해결과 작업 습관](#17-문제-해결과-작업-습관)
18. [참고 파일과 공식 자료](#18-참고-파일과-공식-자료)

## 1. 현재 구현과 목표 범위

### 1.1 무엇을 재사용할 수 있나

2026-09-22 작업 트리의 소스와 문서를 기준으로 확인한 내용이다. 실제 운영 서버가 같은 코드를 실행 중인지는 별도로 확인해야 한다.

| 영역 | 확인한 현재 상태 | Swift 앱 개발 시 할 일 |
|---|---|---|
| Python API·PostgreSQL | 공개 발매 일정 조회, 운영자 일정 관리 | 기존 API 이용 |
| Next.js 공개 경계 | `/api/mobile/v1/*` 고정 GET 프록시 | 동일 HTTPS 주소로 요청 |
| Expo 앱 | 실제 피드·상세·설정 화면과 테마, API 타입·검증 코드 | 화면 동작과 규칙을 참고해 Swift로 작성 |
| 일정 발송 | 기존 Web Push와 서버 스케줄러 | 향후 APNs 전송 경로 추가 |
| iOS 기기 등록 | DB에 IOS 구분은 있지만 네이티브 등록·발송 흐름은 미구현 | 인증·환경 구분·등록 API·sender 설계 및 구현 |
| 네이티브 배포 | Swift 앱·서명·TestFlight는 이 가이드의 후속 작업 | Xcode 프로젝트부터 준비 |

TypeScript 코드를 Swift로 자동 번역하려고 하기보다, 기존 코드에서 **입력, 출력, 화면 상태, 예외 처리**를 읽어 옮긴다. 디자인 색상과 문구는 참고할 수 있지만 React 컴포넌트와 CSS를 SwiftUI에 그대로 넣을 수는 없다.

### 1.2 첫 버전의 범위

첫 버전은 로그인 없이 사용하도록 구성한다.

- 임박순·최근 변경순 피드와 새로고침.
- 발매 상세, 일정 상태, 판매처 원문 링크.
- 로딩·빈 결과·네트워크 오류·삭제 또는 비공개된 상세 처리.
- 마지막 성공 데이터의 오프라인 읽기.
- 전체 일정 알림 켜기·끄기와 알림 탭 후 상세 이동.
- 다크 모드·큰 글자·VoiceOver 및 실기기 검증.

계정, 관심 음반별 서버 알림, 결제, 자동 수집, Android, 위젯은 이후 단계로 둔다. 로컬 즐겨찾기를 추가해도 그 음반만 알림을 받는 기능이 생기는 것은 아니다.

### 1.3 기존 문서와의 관계

현재 [ADR-0009](adr/0009-expo-mobile-app.md), [모바일 블루프린트](MOBILE_BLUEPRINT.ko.md), [한국어 블루프린트](BLUEPRINT.ko.md), [영문 블루프린트](BLUEPRINT.en.md)는 Expo 방향을 기록한다. 이 가이드는 그것을 몰래 확정 변경하지 않는다.

실제 저장소의 공식 개발 방향을 전환할 때에는 별도 작업으로 Swift 전환 ADR을 남기고, 지원 iOS·앱 식별자·APNs·익명 설치 인증 등 결정을 기록한 뒤 양쪽 블루프린트와 작업 완료 조건을 맞춘다. 학습용 화면·읽기 API 구현은 푸시 인증 설계를 기다리지 않고 진행할 수 있다.

## 2. TypeScript에서 Swift로 넘어가기

### 2.1 익숙한 개념과 연결하기

| TypeScript / React | Swift / SwiftUI | 이해할 때 주의할 점 |
|---|---|---|
| `const` / `let` | `let` / `var` | Swift `let`은 재대입 불가, `var`는 변경 가능 |
| `interface`의 데이터 형태 | `struct` | Swift 구조체는 주로 값으로 전달됨 |
| `string \| null` | `String?` | 값이 없을 수 있음을 타입에 표시 |
| optional chaining | `?.`, `if let`, `guard let` | Optional을 강제 해제하는 `!`는 가급적 피하기 |
| JSON 응답 타입 | `Decodable` 모델 | 디코딩은 실행 시 타입 오류도 확인함 |
| React 함수 컴포넌트 | `struct ...: View` | `body`는 현재 상태의 화면을 선언 |
| `useState` | `@State` | 뷰 생명주기에 속한 상태 보관 |
| 입력값·props | 뷰의 저장 프로퍼티 | `let release: ReleaseDTO`처럼 전달 |
| 상태 수정 콜백 | `@Binding` | 부모 상태를 자식에서 편집할 때 사용 |
| 공유 상태 객체 | `@Observable` 객체 | 읽힌 상태가 바뀌면 관련 화면 갱신 |
| `useEffect`의 일부 역할 | `.task`, `.task(id:)`, `.onChange` | 완전한 일대일 대응은 아님 |
| `Promise<T>` | `async throws -> T` | `await`는 기다림, `try`는 실패 가능성 |
| `fetch` | `URLSession` | 응답 상태·형식·취소는 직접 처리 |
| Router | `NavigationStack` | 화면 경로와 상세 ID를 앱 상태로 관리 |

`Codable`은 `Encodable + Decodable`이다. 응답을 읽기만 하면 `Decodable`로 충분하지만, 아래 예제는 나중에 공개 응답을 캐시하기 쉽게 `Codable`을 사용한다. 타입 검증이 성공해도 “양수 ID”, “공개 상태”, “안전한 링크” 같은 제품 규칙은 별도로 검사해야 한다.

### 2.2 Optional부터 익히기

```swift
let artistName: String? = nil
let label = artistName ?? "아티스트 정보 없음"

if let artistName {
    print(artistName)
}
```

`artistName!`로 강제로 꺼내면 값이 없을 때 앱이 종료될 수 있다. API에서 누락될 수 있는 아티스트, 이미지, 날짜는 Optional로 모델링하고 대체 표시를 정한다.

### 2.3 구조체와 클래스

API 응답처럼 하나의 데이터 묶음은 `struct`로 시작한다. 여러 화면 갱신 동안 같은 정체성을 유지해야 하는 화면 상태는 `@Observable class`로 만든다.

`@MainActor`는 화면 상태를 갱신하는 실행 영역을 명확하게 한다. 네트워크 호출에 `await`를 사용하면 대기 중 UI 실행을 막지 않는다. 다만 큰 JSON 처리나 이미지 변환 같은 CPU 작업이 자동으로 백그라운드로 옮겨지는 것은 아니다.

이 가이드는 학습을 쉽게 하기 위해 API 서비스와 화면 모델을 `@MainActor`에 맞춘다. 피드 50개 규모의 첫 구현에 쓰는 출발점이며, 측정 결과에 따라 무거운 처리와 캐시 I/O를 별도 actor로 분리한다. Swift 동시성 경고를 `@unchecked Sendable`로 덮지 말고 어떤 상태를 어디서 접근하는지 먼저 확인한다.

### 2.4 최소 학습 순서

1. `let`, `var`, 함수, 배열, 구조체.
2. Optional, `if let`, `guard`, 오류 던지기.
3. `Codable`, `CodingKeys`, JSON 디코딩.
4. `async/await`, 취소, `@MainActor`.
5. SwiftUI `Text`, `VStack`, `List`, `Button`.
6. `@State`, `@Observable`, 화면 이동.
7. 테스트, 파일 캐시, 알림.

언어 문법을 모두 공부한 뒤 앱을 만들 필요는 없다. 각 개념을 아래 피드 구현에 바로 적용한다.

## 3. 전체 시스템과 데이터 흐름

### 3.1 앱 실행과 읽기 요청

```text
OROTApp                         앱 실행, 공통 의존성 생성
  └─ FeedView                   사용자가 목록을 봄
       └─ FeedModel.load()      로딩·성공·실패 상태 관리
            └─ APIClient       HTTPS 요청과 JSON 디코딩
                 ↓
https://<공개 호스트>/api/mobile/v1/feed
                 ↓
Tailscale Funnel → Next.js의 고정 모바일 프록시
                 ↓
FastAPI /v1/feed → PostgreSQL
                 ↓
JSON → FeedPageDTO → FeedModel 상태 변경 → SwiftUI 화면 갱신
```

Swift 앱은 Mac mini의 DB에 직접 연결하지 않는다. `http://api:8000`은 Docker 내부 주소이며 iPhone이 사용하는 주소가 아니다. iPhone의 `localhost`는 iPhone 자신이다.

공개 주소는 `tailscale funnel status`로 확인할 수 있다. 서버의 API 8000·DB 5432를 공개하거나 CORS를 무제한 허용하는 방식으로 모바일 연결을 해결하지 않는다. 기존 HTTPS 프록시를 이용한다.

### 3.2 실제 공개 읽기 계약

| 공개 경로 | 응답 / 동작 | 앱에서 사용 |
|---|---|---|
| `GET /api/mobile/v1/feed?sort=imminent&limit=50` | `{items, generated_at}` | 임박순 목록 |
| `GET /api/mobile/v1/feed?sort=recent&limit=50` | 같은 형태 | 최근 변경순 목록 |
| `GET /api/mobile/v1/releases?limit=50` | `{items, next_cursor}` | 전체 목록을 별도 구현할 때 |
| `GET /api/mobile/v1/releases/{id}` | 공개 발매 상세, 없거나 비공개면 404 | 상세 진입 시 새로 조회 |

피드에는 cursor가 없다. 피드에 무한 스크롤을 붙이고 싶다면 먼저 계약 변경이 필요하다. `releases`의 `from`, `to`는 발매일 기준이므로 예약 시작일 필터와 혼동하지 않는다. 내부 OpenAPI에는 `/v1/...`로 기록되고, 앱에서는 공개 프록시 접두사 `/api/mobile`를 더한다.

### 3.3 알림 흐름은 별개

```text
운영자 일정 등록·변경 → 서버 이벤트와 발송 대상 선정
  ├─ 기존 WebPushSender → 브라우저
  └─ 향후 APNs sender → Apple APNs → iPhone 알림
                                          ↓ 탭
                             앱 라우터 → release ID → 상세 API
```

앱이 켜져 있어야만 예약 시각을 감시하는 구조로 만들지 않는다. 예약 시점 판단과 발송은 서버 책임이다. 앱의 로컬 타이머는 서버 일정 변경이나 앱 종료를 안정적으로 처리할 수 없다.

## 4. Xcode 준비와 프로젝트 생성

### 4.1 개발 환경 확인

Mac에는 Xcode와 필요한 iOS Simulator 런타임을 설치한다. 아래는 버전·경로를 읽는 명령이다.

```sh
xcodebuild -version
xcrun swift --version
xcode-select -p
```

문서 작성 환경에서는 Xcode 27.0, Apple Swift 6.4가 확인되었다. 이는 이 Mac의 관찰값이며 모든 개발자의 필수 버전은 아니다. 설치 가능한 Xcode는 macOS 버전에 영향을 받고, App Store 업로드 요구 사항은 바뀔 수 있으므로 배포 시점에 공식 문서를 다시 확인한다.

이 가이드의 예제는 **iOS 17 이상**을 학습용 기준으로 삼는다. SwiftUI Observation을 사용하기 위한 기준이다. 실제 서비스의 최소 지원 버전이 확정되었다는 의미는 아니다. [Observation 지원 범위](https://developer.apple.com/documentation/SwiftUI/Managing-model-data-in-your-app)

### 4.2 새 프로젝트 만들기

1. Xcode에서 **Create New Project** 또는 **File → New → Project**를 선택한다.
2. iOS의 **App** 템플릿을 선택한다.
3. Product Name은 `OROT`, Interface는 **SwiftUI**, Language는 **Swift**로 한다.
4. Storage 선택이 있다면 첫 단계에서는 **None**으로 한다. SwiftData는 지금 필요하지 않다.
5. 테스트 선택이 있다면 Swift Testing 단위 테스트와 XCTest UI 테스트를 포함한다.
6. Organization Identifier는 본인이 관리할 reverse-DNS 형식을 정한다. `com.example` 같은 예시를 배포용으로 그대로 쓰지 않는다.
7. 이미 Git 저장소 안에서 작업하므로 새 Git 저장소 생성 옵션은 끈다.
8. 저장 후 최종 경로가 `apps/ios/OROT.xcodeproj`와 `apps/ios/OROT/`가 되도록 배치한다. Xcode가 프로젝트 이름 폴더를 한 겹 더 만들 수 있으므로 Finder에서 확인한다.
9. 앱 target의 General에서 iOS Deployment Target을 예제 기준인 17.0 이상으로 맞춘다.
10. 프로젝트 설정에서 Swift Language Version을 확인한다. 예제는 Swift 6 동시성 검사를 염두에 두고 작성했다.
11. Simulator를 실행 대상으로 선택하고 `⌘R`로 기본 화면을 실행한다.

처음엔 Signing 때문에 실제 iPhone 실행이 막혀도 Simulator로 화면 학습을 진행할 수 있다. 실기기 서명은 15장에서 다룬다.

### 4.3 Xcode의 단어 이해하기

| 용어 | 의미 |
|---|---|
| Project | 소스 파일, target, 빌드 설정을 묶는 프로젝트 |
| Target | 앱이나 테스트처럼 실제로 만드는 결과물 단위 |
| Scheme | 어떤 target을 어떤 설정으로 실행·테스트할지 정한 묶음 |
| Build Configuration | Debug·Release 같은 빌드별 설정 |
| Deployment Target | 앱을 설치할 수 있는 최소 iOS |
| SDK | 컴파일할 때 사용하는 Apple API 묶음 |
| Signing | 누가 만든 앱이며 어떤 기능을 사용할 수 있는지 서명하는 과정 |
| Bundle Identifier | Apple 시스템에서 앱을 구분하는 고유 식별자 |

최신 SDK로 컴파일하면서 더 낮은 iOS를 지원할 수 있다. 단, 화면에서 호출하는 API가 최소 지원 버전에서 제공되는지 확인해야 한다.

### 4.4 기존 Expo 앱과 분리

`apps/mobile/ios/`는 Expo prebuild가 생성·관리하는 위치다. 독립 Swift 앱을 그 안에 넣으면 생성 과정과 충돌할 수 있다. 이 가이드에서는 별도 `apps/ios/`를 제안한다.

Swift 앱의 UI·API 동작을 비교할 때 기존 Expo 앱을 참고한다. 전환 검증이 끝나기 전에 기존 폴더나 테스트를 지우지 않는다.

**완료 기준:** Xcode에서 빈 SwiftUI 앱이 Simulator에 뜨고, 프로젝트의 실제 디스크 위치를 설명할 수 있다.

## 5. 파일과 폴더 구조

### 5.1 첫날 만들 최소 구조

아래 6개 Swift 파일이 7~8장의 예제에 대응한다. 폴더를 먼저 전부 만들기보다 해당 파일을 작성할 때 폴더를 추가해도 된다.

```text
apps/ios/                               앞으로 만들 독립 iOS 프로젝트
├── OROT.xcodeproj/                      Xcode 프로젝트 설정
├── OROT/
│   ├── App/
│   │   └── OROTApp.swift                @main 진입점과 API 설정
│   ├── Core/
│   │   ├── Models/
│   │   │   └── ReleaseDTO.swift         피드·발매·판매처 응답 모델
│   │   └── Networking/
│   │       └── APIClient.swift          통신, 오류, 서비스 protocol
│   ├── Features/
│   │   ├── Feed/
│   │   │   ├── FeedModel.swift          피드 상태와 로딩
│   │   │   └── FeedView.swift           목록·정렬·화면 이동
│   │   └── ReleaseDetail/
│   │       └── ReleaseDetailView.swift  ID로 상세 조회
│   └── Resources/
│       └── Assets.xcassets/             색상·아이콘·이미지
├── OROTTests/                           단위·통합 테스트 target
└── OROTUITests/                         UI 테스트 target
```

Xcode 템플릿이 이미 만든 `OROTApp.swift`를 이동하거나 내용을 바꾼다. 같은 이름의 `@main` 파일을 하나 더 만들면 앱 진입점이 중복된다. 기본 `ContentView.swift`는 예제에서 사용하지 않으므로 새 iOS 프로젝트 안에서 정리할 수 있다.

### 5.2 기능이 늘어난 뒤의 권장 구조

다음은 확장 설계다. 지금 구현되었다는 의미가 아니다.

```text
apps/ios/
├── OROT.xcodeproj/
├── Config/
│   ├── Debug.xcconfig                  개발용 공개 설정
│   └── Release.xcconfig                배포용 공개 설정
├── OROT/
│   ├── App/
│   │   ├── OROTApp.swift
│   │   ├── AppDependencies.swift       API·캐시·서비스 생성과 주입
│   │   ├── AppRouter.swift             탭과 상세 경로·대기 중 딥링크
│   │   └── AppDelegate.swift           APNs 토큰·시스템 알림 콜백
│   ├── Core/
│   │   ├── Models/                     ReleaseDTO·FeedPageDTO·LinkDTO
│   │   ├── Networking/                 APIClient·APIError·AppConfiguration
│   │   ├── Repositories/               네트워크·캐시 조합; 필요할 때 추가
│   │   ├── Persistence/                FeedCache·KeychainStore
│   │   ├── Notifications/              권한·등록·알림 payload 검증
│   │   └── Formatting/                 날짜·시각·가격·일정 상태 표시
│   ├── DesignSystem/
│   │   ├── Theme.swift                 의미별 색상·간격·타이포그래피
│   │   └── Components/                 표지·오류·빈 화면·배지
│   ├── Features/
│   │   ├── Feed/                       FeedView·FeedModel·ReleaseRow
│   │   ├── ReleaseDetail/              DetailView·DetailModel
│   │   └── Settings/                   SettingsView·NotificationSettingsModel
│   └── Resources/
│       ├── Assets.xcassets/
│       ├── Localizable.xcstrings       UI 문구·번역 관리
│       └── PrivacyInfo.xcprivacy       실제 API 사용에 따라 필요한 선언
├── OROTTests/
│   ├── Models/
│   ├── Networking/
│   ├── Features/
│   ├── Notifications/
│   ├── Doubles/                        FakeReleaseService 등
│   └── Fixtures/                       공개 API 모양의 합성 JSON
└── OROTUITests/
    └── FeedFlowTests.swift
```

`PrivacyInfo.xcprivacy`는 빈 파일을 추가했다고 준비가 끝나는 항목이 아니다. 실제 앱과 의존성의 required-reason API 사용 등을 확인해서 작성한다. APNs를 추가하면 Xcode가 관리하는 entitlements 파일도 생긴다.

### 5.3 파일을 어디에 둘지 결정하는 기준

- 특정 화면에서만 쓰면 `Features/그화면/`에 둔다.
- 피드와 상세가 함께 쓰는 날짜 표시라면 `Core/Formatting/`에 둔다.
- 모양이 여러 화면에서 반복되면 `DesignSystem/Components/`에 둔다.
- HTTP 상태 코드 처리는 `Core/Networking/`에 둔다.
- 앱 전체 이동 경로는 `AppRouter`가 관리한다.
- 기기 비밀의 저장·삭제는 `KeychainStore`에 둔다.

처음부터 모든 기능을 protocol·repository·use case로 나누지 않는다. 실제 통신과 테스트용 가짜 통신을 바꾸기 위한 protocol 하나부터 시작해도 충분하다.

### 5.4 Xcode 폴더와 target membership

Finder에 파일이 있다고 반드시 컴파일되는 것은 아니다. 프로젝트의 폴더 동기화 방식 또는 File Inspector의 **Target Membership**을 확인한다. 앱 코드는 앱 target, 테스트 코드는 테스트 target에 들어가야 한다.

fixture JSON은 테스트 bundle의 리소스로 포함한다. Keychain 비밀, `.env`, APNs `.p8` 키, 실기기 토큰은 리소스에 추가하지 않는다. 기본 Info.plist는 Xcode가 빌드 설정으로 생성할 수 있으므로, 파일이 안 보인다고 새 plist를 무조건 만들지 않는다.

향후 Git에 포함할 것은 소스·리소스·프로젝트 설정·공유 scheme이다. DerivedData, 빌드 산출물, 개인 `xcuserdata`, 비밀 파일은 제외한다. 실제 앱 추가 시 기존 `.gitignore` 패턴이 `apps/ios`까지 무시하는지도 `git check-ignore -v`로 확인한다.

## 6. 화면 상태와 책임 나누기

### 6.1 화면 상태가 먼저다

피드를 “배열 하나”로만 생각하면 빈 결과와 로딩 중을 구분하기 어렵다. 다음 상태를 먼저 정한다.

| 상황 | 화면 | 사용자 동작 |
|---|---|---|
| 처음 진입 | 로딩 표시 | 기다림 |
| 조회 성공·0개 | 등록된 일정 없음 | 새로고침 |
| 조회 성공·1개 이상 | 목록 | 상세 선택 |
| 초기 조회 실패 | 오류 설명 | 재시도 |
| 기존 목록이 있는 상태에서 갱신 실패 | 이전 목록 + 갱신 실패 안내 | 다시 갱신 |
| 화면 이동으로 요청 취소 | 오류 팝업 없음 | 이동 계속 |

아래 최소 예제는 정렬 간 데이터 혼합을 피하려고 새 조회 시 목록을 지운다. 마지막 성공 목록을 유지하는 개선은 12장에서 다룬다. 예제의 생략 사항을 완성된 제품 동작으로 오해하지 않는다.

### 6.2 한 번의 요청을 따라가기

1. `FeedView`에서 정렬값이 바뀐다.
2. `.task(id: sort)`가 새 로딩을 시작하고 이전 작업은 취소한다.
3. `FeedModel`이 로딩 상태를 표시한다.
4. 서비스가 요청을 만들고 `URLSession`으로 보낸다.
5. HTTP 응답을 검사한 다음 JSON을 디코딩한다.
6. 최신 요청인지, 취소되지 않았는지 검사한다.
7. `items` 또는 오류 메시지가 바뀐다.
8. SwiftUI가 해당 상태를 읽는 화면을 갱신한다.

`body` 안에서 직접 네트워크 요청을 실행하지 않는다. `body`는 자주 다시 계산된다. 네트워크 시작은 `.task`, 버튼, 새로고침처럼 명시적인 동작에 연결한다.

### 6.3 의존성 주입은 무엇인가

화면 모델 안에서 `APIClient()`를 직접 만들면 테스트에서도 실제 서버를 호출하기 쉽다. 대신 `ReleaseService`를 바깥에서 전달한다. 앱 실행 시에는 APIClient, 테스트와 Preview에서는 FakeReleaseService를 전달한다.

처음에는 “필요한 도구를 생성자 인자로 받는다” 정도로 이해하면 된다.

## 7. 첫 구현: 모델과 API

> 7~8장은 함께 사용하는 최소 예제다. 파일 경로 주석을 따라 6개 파일로 나눈다. API 주소 한 곳을 본인의 실제 공개 주소로 바꿔야 한다. 날짜는 첫 연결 단계에서 문자열로 보관하며 10장에서 표시를 개선한다. 아래 예제만으로 푸시·캐시·배포가 완성되지는 않는다.

### 7.1 응답 모델

API의 `snake_case`와 Swift의 `camelCase`를 `CodingKeys`로 명시적으로 연결한다. 예제는 화면에 쓰는 필드만 읽으며, 서버가 추가로 보내는 다른 필드는 디코더가 무시한다.

```swift
// File: OROT/Core/Models/ReleaseDTO.swift
import Foundation

struct ReleaseLinkDTO: Codable, Identifiable, Sendable {
    let id: Int
    let shopName: String
    let url: String
    let priceKrw: Int?

    enum CodingKeys: String, CodingKey {
        case id, url
        case shopName = "shop_name"
        case priceKrw = "price_krw"
    }

    var safeURL: URL? {
        guard let result = URL(string: url),
              let scheme = result.scheme?.lowercased(),
              ["http", "https"].contains(scheme),
              let host = result.host, !host.isEmpty,
              result.user == nil, result.password == nil else { return nil }
        return result
    }
}

struct ReleaseDTO: Codable, Identifiable, Sendable {
    let id: Int
    let title: String
    let artistName: String?
    let variant: String?
    let isPublished: Bool
    let scheduleStatus: String?
    let untilSoldOut: Bool?
    let releaseDate: String?
    let preorderOpensAt: String?
    let preorderClosesAt: String?
    let links: [ReleaseLinkDTO]

    enum CodingKeys: String, CodingKey {
        case id, title, variant, links
        case artistName = "artist_name"
        case isPublished = "is_published"
        case scheduleStatus = "schedule_status"
        case untilSoldOut = "until_sold_out"
        case releaseDate = "release_date"
        case preorderOpensAt = "preorder_opens_at"
        case preorderClosesAt = "preorder_closes_at"
    }
}

struct FeedItemDTO: Codable, Identifiable, Sendable {
    let kind: String
    let at: String
    let eventType: String?
    let release: ReleaseDTO
    var id: Int { release.id }

    enum CodingKeys: String, CodingKey {
        case kind, at, release
        case eventType = "event_type"
    }
}

struct FeedPageDTO: Codable, Sendable {
    let items: [FeedItemDTO]
    let generatedAt: String

    enum CodingKeys: String, CodingKey {
        case items
        case generatedAt = "generated_at"
    }
}
```

현재 피드는 발매당 한 줄이므로 `release.id`를 목록 ID로 쓴다. 향후 알림 이력 화면의 ID까지 발매 ID로 묶어서는 안 된다. 한 발매에 여러 이벤트가 생길 수 있기 때문이다.

새 일정 필드 두 개는 이전 배포 응답도 읽을 수 있도록 Optional로 두었다. `scheduleStatus`를 String으로 둔 것은 미지의 새 값 때문에 전체 피드 디코딩이 실패하지 않게 하기 위한 초기 선택이다. 다음 단계에서는 원문을 보존하면서 `unknown`을 지원하는 도메인 상태로 바꾸고 대체 표시를 테스트한다.

### 7.2 네트워크와 오류

```swift
// File: OROT/Core/Networking/APIClient.swift
import Foundation

enum FeedSort: String, CaseIterable, Identifiable, Sendable {
    case imminent, recent
    var id: String { rawValue }
    var title: String { self == .imminent ? "발매 임박순" : "최근 변경순" }
}

enum APIError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case http(Int)
    case decoding

    var errorDescription: String? {
        switch self {
        case .invalidURL: "API 주소를 확인해 주세요."
        case .invalidResponse: "서버 응답 형식을 확인할 수 없습니다."
        case .http(404): "일정을 찾을 수 없습니다."
        case .http(429): "요청이 많습니다. 잠시 후 다시 시도해 주세요."
        case .http: "일정을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
        case .decoding: "일정 정보의 형식이 예상과 다릅니다."
        }
    }
}

@MainActor
protocol ReleaseService {
    func feed(sort: FeedSort) async throws -> FeedPageDTO
    func release(id: Int) async throws -> ReleaseDTO
}

@MainActor
final class APIClient: ReleaseService {
    private let baseURL: URL
    private let session: URLSession

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func feed(sort: FeedSort) async throws -> FeedPageDTO {
        let page: FeedPageDTO = try await get("v1/feed", query: [
            URLQueryItem(name: "sort", value: sort.rawValue),
            URLQueryItem(name: "limit", value: "50")
        ])
        guard page.items.allSatisfy({ $0.release.id > 0 && $0.release.isPublished }),
              Set(page.items.map(\.id)).count == page.items.count else {
            throw APIError.invalidResponse
        }
        return page
    }

    func release(id: Int) async throws -> ReleaseDTO {
        guard id > 0 else { throw APIError.invalidURL }
        let release: ReleaseDTO = try await get("v1/releases/\(id)")
        guard release.id == id, release.isPublished else {
            throw APIError.invalidResponse
        }
        return release
    }

    private func get<T: Decodable>(
        _ path: String, query: [URLQueryItem] = []
    ) async throws -> T {
        let endpoint = baseURL.appendingPathComponent(path)
        guard var parts = URLComponents(url: endpoint, resolvingAgainstBaseURL: false)
        else { throw APIError.invalidURL }
        if !query.isEmpty { parts.queryItems = query }
        guard let url = parts.url else { throw APIError.invalidURL }

        var request = URLRequest(url: url)
        request.timeoutInterval = 12
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await session.data(for: request)
        try Task.checkCancellation()
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            throw APIError.http(http.statusCode)
        }
        guard http.mimeType?.lowercased() == "application/json" else {
            throw APIError.invalidResponse
        }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError.decoding
        }
    }
}
```

`URLSession`이 비동기 요청을 제공해도 404·429를 앱의 오류로 바꾸는 처리는 직접 해야 한다. 초기 예제는 자동 재시도 없이 사용자가 재시도한다. 출시 전에는 429의 `Retry-After`를 읽어 재시도 버튼의 대기 시간을 반영하고, 요청 폭주를 막는다. [Apple URLSession 문서](https://developer.apple.com/documentation/foundation/urlsession)

이 코드는 고정된 공개 GET 요청만 한다. 향후 인증을 넣을 때 범용 URL 입력 기능이나 관리자 키를 추가하지 않는다. 네이티브 기기 쓰기는 별도 인증 경계를 설계한다.

## 8. 첫 구현: 피드와 상세 화면

### 8.1 피드 상태

```swift
// File: OROT/Features/Feed/FeedModel.swift
import Foundation
import Observation

@MainActor
@Observable
final class FeedModel {
    private(set) var items: [FeedItemDTO] = []
    private(set) var isLoading = false
    private(set) var message: String?
    @ObservationIgnored private let service: any ReleaseService
    @ObservationIgnored private var revision = 0

    init(service: any ReleaseService) { self.service = service }

    func load(sort: FeedSort) async {
        revision += 1
        let requestRevision = revision
        isLoading = true
        message = nil
        items = []
        defer {
            if revision == requestRevision { isLoading = false }
        }
        do {
            let page = try await service.feed(sort: sort)
            try Task.checkCancellation()
            guard revision == requestRevision else { return }
            items = page.items
        } catch {
            guard revision == requestRevision, !Task.isCancelled else { return }
            if error is CancellationError { return }
            if let urlError = error as? URLError, urlError.code == .cancelled { return }
            message = (error as? APIError)?.errorDescription
                ?? "연결하지 못했습니다. 네트워크를 확인하고 다시 시도해 주세요."
        }
    }
}
```

`revision`은 이전 요청이 늦게 도착해 새 정렬 결과를 덮어쓰지 못하게 한다. 네트워크 취소만으로 모든 경쟁 상태가 사라진다고 가정하지 않는다. `private(set)`은 화면에서는 읽을 수 있지만 값을 바꾸는 책임은 모델에 남긴다는 뜻이다.

### 8.2 피드 화면

```swift
// File: OROT/Features/Feed/FeedView.swift
import SwiftUI

@MainActor
struct FeedView: View {
    private let service: any ReleaseService
    @State private var model: FeedModel
    @State private var sort: FeedSort = .imminent
    @State private var retryVersion = 0

    init(service: any ReleaseService) {
        self.service = service
        _model = State(initialValue: FeedModel(service: service))
    }

    var body: some View {
        NavigationStack {
            VStack {
                Picker("정렬", selection: $sort) {
                    ForEach(FeedSort.allCases) { sort in
                        Text(sort.title).tag(sort)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)

                List {
                    if model.isLoading {
                        ProgressView("일정 불러오는 중")
                    } else if let message = model.message {
                        Text(message)
                        Button("다시 시도") { retryVersion += 1 }
                    } else if model.items.isEmpty {
                        Text("아직 등록된 일정이 없습니다.")
                    } else {
                        ForEach(model.items) { item in
                            NavigationLink(value: item.release.id) {
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(item.release.title).font(.headline)
                                    Text(item.release.artistName ?? "아티스트 정보 없음")
                                        .font(.subheadline)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
                .refreshable { await model.load(sort: sort) }
            }
            .navigationTitle("OROT")
            .navigationDestination(for: Int.self) { id in
                ReleaseDetailView(id: id, service: service)
            }
            .task(id: "\(sort.rawValue)-\(retryVersion)") {
                await model.load(sort: sort)
            }
        }
    }
}
```

`@State`는 모델을 뷰 생명주기에 보관하고, `@Observable`은 모델의 변경을 관찰한다. 이 조합의 개념은 Apple의 [모델 데이터 관리](https://developer.apple.com/documentation/SwiftUI/Managing-model-data-in-your-app) 설명을 참고한다.

### 8.3 상세 화면

```swift
// File: OROT/Features/ReleaseDetail/ReleaseDetailView.swift
import SwiftUI

@MainActor
struct ReleaseDetailView: View {
    let id: Int
    let service: any ReleaseService
    @State private var release: ReleaseDTO?
    @State private var message: String?
    @State private var retryVersion = 0

    var body: some View {
        List {
            if let release {
                Section("음반") {
                    Text(release.title).font(.title2)
                    Text(release.artistName ?? "아티스트 정보 없음")
                    if let variant = release.variant { Text(variant) }
                }
                Section("일정 · 첫 연결 확인용 원문") {
                    Text(release.scheduleStatus ?? "상태 정보 없음")
                    Text("발매일: \(release.releaseDate ?? "미정")")
                    Text("예약 시작: \(release.preorderOpensAt ?? "미정")")
                    Text("예약 마감: \(release.preorderClosesAt ?? "미정")")
                }
                Section("판매처") {
                    if release.links.isEmpty { Text("등록된 판매처가 없습니다.") }
                    ForEach(release.links) { link in
                        if let url = link.safeURL {
                            Link(destination: url) {
                                VStack(alignment: .leading) {
                                    Text(link.shopName)
                                    if let price = link.priceKrw {
                                        Text("\(price.formatted())원")
                                    }
                                }
                            }
                        } else {
                            Text("\(link.shopName) · 링크를 확인할 수 없습니다.")
                        }
                    }
                }
            } else if let message {
                Text(message)
                Button("다시 시도") { retryVersion += 1 }
            } else {
                ProgressView("상세 불러오는 중")
            }
        }
        .navigationTitle("발매 상세")
        .task(id: "\(id)-\(retryVersion)") { await load() }
    }

    private func load() async {
        release = nil
        message = nil
        do {
            let result = try await service.release(id: id)
            try Task.checkCancellation()
            release = result
        } catch {
            guard !Task.isCancelled else { return }
            if error is CancellationError { return }
            if let urlError = error as? URLError, urlError.code == .cancelled { return }
            message = (error as? APIError)?.errorDescription
                ?? "네트워크를 확인하고 다시 시도해 주세요."
        }
    }
}
```

상세는 목록에서 받은 객체를 영구히 믿지 않고 ID로 다시 조회한다. 목록을 본 뒤 운영자가 시간을 고치거나 비공개로 돌렸을 수 있기 때문이다. 예제의 raw 날짜·상태 표시는 연결 확인용이며 사용자 공개 전 10장의 표시 규칙으로 교체한다.

### 8.4 앱 진입점

```swift
// File: OROT/App/OROTApp.swift
import SwiftUI

@main
@MainActor
struct OROTApp: App {
    private let service: APIClient

    init() {
        // 본인의 실제 공개 호스트로 교체한다. 비밀 키는 넣지 않는다.
        let rawURL = "https://YOUR-PUBLIC-HOST/api/mobile"
        guard let url = URL(string: rawURL),
              url.scheme == "https", url.host != nil,
              url.user == nil, url.password == nil,
              url.query == nil, url.fragment == nil else {
            preconditionFailure("공개 API 설정을 확인하세요.")
        }
        service = APIClient(baseURL: url)
    }

    var body: some Scene {
        WindowGroup { FeedView(service: service) }
    }
}
```

`YOUR-PUBLIC-HOST`는 실제 주소가 아닌 자리표시자다. 형식 검사만 통과하므로 그대로 실행하면 네트워크 오류가 나는 것이 정상이다. 실제 Funnel 호스트를 확인해 바꾼다.

개발용 코드 상수는 공개 API 주소만 담는다. 배포 준비 단계에서는 `AppConfiguration`으로 분리하고 Debug·Release 설정을 각각 검증한다. `.xcconfig`에 URL을 직접 넣을 때 `//`가 주석으로 해석될 수 있으므로 호스트만 설정하고 코드에서 HTTPS URL을 조합하는 방식이 쉽다. Info 설정에 사용자 키를 넣었다면 `Bundle.main`에서 읽어 앱 시작 시 검증한다.

## 9. 예제 실행과 확장 순서

1. 5.1의 6개 파일을 앱 target에 추가한다.
2. 템플릿의 앱 진입점이 중복되지 않았는지 확인한다.
3. 공개 API 호스트를 실제 주소로 바꾼다.
4. `⌘B`로 컴파일한다. 먼저 나타난 컴파일 오류부터 하나씩 해결한다.
5. Simulator에서 `⌘R`로 실행한다.
6. 목록 → 정렬 변경 → 당겨 새로고침 → 상세 → 판매처 링크를 확인한다.
7. 서버에 공개 일정이 없으면 빈 목록이 정상일 수 있다. 개발 화면용 데이터는 Preview·fixture로 만들고, 운영 DB에 더미 일정을 게시하지 않는다.
8. 10장의 표시 함수, 표지, 공통 색상, 설정 화면 순으로 추가한다.
9. 통신·디코딩·상태 테스트를 만들고, 마지막 성공 데이터 보존을 구현한다.
10. 푸시와 실제 배포는 별도 단계에서 진행한다.

최소 예제에는 이미지, 앱 설정 탭, 오프라인 보관, Retry-After 처리, APNs, 배포 서명이 없다. 성공적으로 컴파일되어도 완성된 출시 앱을 뜻하지 않는다.

**완료 기준:** 실제 서버의 공개 일정이 표시되고 상세 링크를 열 수 있으며, 서버 오류가 앱 종료로 이어지지 않는다.

## 10. OROT 일정과 가격을 정확하게 표시하기

### 10.1 날짜와 시각은 다른 타입이다

| API 예시 | 의미 | 처리 |
|---|---|---|
| `2026-10-01` | 달력 날짜 | 년·월·일 자체를 유지 |
| `2026-10-01T05:00:00Z` | 특정 순간 | KST로 변환하면 10월 1일 14:00 |
| `null` | 미정·해당 없음 | 필드와 상태에 맞는 안내 |

날짜만 있는 값을 UTC 자정으로 만들고 기기 시간대로 변환하면 날짜가 바뀔 수 있다. `release_date`는 날짜 전용 값으로 다루고, `preorder_*_at`는 시간대가 있는 시각으로 다룬다.

다음은 별도 `Core/Formatting/ScheduleFormatter.swift`에 확장할 때 사용하는 함수 예제다. 7~8장 실행에 필수인 파일은 아니다.

```swift
import Foundation

func parseInstant(_ raw: String) -> Date? {
    let fractional = ISO8601DateFormatter()
    fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let value = fractional.date(from: raw) { return value }
    let ordinary = ISO8601DateFormatter()
    ordinary.formatOptions = [.withInternetDateTime]
    return ordinary.date(from: raw)
}

func formatKST(_ raw: String?) -> String {
    guard let raw else { return "일정 미정" }
    guard let date = parseInstant(raw) else { return "일정 확인 필요" }
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "ko_KR")
    formatter.timeZone = TimeZone(identifier: "Asia/Seoul")
    formatter.dateFormat = "yyyy년 M월 d일 HH:mm"
    return formatter.string(from: date) + " KST"
}
```

소수 초가 있는 응답과 없는 응답을 모두 fixture로 검증한다. 위 함수는 설명을 위해 formatter를 매번 생성한다. 성능 개선이 필요하면 격리된 formatter 서비스로 관리한다.

날짜 전용 값은 다음 순서로 처리한다.

1. `YYYY-MM-DD` 형식과 숫자 범위를 검사한다.
2. Gregorian 달력에 년·월·일을 넣는다.
3. 존재하는 날짜인지 구성 후 되읽어 확인한다. 2월 30일이 자동 보정되지 않게 한다.
4. 다른 시간대로 옮기지 않고 `2026년 10월 1일`처럼 표시한다.

### 10.2 상태별 표시

| 조건 | 기본 표시 방향 |
|---|---|
| `schedule_status == TBA` | 발매일 미정 |
| `ON_SALE`이고 마감이 지남 | 판매 종료 |
| `ON_SALE`이고 아직 마감 전 또는 마감 없음 | 판매 중 |
| `SCHEDULED`이고 예약 시작이 있음 | 예약 시작 시각을 KST로 표시 |
| 예약 시작이 없고 발매일이 있음 | 발매일 표시 |
| `until_sold_out == true` | 마감 영역에 품절 시까지 |
| 상태가 알려지지 않은 새 값 | 일정 확인 필요 등 안전한 대체 표시 |

`until_sold_out`은 실제 현재 재고를 증명하는 값이 아니다. “품절 시까지”를 “재고 있음”으로 바꾸지 않는다. 피드의 `at`도 항상 발매일은 아니다. 해당 의미에 맞는 `release` 필드를 사용한다.

판본·색상이 다르면 다른 발매이므로 제목이 같다는 이유로 합치지 않는다. 가격은 정수 원화이고 0원도 유효하다. `if price > 0`으로 존재 여부를 판단하지 않는다.

자동 테스트에 현재 시간을 주입할 수 있도록 `formatSchedule(release:now:)` 형태로 만든다. 경계 시각 바로 전·정각·바로 후의 결과를 검증한다.

## 11. 디자인과 접근성

### 11.1 기존 테마 옮기기

기존 `apps/mobile/theme.ts`와 `apps/mobile/THEME.md`에서 색상·글꼴·간격 의도를 읽는다. Swift 파일에 모든 숫자를 흩뿌리기보다 역할별 이름을 붙인다.

- 색상: background, surface, primaryText, secondaryText, accent, divider.
- 글자: 화면 제목, 앨범 제목, 본문, 보조 설명.
- 간격: 작은 간격, 기본 간격, 화면 여백.
- 컴포넌트: RecordArtwork, ScheduleBadge, ErrorStateView.

Assets의 Color Set에 밝은 화면·어두운 화면 값을 지정할 수 있다. 글자는 `.headline`, `.body` 같은 시스템 텍스트 스타일로 시작하면 Dynamic Type 대응이 쉽다. 사용자 글꼴은 등록과 라이선스를 확인하고 큰 글자 대응도 함께 검증한다.

### 11.2 피드 한 행

표지 → 제목 → 아티스트·판본 → 핵심 일정 순으로 읽히게 만든다. 행 높이를 고정하면 긴 제목과 큰 글자가 잘릴 수 있다. 장식 이미지는 VoiceOver가 불필요하게 읽지 않게 하고, 동작에는 의미 있는 레이블을 제공한다.

표지는 `AsyncImage`로 시작하되 로딩·실패 대체 이미지를 둔다. 이미지 한 장이 실패했다고 전체 발매를 지우지 않는다. 원본 링크를 사용하고 이미지를 서버에 복제·재호스팅하는 기능을 임의로 추가하지 않는다.

### 11.3 직접 확인할 항목

- 가장 큰 글자 크기에서도 주요 버튼·일정이 읽히는가.
- 다크 모드에서 보조 문구가 충분히 보이는가.
- 색을 구분하지 못해도 상태 텍스트를 이해할 수 있는가.
- VoiceOver로 제목, 일정, 판매처 링크를 순서대로 탐색하는가.
- 긴 한글·영문 제목, 아티스트 없음, 표지 없음이 자연스러운가.
- 하단 홈 인디케이터와 상단 safe area를 침범하지 않는가.

Preview는 레이아웃을 빠르게 보는 도구다. Preview에서 좋아 보여도 실기기의 VoiceOver·큰 글자 검증을 대신하지 않는다.

## 12. 캐시와 오프라인

### 12.1 어떤 저장소를 쓸까

| 데이터 | 초기 제안 |
|---|---|
| 마지막 정렬 선택·UI 설정 | UserDefaults / `@AppStorage` |
| 공개 피드·상세 캐시 | Caches 디렉터리의 버전 있는 JSON |
| 설치 인증 비밀 | Keychain |
| 장기 보존·검색이 필요한 복잡한 로컬 데이터 | 필요 시 SwiftData 검토 |

Caches는 운영체제가 지울 수 있다. 따라서 캐시가 없으면 정상적으로 다시 다운로드할 수 있어야 한다. 사용자가 만든 중요한 즐겨찾기는 재생성 가능한 API 캐시와 같은 보존 정책으로 취급하지 않는다.

### 12.2 캐시 흐름

```text
화면 진입
  → 현재 host·정렬에 해당하는 캐시 읽기
  → 있으면 마지막 갱신 시각과 함께 표시
  → 네트워크로 재검증
     ├─ 성공: 화면 갱신 + 캐시 원자적 저장
     ├─ 실패: 기존 데이터 유지 + 갱신 실패 안내
     └─ 상세 404: 해당 상세 캐시 무효화 + 이용 불가 안내
```

캐시 키에는 API host·경로·쿼리·스키마 버전을 포함한다. `imminent`와 `recent`를 같은 파일 하나로 섞거나 개발 서버 데이터를 운영 서버 데이터처럼 보여주면 안 된다.

본문과 함께 `schema_version`, `fetched_at`을 저장한다. 예를 들어 24시간을 넘어선 캐시는 오래된 정보 안내를 강화하는 정책을 정할 수 있지만, 이는 제안값이며 제품 요구에 맞춰 정한다. 캐시 표시가 실제 판매 상태나 일정 유효성을 보장하지 않는다.

네트워크 응답이 성공하고 디코딩·검증까지 끝난 경우에만 저장한다. 파일 쓰기는 원자적으로 하고 손상된 캐시는 안전하게 무시한다. 큰 파일 I/O는 화면 actor에서 동기 실행하지 않는다.

처음에는 ETag 없이 시작해도 된다. ETag를 도입할 경우 304에는 본문이 없다는 점과 공개 프록시의 전달 동작을 함께 검증한다. 모든 응답을 무조건 JSON으로 읽으면 304에서 실패한다.

**완료 기준:** 온라인 조회 후 앱을 종료하고 기내 모드에서 다시 열어 이전 데이터와 갱신 시각을 볼 수 있다. 온라인 복귀 후 수정된 일정으로 갱신된다.

## 13. 네이티브 푸시의 전체 흐름

### 13.1 푸시는 앱 UI만으로 끝나지 않는다

다음은 **향후 구현 설계**다. 현재 `/api/mobile/v1/devices`가 동작한다고 가정해서 호출하면 안 된다. 기존 DB에 IOS enum이 있다고 앱 구독·인증·전송 경로가 완성된 것은 아니다.

iOS 중심의 초기 구현에는 직접 APNs를 사용하는 구성을 제안한다. Expo Push Service의 ticket·receipt 처리 코드를 그대로 APNs에 적용하지 않는다. APNs 응답 성공은 Apple의 요청 수락이며 사용자 화면 표시를 증명하는 영수증이 아니다.

### 13.2 구성요소

| 위치 | 책임 |
|---|---|
| SettingsView | 설명, 알림 켜기·끄기, 실제 상태 안내 |
| NotificationSettingsModel | OS 권한·사용자 의사·서버 등록 상태 조정 |
| AppDelegate | APNs 토큰 수신·등록 실패 콜백 |
| NotificationService | 권한 조회·요청, 기기 등록 서비스 호출 |
| KeychainStore | 설치 소유 증명용 비밀 보관 |
| AppRouter | 유효한 release ID로 상세 이동 |
| FastAPI 기기 API | 등록·수정·해지, 소유권 검증, 속도 제한 |
| DB | provider·환경·기기 상태·전송 이력 |
| collector APNs sender | 전송, 오류 분류, 재시도·비활성화 |

### 13.3 등록 순서

1. 사용자가 설정에서 알림 켜기를 누른다.
2. 어떤 알림인지 설명한 뒤 `UNUserNotificationCenter`로 권한을 요청한다.
3. 허용 여부와 앱의 구독 의사를 확인한다.
4. 시스템의 remote notification 등록을 요청한다.
5. AppDelegate의 토큰 콜백에서 최신 APNs 토큰을 받는다.
6. 앱 설치의 인증 정보와 함께 서버 기기 등록 또는 갱신을 요청한다.
7. 서버 저장 성공 후에만 “알림 등록 완료”라고 표시한다.

알림 표시 권한과 APNs 토큰 획득은 서로 다른 상태다. 앱 실행 시에도 관련 설정을 다시 확인하고, 구독을 원하는 설치의 토큰 등록을 최신 상태로 맞춘다. 토큰이 고정 길이이거나 영구히 같다고 가정하지 않는다. [권한 요청](https://developer.apple.com/documentation/UserNotifications/asking-permission-to-use-notifications), [APNs 등록](https://developer.apple.com/documentation/usernotifications/registering-your-app-with-apns)

SwiftUI 앱에서는 `@UIApplicationDelegateAdaptor`로 AppDelegate를 연결할 수 있다. `UNUserNotificationCenterDelegate`를 앱 초기화 때 설정하고, foreground 표시와 알림 탭을 처리한다. delegate 콜백이 화면 actor에서 실행된다고 가정하지 말고 UI 경로 변경은 MainActor로 전달한다.

### 13.4 알림 스위치의 실제 상태

| OS 권한 | 사용자 구독 의사 | 서버 등록 | 화면 |
|---|---|---|---|
| 미결정 | 꺼짐 | 없음 | 알림 켜기 |
| 거부 | 켜고 싶음 | 비활성 또는 없음 | iOS 설정 안내 |
| 허용 | 켜짐 | 등록 중 | 등록 중 표시 |
| 허용 | 켜짐 | 실패 | 등록 실패·재시도 |
| 허용 | 켜짐 | 활성 | 알림 켜짐 |
| 허용 | 꺼짐 | 해지 실패 | 해지 미완료 안내·재시도 |

OS 알림을 허용해도 서버 등록이 실패하면 정상 구독이 아니다. 앱 스위치를 꺼도 OS 권한 자체를 앱이 철회할 수는 없다. 앱 구독 해제는 서버 전송 대상을 비활성화하는 동작이다.

오프라인에서 끄기를 누르면 사용자 의사를 로컬에 먼저 보존하되 서버 반영이 아직 안 됐다는 상태를 표시한다. 다음 실행·연결 시 해지를 재시도한다. 재설치와 Keychain 잔존 여부를 포함한 설치 수명주기도 설계해야 한다.

### 13.5 서버에서 새로 해야 할 일

- APNs 토큰, 앱 식별자, sandbox/production을 분리할 저장 구조와 마이그레이션.
- 등록·갱신·해지의 구체적 요청·응답 계약.
- 익명 설치도 본인 기기만 수정·삭제할 수 있는 인증.
- 등록 bootstrap, 토큰 교체 충돌, 만료·재설치, 탈취 방어 정책.
- 기존 WEB 대상과 별개인 IOS 대상 선택 및 APNs sender.
- 오류 분류, 재시도, 사용 불가능한 토큰의 비활성화.
- 외부 요청 중 DB 트랜잭션을 오래 붙잡지 않는 발송 구조.
- 기존 배송 기록·일정 변경 무효화 규칙 유지.
- 위조된 등록 요청·본문 크기·속도 제한에 대한 테스트.

APNs 토큰 자체를 기기 관리 API의 인증 비밀로 사용하지 않는다. 앱에 공통 관리자 키를 넣는 방식도 쓰지 않는다. 이 인증은 초기 화면 학습과 별개로 설계해야 하는 부분이다.

### 13.6 APNs 환경과 발송

개발 서명 앱과 배포 앱은 APNs 환경이 다를 수 있다. 특히 TestFlight는 production 환경을 사용한다. Debug라는 이름만 보고 환경을 결정하지 말고 서명 결과의 `aps-environment`와 서버 저장값이 일치하는지 확인한다.

APNs 인증용 `.p8` 개인키는 서버에서만 관리한다. 앱 번들·Git·로그에 넣지 않는다. sender에는 올바른 topic(bundle ID), 환경, payload, 만료 시각을 적용한다. [APNs 요청 구성](https://developer.apple.com/documentation/usernotifications/sending-notification-requests-to-apns)

실패 응답은 모두 같은 방식으로 재시도하지 않는다. 예를 들어 토큰이 더 이상 유효하지 않은 경우와 일시적 서버 오류는 조치가 다르다. 구체적인 상태·reason 매핑은 구현 시점 Apple 문서와 fake 응답 테스트로 확정한다.

예약 임박과 예약 시작 알림을 발매 ID 하나로 collapse하면 앞 알림이 뒤 알림으로 대체될 수 있다. 서로 다른 이벤트를 유지해야 하는 OROT 요구를 반영한다. 외부 전송 성공 직후 DB 커밋 전에 프로세스가 종료되는 경우가 있으므로 “절대 중복 없음”을 보장한다고 쓰지 않는다.

### 13.7 알림 탭과 상세 이동

payload 제안 예시는 다음과 같다. 현재 서버의 구현 계약은 아니다.

```json
{
  "aps": {
    "alert": { "title": "예약 시작", "body": "관심 있는 발매 일정을 확인해 보세요." },
    "sound": "default"
  },
  "schema_version": 1,
  "release_id": 123,
  "event_id": 456,
  "event_type": "PREORDER_OPEN"
}
```

앱은 양수 ID와 지원 payload 버전을 검사하고 임의 URL을 그대로 열지 않는다. `release_id`로 공개 API를 조회한 뒤 상세를 보여준다.

```text
알림 탭
  → payload 검증
  → AppRouter에 pending release ID 저장
  → 루트 화면 준비·피드 탭 선택
  → NavigationStack 경로에 상세 ID 반영
  → 상세 API 재조회
     ├─ 200: 최신 상세
     ├─ 404: 더 이상 볼 수 없는 일정 안내
     └─ 통신 오류: 재시도
```

앱 종료 상태에서는 화면이 아직 만들어지지 않았을 수 있다. 경로를 즉시 밀어 넣고 잃어버리지 않도록 대기 중 목적지를 보관한다. 같은 콜백이 중복 처리될 때 상세가 여러 겹 쌓이지 않게 event ID·현재 경로를 활용한다.

7~8장의 `NavigationStack`은 피드 안에 있다. 이 단계에서는 이를 앱 수준 `AppRouter`와 명시적인 `[Route]` 경로로 확장한다. 설정·피드 탭을 도입했다면 알림 탭 시 어느 탭의 상세를 열지 한 곳에서 결정한다.

### 13.8 실제 푸시 테스트

로컬·자동 테스트에서는 fake sender와 합성 payload를 사용한다. Simulator에 payload를 주입해 화면 이동을 확인하는 것은 APNs 서버 전송 검증과 다르다.

실제 발송은 지정한 테스트 기기·이벤트로만 진행한다. 운영 DB에 더미 공개 일정을 넣으면 기존 Web Push 사용자도 알림을 받을 수 있으므로 격리 환경 또는 서버에서 강제하는 테스트 대상 제한을 먼저 마련한다.

기록을 네 단계로 나눈다: 서버 대상 선정 → APNs 수락 → 기기 표시 → 탭 후 상세. 집중 모드·알림 요약·네트워크 때문에 기기 표시가 지연될 수 있다. 앱과 서버가 아무리 정확해도 운영체제 표시 시점을 절대 보장할 수는 없다.

**완료 기준:** 지정한 iPhone에서 foreground·background·종료 상태의 수신·탭 이동이 되고, 알림 해지 후 서버 대상에서 제외된다. 기존 WEB 전송도 유지된다.

## 14. 테스트와 디버깅

### 14.1 테스트의 순서

1. DTO 디코딩: 공개 응답 형식이 맞는지.
2. 표시 함수: 날짜·가격·상태가 맞는지.
3. 화면 모델: 성공·빈 결과·실패·경쟁 요청에서 상태가 맞는지.
4. APIClient: URL·쿼리·HTTP 오류·취소를 제대로 처리하는지.
5. UI: 목록 → 상세 → 뒤로, 오류 → 재시도.
6. 실기기: 링크, 접근성, 푸시, 설치 앱의 독립 실행.

단위 테스트는 Swift Testing, UI 테스트는 XCTest로 시작할 수 있다. [Apple 테스트 추가 안내](https://developer.apple.com/documentation/xcode/adding-tests-to-your-xcode-project)

### 14.2 테스트용 가짜 서비스

`OROTTests/Doubles/FakeReleaseService.swift`의 예시다. 실제 서버를 호출하지 않는다.

```swift
import Foundation
@testable import OROT

@MainActor
struct FakeReleaseService: ReleaseService {
    let page: FeedPageDTO

    func feed(sort: FeedSort) async throws -> FeedPageDTO { page }

    func release(id: Int) async throws -> ReleaseDTO {
        guard let value = page.items.first(where: { $0.release.id == id }) else {
            throw APIError.http(404)
        }
        return value.release
    }
}
```

실패 테스트에는 항상 `APIError.http(502)`를 던지는 서비스를, 경쟁 요청 테스트에는 완료 순서를 통제할 수 있는 서비스를 별도로 만든다. 단순히 실제 APIClient를 불러 “오류가 안 났다”로 끝내지 않는다.

### 14.3 디코딩 테스트 예제

```swift
import Foundation
import Testing
@testable import OROT

struct ReleaseDTOTests {
    @Test func zeroWonAndMissingArtistArePreserved() throws {
        let data = Data(#"""
        {
          "id": 1,
          "title": "테스트 발매",
          "is_published": true,
          "schedule_status": "TBA",
          "until_sold_out": false,
          "links": [
            {"id": 10, "shop_name": "테스트 판매처",
             "url": "https://example.com/release/1", "price_krw": 0}
          ]
        }
        """#.utf8)
        let release = try JSONDecoder().decode(ReleaseDTO.self, from: data)
        #expect(release.artistName == nil)
        #expect(release.links.first?.priceKrw == 0)
        #expect(release.links.first?.safeURL != nil)
    }
}
```

이 JSON은 합성 fixture다. 실제 판매처를 긁어 오거나 운영 데이터를 바꾸지 않는다. `@testable import OROT`의 모듈 이름은 앱 target의 실제 Product Module Name과 같아야 한다.

### 14.4 꼭 포함할 회귀 사례

| 분류 | 사례 |
|---|---|
| 응답 | 빈 items, 누락된 필수값, 추가 필드, 중복 ID, 비공개 응답 거부 |
| 일정 | UTC→KST 날짜 경계, 소수 초, 날짜만 있는 값, TBA·ON_SALE·품절 시까지 |
| 금액·링크 | 0원, null, 큰 원화 정수, 허용하지 않는 URL scheme |
| 요청 | HTML 502, JSON 404, 429, timeout, 취소 |
| 상태 | 빠른 정렬 변경, 늦은 이전 응답, 초기 오류 후 성공 |
| 캐시 | 손상 파일, host·정렬별 분리, 만료 안내, 상세 404 무효화 |
| 알림 | 알 수 없는 payload 버전, 없는 ID, 중복 탭, cold start |

APIClient의 HTTP 테스트에는 주입한 URLSession과 URLProtocol stub을 사용할 수 있다. 테스트 fixture를 UI 실행 인자로 주입하면 UI 테스트도 서버 없이 돌릴 수 있다. 실서버를 읽는 수동 점검은 별도 기록한다.

### 14.5 Xcode와 터미널에서 실행

Xcode에서 `⌘U`는 테스트, `⌘B`는 빌드, `⌘R`은 실행이다. Test navigator에서 실패한 테스트만 열어 기대값과 실제값을 비교한다.

프로젝트를 만든 뒤 저장소 루트에서 사용할 명령 예시:

```sh
xcodebuild -list -project apps/ios/OROT.xcodeproj
xcodebuild -showdestinations -project apps/ios/OROT.xcodeproj -scheme OROT
```

위 출력에서 실제 Simulator ID를 골라 아래 자리표시자를 바꾼다. 기기 이름을 문서에서 복사해 존재한다고 가정하지 않는다.

```sh
xcodebuild test \
  -project apps/ios/OROT.xcodeproj \
  -scheme OROT \
  -destination 'platform=iOS Simulator,id=SIMULATOR-UUID' \
  -derivedDataPath /private/tmp/orot-ios-derived-data
```

현재 이 문서만으로는 해당 프로젝트나 scheme이 생기지 않는다. 명령은 프로젝트 생성 후 실행한다. 테스트 target이 scheme의 Test 동작에 포함되어 있어야 한다.

### 14.6 기존 저장소 검사와 구분

이 가이드 문서만 추가할 때는 Python·웹 서비스를 시작하거나 다시 빌드하지 않는다. 실제 구현 작업에서는 저장소의 `AGENTS.md`가 정한 `make lint`, `make test`를 수행하고, 웹 프록시를 바꾸면 웹 lint·회귀 테스트·build도 추가한다. iOS 기능은 별도로 Xcode 빌드·테스트·실기기 검증을 한다. Python 테스트 통과가 iOS 컴파일 성공을 의미하지 않는다.

## 15. 실기기와 TestFlight

### 15.1 iPhone 개발 실행

1. Xcode Settings의 Apple Accounts에서 계정을 연결한다.
2. iPhone을 Mac에 연결하고 기기의 신뢰 요청을 확인한다.
3. iPhone에서 필요한 Developer Mode를 활성화한다.
4. 앱 target의 Signing & Capabilities에서 본인 Team과 고유 Bundle Identifier를 선택한다.
5. 자동 서명 설정을 확인하고 iPhone을 실행 대상으로 선택한다.
6. `⌘R`로 설치·실행한다.
7. Wi-Fi와 셀룰러에서 공개 API에 연결되는지 각각 확인한다.

메뉴 위치는 Xcode 버전에 따라 달라질 수 있다. [Simulator·실기기 실행 안내](https://developer.apple.com/documentation/Xcode/running-your-app-on-simulated-or-physical-devices)를 기준으로 확인한다.

개인 Apple 계정으로 할 수 있는 기본 기기 테스트와 Apple Developer Program의 배포·capability 지원은 범위가 다르다. APNs·TestFlight 단계에서는 적절한 유료 프로그램 가입과 Team 권한이 필요하다. 현재 제공 범위는 [멤버십 비교](https://developer.apple.com/support/compare-memberships/)에서 확인한다.

### 15.2 푸시 capability

실제 APNs 단계에서 앱 ID의 Push Notifications와 앱 target capability·서명 profile을 맞춘다. 일반적인 표시 알림을 받기 위해 무조건 Background Modes의 Remote notifications를 켜는 것은 아니다. 무음 백그라운드 처리 요구가 있을 때 별도로 검토한다.

토큰 오류가 나면 네트워크부터 바꾸기보다 Team, Bundle ID, entitlement, APNs 환경을 차례로 확인한다.

### 15.3 TestFlight까지의 순서

1. iPhone에서 읽기·오류·알림 흐름을 검증한다.
2. 배포용 Bundle ID, 앱 버전, build 번호, 공개 API 주소를 확정한다.
3. 개인정보 처리·지원 URL, 앱 아이콘, 테스트 설명을 준비한다.
4. App Store Connect에 앱 레코드를 만든다.
5. Xcode에서 배포용 실행 대상을 선택하고 **Product → Archive**를 실행한다.
6. Organizer에서 archive의 앱 식별자·버전·서명을 확인한다.
7. **Distribute App** 흐름으로 App Store Connect에 업로드한다.
8. App Store Connect 처리가 끝나면 수출 규정 등 실제 앱에 해당하는 정보를 작성한다.
9. TestFlight 그룹에 빌드를 연결하고 본인 테스트 계정으로 설치한다.
10. Xcode 디버거 없이 실행·셀룰러·알림·종료 후 탭 이동을 다시 확인한다.

TestFlight 빌드는 만료되며 외부 테스트에는 별도 검토가 필요할 수 있다. 업로드 성공, 처리 완료, 설치 성공, App Store 공개는 각각 다른 단계다. [TestFlight 흐름](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview/), [빌드 업로드](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds)

Swift 앱에는 Expo Metro나 EAS가 필요하지 않다. 설치 앱 자체는 Xcode 없이 실행되지만 데이터를 제공하는 Mac mini 서버는 계속 접근 가능해야 한다. 서버 환경변수를 바꿔도 이미 설치된 앱에 포함된 API 주소가 저절로 바뀌지는 않는다.

## 16. 혼자 진행하는 단계별 작업표

아래는 기존 작업 ID에 연결한 **전환 시 제안 순서**다. 기존 백로그의 확정 완료 조건을 이 문서만으로 변경하거나 완료 처리하지 않는다. 하루 단위의 고정 일정 대신 완료 기준으로 진행한다.

| 단계 | 관련 기존 ID | 직접 할 작업 | 다음 단계로 가는 기준 |
|---|---|---|---|
| 준비 | T-033 | Xcode, 최소 iOS, 별도 프로젝트, 공개 주소 | 빈 앱 실행 |
| 읽기 연결 | T-033 | DTO, APIClient, 최소 피드·상세 | 실제 공개 API 읽기 |
| 기본 화면 | T-034~T-036 | 테마, 피드 정렬·상태, 상세·원문 링크 | 오류·빈 결과·접근성 포함 화면 검증 |
| 오프라인 | T-039 | 버전·host·정렬별 캐시 | 재실행·기내 모드·복구 확인 |
| 기기 API | T-040 | 인증·등록·갱신·해지·마이그레이션 | 소유권·토큰 교체·WEB 회귀 검증 |
| 전송 | T-041 | APNs sender·오류·이력·대상 제한 | fake 검증 후 지정 기기 수신 |
| 앱 알림 | T-042 | 권한·foreground·탭·cold start | 모든 앱 상태에서 상세 이동 |
| 설정 | T-043 | OS·서버·구독 의사 동기화 | 켜기·끄기·실패 복구 |
| 배포 검증 | 기존 최종 게이트 | Archive·TestFlight | 독립 설치 앱의 전체 흐름 성공 |

표의 화면 묶음도 실제 작업은 T-034, T-035, T-036을 한 번에 완료 처리하지 않고 하나씩 끝낸다. T-037 계정, T-038 워치리스트는 해당 서버 기능이 준비되기 전까지 별도 후속으로 둔다.

### 첫 작업 세션 예시

- Xcode 프로젝트를 만들고 기본 화면을 실행한다.
- 모델 파일 하나를 작성하고 테스트 JSON을 디코딩한다.
- 다음 세션에 APIClient와 피드를 연결한다.
- 그다음 상세·외부 링크와 오류 처리를 추가한다.
- 안정되면 화면을 꾸미고 날짜 표시를 정확하게 만든다.

매번 “무엇을 만들었는지”와 “무엇을 실제로 확인했는지”를 따로 적는다. 예를 들어 “알림 payload 파서 테스트 통과”와 “APNs 실기기 수신 성공”은 다른 결과다.

## 17. 문제 해결과 작업 습관

### 17.1 자주 막히는 문제

| 증상 | 먼저 확인할 것 |
|---|---|
| 타입을 찾을 수 없음 | 파일 target membership, 이름, 접근 수준 |
| `@main` 관련 오류 | 템플릿과 새 OROTApp 진입점 중복 |
| iOS 버전 사용 가능성 오류 | Deployment Target과 해당 API 지원 버전 |
| actor isolation 오류 | UI 상태와 서비스의 MainActor 경계, await 누락 |
| 실제 API 대신 HTML이 옴 | 공개 URL 경로, 프록시 오류, 상태 코드·Content-Type |
| Simulator는 되는데 iPhone은 안 됨 | localhost·Docker 주소 사용 여부, HTTPS 공개 연결 |
| 날짜가 하루 다름 | 날짜만 있는 값을 UTC 순간으로 바꿨는지 |
| 정렬이 예전 것으로 돌아감 | 늦은 이전 요청이 새 상태를 덮었는지 |
| 권한은 허용인데 알림이 없음 | 서버 등록·대상·APNs 환경·수락·기기 설정을 각각 확인 |
| TestFlight에서만 푸시 실패 | production 토큰·topic·서명 환경 확인 |
| Preview가 서버 오류로 실패 | live API 대신 fake 서비스 주입 |
| 파일을 추가했는데 Git에 안 보임 | ignore 패턴, 실제 파일 경로 |

문제 해결을 위해 DB를 삭제하거나 Docker 볼륨을 지울 필요는 없다. 문서 예제 검증에서도 기존 등록 일정과 구독을 건드리지 않는다.

### 17.2 한 번의 개발 주기

1. `git status --short`로 기존 변경을 확인한다.
2. 오늘의 목표 하나를 적는다. 예: “정렬 변경 후 이전 응답이 덮지 않게 한다.”
3. 관련 파일만 읽고 변경한다.
4. `⌘B`, 관련 테스트, 필요 시 Simulator 순으로 확인한다.
5. 사용자 동선을 손으로 한 번 따라간다.
6. diff에 프로젝트 설정·자동 생성 파일이 예상치 않게 섞였는지 확인한다.
7. 실제 기기에서 확인하지 못한 항목을 남긴다.

오류가 많으면 가장 먼저 발생한 오류부터 해결한다. 첫 오류 때문에 뒤에 연쇄 오류가 생기는 경우가 많다. 코드 조각을 계속 덧붙이기 전에 어떤 상태와 파일이 책임을 갖는지 5~6장으로 돌아가 확인한다.

### 17.3 다른 도구나 AI에 도움을 요청할 때

“앱 전체를 만들어 줘”보다 범위를 좁히면 학습과 검증이 쉽다.

> `FeedModel.swift`의 정렬 변경 요청 경쟁을 해결하고 싶습니다. 현재 모델과 테스트를 기준으로 원인을 설명해 주세요. 수정 범위는 이 파일과 해당 테스트로 제한하고, 오래된 요청이 나중에 끝나는 경우를 검증해 주세요.

> `release_date`는 날짜만 있고 `preorder_opens_at`은 UTC 시각입니다. KST 표시에 필요한 차이를 설명하고, 날짜가 바뀌는 경계 사례의 테스트를 작성해 주세요.

> 푸시 등록 API는 아직 없습니다. 앱의 설정 상태와 필요한 서버 계약을 구분해서 제안해 주세요. 관리자 키를 앱에 넣지 않는 설치 인증 설계가 필요합니다.

APNs 키, 설치 비밀, 실제 기기 토큰, `.env`를 질문에 붙이지 않는다. 오류는 상태 코드·오류 종류·재현 동작과 함께 공유하면 된다.

## 18. 참고 파일과 공식 자료

### 저장소에서 읽을 파일

| 파일 | 읽는 이유 |
|---|---|
| [루트 지침](../AGENTS.md), [CLAUDE.md](../CLAUDE.md) | 제품 범위·검증·운영 규칙 |
| [모바일 블루프린트](MOBILE_BLUEPRINT.ko.md) | MVP, 공개 경계, 기존 단계·제안 인증 |
| [한국어 블루프린트](BLUEPRINT.ko.md), [영문 블루프린트](BLUEPRINT.en.md) | 공통 계약·도메인 규칙 |
| [Expo 방향 ADR](adr/0009-expo-mobile-app.md) | 전환 전 확정 방향과 미결정 사항 |
| [Web Push 우선 ADR](adr/0006-web-push-first.md) | 기존 알림과 iOS의 관계 |
| [공개 경계 ADR](adr/0007-same-origin-push-proxy.md) | 프록시·공개 주소 구분 |
| [OpenAPI](api/openapi.json) | 응답·오류·필드 계약 |
| [API 응답 모델](../apps/api/src/orot_api/schemas/release.py) | 현재 날짜·가격·공개 필드 |
| [모바일 APIClient](../apps/mobile/src/lib/api/client.ts) | 기존 요청·검증·오류 처리 |
| [모바일 일정 표시](../apps/mobile/src/features/releases/display.ts) | 상태와 KST 표시 기준 |
| [모바일 테마](../apps/mobile/theme.ts), [테마 안내](../apps/mobile/THEME.md) | 디자인 값과 글꼴·이미지 의도 |

소스와 OpenAPI가 다르면 현재 소스의 계약을 먼저 확인한다. 과거 검증 기록은 해당 날짜의 증거이지 현재 배포 상태의 보증이 아니다.

### 공식 학습 자료

- [Swift 언어 가이드](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/) — Optional·구조체·프로토콜·동시성.
- [Apple Develop in Swift](https://developer.apple.com/tutorials/develop-in-swift) — Xcode와 앱 개발 입문.
- [SwiftUI](https://developer.apple.com/documentation/swiftui) — 화면 구성 API.
- [모델 데이터와 Observation](https://developer.apple.com/documentation/SwiftUI/Managing-model-data-in-your-app) — 상태 소유·관찰.
- [URLSession](https://developer.apple.com/documentation/foundation/urlsession) — 비동기 HTTP 통신.
- [User Notifications](https://developer.apple.com/documentation/usernotifications) — 권한·수신·탭 처리.
- [Swift Testing](https://developer.apple.com/documentation/Testing) — 단위 테스트.
- [개인정보 manifest](https://developer.apple.com/documentation/bundleresources/privacy_manifest_files) — 실제 사용하는 API에 맞는 선언.
- [App Store 배포 준비](https://developer.apple.com/documentation/xcode/preparing-your-app-for-distribution) — archive·서명·배포 확인.

공식 문서의 UI 명칭과 배포 요구는 버전에 따라 변할 수 있다. 이 가이드에서는 안정적인 역할과 흐름을 중심으로 설명했으며, 서명·APNs·스토어 설정은 실제 실행 시점에 다시 확인한다.
