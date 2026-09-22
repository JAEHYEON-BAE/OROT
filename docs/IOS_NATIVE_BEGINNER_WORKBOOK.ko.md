# OROT iOS 실습 가이드북 — Xcode 첫 실행부터 피드·상세 앱까지

> 작성일: 2026-09-22  
> 대상: Xcode와 SwiftUI를 처음 사용하는 개발자  
> 시작점: `apps/ios/OROT.xcodeproj`와 기본 SwiftUI 화면이 있는 현재 작업 트리  
> 도착점: 자동 테스트를 갖추고 공개 API에서 피드·상세를 읽는 iOS 앱 뼈대  
> 도구 기준: 기존 가이드의 Xcode 27, Swift 6 언어 모드, 최소 iOS 17

이 책은 [iOS 네이티브 개발 가이드](IOS_NATIVE_DEVELOPMENT_GUIDE.ko.md)의 첫 구현을 **작성 → 빌드 → 테스트 → 실행** 순서로 풀어 쓴 실습서다. 각 장의 완료 상자를 체크한 다음 다음 장으로 이동한다. 책 전체 코드를 한꺼번에 붙여 넣지 않는다.

문서 작성 과정에서는 앱 소스·Xcode 설정을 변경하거나 앱을 실행하지 않았다. 코드와 현재 API 계약, 파일 경로, 단계 간 의존성을 정적으로 검토했다. **이 책의 새 예제를 Xcode에서 컴파일하거나 테스트한 결과는 아직 없다.** 아래 체크포인트는 독자가 직접 확인할 항목이다. 기존 가이드의 과거 타입 검사 기록을 이 책의 실행 결과로 해석하지 않는다.

이 실습은 학습용 Swift 앱의 읽기 기능을 만든다. [ADR-0009](adr/0009-expo-mobile-app.md), [한국어 블루프린트](BLUEPRINT.ko.md), [영문 블루프린트](BLUEPRINT.en.md)의 공식 Expo 방향이나 백로그 완료 상태를 변경하지 않는다. 푸시·캐시·계정·배포는 뼈대 다음 단계다.

## 이 책을 사용하는 방법

- **새 파일**이라고 쓰면 해당 경로에 파일을 만들고 코드 블록 전체를 넣는다.
- **전체 교체**라고 쓰면 기존 내용을 모두 선택해서 해당 블록으로 바꾼다. 뒤에 덧붙이지 않는다.
- 경로는 저장소 루트 기준이다. `OROT/`는 저장소 이름이면서 앱 소스 폴더 이름이기도 하므로 전체 경로를 확인한다.
- Swift 파일 첫 줄의 `// File:`은 위치를 알려 주는 주석이다. 함께 복사해도 된다.
- 앱 파일은 `OROT` target, 테스트 파일은 `OROTTests` 또는 `OROTUITests` target에만 넣는다.
- 코드에 등장하는 Swift 타입은 앞 단계에서 만든다. 오류가 나면 뒤 장의 코드를 미리 추가하지 말고 현재 장의 파일·target부터 확인한다.
- 11장까지는 실제 OROT API에 접속하지 않는다. 합성 데이터로 성공·오류 화면을 재현한다.

| 단계 | 만드는 것 | 다음 단계로 가는 증거 |
|---|---|---|
| [1](#step-1) | 개발 환경 확인 | iPhone Simulator 선택 가능 |
| [2](#step-2) | 기본 화면 | 화면의 문구가 보임 |
| [3](#step-3) | 폴더와 진입점 | 이동 후에도 같은 화면 실행 |
| [4](#step-4) | 단위 테스트 target | 테스트를 찾고 실행할 수 있음 |
| [5](#step-5) | DTO·합성 JSON | 디코딩·금액·링크 테스트 통과 |
| [6](#step-6) | APIClient | 실제 인터넷 없이 HTTP 처리 테스트 통과 |
| [7](#step-7) | 가짜 서비스 | 피드·상세용 데이터를 공급할 준비 완료 |
| [8](#step-8) | FeedModel | 성공·빈 결과·실패·요청 경쟁 테스트 통과 |
| [9](#step-9) | 피드 | 정렬·새로고침·재시도 화면 확인 |
| [10](#step-10) | 상세·외부 링크 | 목록 → 상세 → 뒤로 이동 |
| [11](#step-11) | UI 테스트 | 서버 없이 사용자 동선 자동 검증 |
| [12](#step-12) | 실제 API 연결 | 공개 일정의 피드·상세 조회 |
| [13](#step-13) | 최종 정리 | Debug 테스트·Release 빌드·변경 검토 |

<a id="step-1"></a>
## 1. Xcode와 프로젝트 위치 확인하기

### 1.1 개발 Mac과 서버 Mac 구분하기

MacBook Air로 개발한다면 **MacBook Air의 로컬 checkout**에 있는 프로젝트를 Xcode로 연다. SSH로 접속한 Mac mini의 파일과 MacBook Air의 파일은 서로 다르다. Git으로 코드를 동기화해도 Simulator와 Apple 계정 설정은 각 Mac에서 준비해야 한다.

```text
개발 Mac: 로컬 OROT 저장소 → Xcode → Simulator / iPhone
                                     ↓ 공개 HTTPS API
서버 Mac: Funnel → Next.js → FastAPI → PostgreSQL
```

Finder에서 아래 파일을 찾아 더블클릭한다.

```text
OROT/apps/ios/OROT.xcodeproj
```

현재 프로젝트가 있다면 새 프로젝트를 다시 만들지 않는다. 다른 Mac에 프로젝트가 아직 없다면 먼저 해당 변경을 안전하게 동기화한다. 새로 생성해야 하는 경우에만 기존 가이드 4.2를 따라 iOS App / SwiftUI / Swift / Storage None으로 만들고 최종 경로를 위와 맞춘다.

### 1.2 Xcode 화면에서 알아둘 위치

| 위치·용어 | 하는 일 |
|---|---|
| 왼쪽 Project navigator, `⌘1` | 파일을 고르고 폴더 구조 보기 |
| 왼쪽 맨 위 파란 프로젝트 아이콘 | PROJECT와 TARGETS 설정 열기 |
| TARGETS → OROT | 실제 앱의 설정 |
| 위쪽 Scheme | 실행·테스트할 대상 묶음. 여기서는 OROT |
| Scheme 옆 실행 대상 | 사용할 iPhone Simulator 선택 |
| Issue navigator, `⌘5` | 빌드 오류와 경고 보기 |
| Test navigator, `⌘6` | 테스트 목록과 결과 보기 |
| 오른쪽 File Inspector | 파일의 실제 위치와 target 소속 확인 |

단축키는 다음 다섯 개부터 사용한다.

| 키 | 의미 |
|---|---|
| `⌘S` | 저장 |
| `⌘B` | 빌드: 코드를 검사하고 앱 만들기 |
| `⌘R` | 빌드한 앱을 선택한 기기에서 실행 |
| `⌘U` | scheme에 포함된 테스트 실행 |
| `⌘.` | 실행 중인 앱·테스트 중지 |

`⌘B` 성공은 화면을 확인했다는 뜻이 아니다. `⌘R`로 화면을 보고, `⌘U`로 작성한 동작 검증을 실행한다.

### 1.3 설치 환경 확인

Xcode → About Xcode에서 버전을 확인한다. 이 책은 기존 가이드의 Xcode 27 UI를 기준으로 하며 설치 버전에 따라 메뉴 문구가 조금 다를 수 있다.

터미널 확인을 원하면 개발 Mac의 **로컬 터미널**에서 다음을 한 줄씩 실행한다. 이 명령들은 독자가 실행할 점검 명령이다.

```sh
sw_vers
xcodebuild -version
xcrun swift --version
xcode-select -p
xcodebuild -showsdks
```

확인할 내용:

- `xcode-select -p`는 사용하려는 전체 Xcode의 `Contents/Developer`를 가리켜야 한다.
- `.../CommandLineTools`만 나온다면 Xcode → Settings → Locations의 Command Line Tools에서 설치한 Xcode를 선택한다.
- iOS SDK와 iOS Simulator SDK가 보여야 한다.
- SDK 목록이 보여도 Simulator 런타임은 별도로 필요하다.

Xcode → Settings → Components에서 iOS Simulator 런타임을 확인한다. 없다면 다운로드한다. Xcode 27에서는 Open Developer Tool → Device Hub에서 가상 iPhone을 만들거나 확인한다. 실행 대상에는 실제 설치된 iPhone Simulator를 선택한다. `Any iOS Device` 같은 일반 빌드 대상은 화면을 실행할 가상 기기가 아니다. [Apple 구성요소 설치](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components), [Device Hub](https://developer.apple.com/documentation/xcode/managing-your-simulated-and-physical-devices-in-device-hub)

### 1.4 앱 설정 맞추기

왼쪽 프로젝트 아이콘 → **TARGETS → OROT → Build Settings**를 연다. 필터를 **All**로 바꾸고 아래 이름을 검색한다. 행을 펼쳐 Debug·Release 양쪽을 확인한다.

| 설정 | 실습 값 |
|---|---|
| Swift Language Version | Swift 6 (`6.0`) |
| Default Actor Isolation | MainActor |
| Approachable Concurrency | Yes |
| iOS Deployment Target | `17.0` |
| Base SDK | iOS, 설치된 SDK |

문서 작성 시 현재 앱은 앞의 Swift 설정 세 개가 이미 맞았다. Deployment Target은 target에서 `$(RECOMMENDED_IPHONEOS_DEPLOYMENT_TARGET)`, project에서 `27.0`으로 기록되어 있었다. **실습에서는 target의 Debug·Release를 명시적으로 17.0으로 맞춘다.** Project 값만 변경하고 target도 바뀌었다고 가정하지 않는다.

최소 iOS 17은 이 실습의 Observation 사용 기준이다. 개발 Mac의 macOS 버전·빌드 SDK 버전과 같을 필요는 없다. [SwiftUI Observation 지원 범위](https://developer.apple.com/documentation/SwiftUI/Managing-model-data-in-your-app)

General의 Display Name은 `OROT`, Signing & Capabilities의 Bundle Identifier는 본인의 고유 값을 사용한다. 현재 프로젝트에는 `com.jaehyeonbae.OROT`와 자동 서명이 설정되어 있다. Simulator 학습과 실제 iPhone 서명 검증은 별개다.

**완료 확인**

- [ ] 로컬 프로젝트 경로를 확인했다.
- [ ] OROT scheme과 iPhone Simulator를 선택할 수 있다.
- [ ] 앱 target의 Debug·Release 설정을 확인했다.

막히면: 기기가 없을 때는 런타임과 가상 기기 생성부터 확인한다. 코드 편집으로 해결하려고 하지 않는다.

<a id="step-2"></a>
## 2. 기본 화면 한 번 실행하기

**목표:** 서버·모델·폴더 이동 없이 현재 프로젝트가 실행되는지 확인한다.

현재 `apps/ios/OROT/ContentView.swift`를 열어 **전체 교체**한다. 기존 `import Playgrounds`와 `#Playground` 산술 예제는 이 블록에 포함하지 않는다.

```swift
// File: apps/ios/OROT/ContentView.swift
import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack(spacing: 12) {
            Text("OROT")
                .font(.largeTitle.bold())
            Text("첫 번째 iOS 앱이 실행되었습니다.")
        }
        .padding()
    }
}

#Preview {
    ContentView()
}
```

현재 `MyApp.swift`는 아직 그대로 둔다. 이 파일의 `WindowGroup` 안에서 `ContentView()`를 열고 있다.

1. `⌘S`로 저장한다.
2. `⌘B`를 누르고 빌드 완료를 기다린다.
3. 성공하면 `⌘R`을 누른다.
4. 가상 iPhone 화면에서 `OROT`와 안내 문구를 확인한다.

`VStack`은 화면 요소를 세로로 놓는다. `body`는 화면을 설명하는 부분이며 여기에서 네트워크 요청을 시작하지 않는다. `#Preview`는 편집기 미리보기다. 미리보기 성공과 Simulator 실행 성공은 구분해서 확인한다.

**완료 확인**

- [ ] Build Succeeded를 확인했다.
- [ ] 실제 Simulator 화면에 두 문구가 보인다.
- [ ] 문구를 잠깐 바꾸고 다시 실행하면 바뀐 문구가 보인다.

막히면: `⌘5`에서 첫 오류를 연다. `ContentView`를 찾지 못하면 파일이 `OROT` 폴더에 있고 앱 target에 속하는지 확인한다.

<a id="step-3"></a>
## 3. 폴더와 앱 진입점 정리하기

**목표:** 동작을 유지한 채 파일의 자리를 정한다.

### 3.1 실제 폴더 만들기

현재 `OROT`는 디스크와 동기화되는 폴더로 프로젝트에 연결되어 있다. Xcode의 Project navigator에서 앱 소스 `OROT`를 선택하고 폴더 생성 메뉴로 다음 폴더를 만든다. 메뉴가 헷갈리면 Finder에서 `apps/ios/OROT/` 안에 실제 폴더를 만든 뒤 Xcode에 나타나는지 확인한다.

```text
apps/ios/OROT/
├── App/
├── Core/
│   ├── Models/
│   └── Networking/
├── Features/
│   ├── Feed/
│   └── ReleaseDetail/
└── Resources/
```

화면에만 보이는 그룹과 디스크 폴더를 혼동하지 않도록 File Inspector의 경로 또는 Show in Finder로 확인한다. 동기화 폴더는 개별 파일을 프로젝트 설정에 나열하지 않을 수 있다. Build Phases의 Sources 목록이 비어 있다는 이유만으로 파일을 중복 등록하지 않는다. [Apple 파일·폴더 관리](https://developer.apple.com/documentation/xcode/managing-files-and-folders-in-your-xcode-project)

### 3.2 기존 파일 이동하기

1. 기존 `MyApp.swift`를 `App`으로 **이동**한다.
2. 파일명을 `OROTApp.swift`로 바꾼다.
3. 그 파일을 다음 코드로 **전체 교체**한다.
4. 기존 `Assets.xcassets`를 통째로 `Resources`로 이동한다. 복사해서 두 개 만들지 않는다.
5. `ContentView.swift`는 아직 현재 위치에 둔다.

```swift
// File: apps/ios/OROT/App/OROTApp.swift
import SwiftUI

@main
@MainActor
struct OROTApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
```

`@main`은 앱 시작점이다. 프로젝트 전체 검색 `⇧⌘F`로 `@main`을 검색했을 때 앱 코드에 한 개만 있어야 한다. 새 파일을 만들고 이전 `MyApp.swift`를 남겨 두면 시작점이 두 개가 된다.

`@MainActor`는 UI 상태에 접근하는 실행 영역을 맞춘다. 첫 실습에서는 서비스와 화면 모델도 여기에 맞춘다. `async`를 붙였다고 CPU 작업이 자동으로 별도 스레드로 이동하는 것은 아니다.

**완료 확인**

- [ ] `⌘B` 성공.
- [ ] `⌘R` 후 2장과 같은 화면.
- [ ] 기존 `MyApp.swift`와 중복 `@main`이 없다.

막히면: Xcode에 파일이 빨갛게 보이면 참조 경로가 실제 위치와 다른 것이다. 중복 파일을 추가하기 전에 Finder 경로를 확인한다.

### 앞으로 Swift 파일을 추가하는 공통 방법

1. Project navigator에서 저장할 폴더를 선택한다.
2. File → New → File from Template 계열 메뉴에서 **Swift File**을 고른다.
3. 이 책에 나온 파일명을 입력한다.
4. 저장 위치를 확인한다. target 선택이 나오면 앱 파일에는 OROT만 선택한다.
5. 자동 생성된 내용을 지우고 해당 블록 전체를 넣는다.
6. `⌘S`, `⌘B` 순으로 확인한다.

테스트 폴더는 앱 소스 `OROT/` **밖**, `OROT.xcodeproj`와 같은 깊이에 둔다. 앱 동기화 폴더에 테스트 코드를 넣지 않는다.

<a id="step-4"></a>
## 4. 단위 테스트를 실행할 자리 만들기

**목표:** `OROTTests` target을 만들고 `⌘U`가 무엇을 실행하는지 이해한다.

현재 프로젝트에는 앱 target 하나만 있다. `OROTTests`라는 폴더만 만들어서는 테스트가 실행되지 않는다.

1. File → New → Target을 선택한다.
2. iOS의 **Unit Testing Bundle**을 선택한다.
3. 이름을 `OROTTests`, 테스트할 앱 또는 Host Application을 `OROT`로 지정한다.
4. Testing System 선택이 있으면 Swift Testing을 선택한다. 생성된 파일이 XCTest 형식이어도 이 책의 Swift Testing 파일로 교체할 수 있다.
5. 최종 실제 경로가 `apps/ios/OROTTests/`인지 확인한다.
6. 테스트 target의 Swift Language Version을 6.0, 최소 iOS를 17.0으로 맞춘다.
7. Product → Scheme → Edit Scheme → Test에서 `OROTTests`가 포함되었는지 확인한다. Test Plan을 사용한다면 해당 계획의 테스트 target 목록에서 확인한다.
8. 자동 생성된 테스트가 있다면 일단 `⌘U`로 실행한다. 아무 테스트도 없으면 5장의 테스트를 만든 뒤 실행한다.

템플릿의 비어 있는 테스트 통과는 연결 확인일 뿐이다. 5장에서 실제 응답 검증으로 교체한다. 앱 이름이 다르면 `@testable import OROT`의 `OROT`는 앱 target의 Product Module Name에 맞춰야 한다.

이 책의 단위 테스트에는 `@MainActor`를 붙여 앱 예제와 실행 영역을 맞춘다. 단순 DTO 테스트가 UI를 조작한다는 뜻은 아니다. [Apple 테스트 추가](https://developer.apple.com/documentation/xcode/adding-tests-to-your-xcode-project)

**완료 확인**

- [ ] TARGETS에 `OROT`, `OROTTests`가 보인다.
- [ ] scheme 또는 Test Plan에 `OROTTests`가 포함되어 있다.
- [ ] 테스트 파일의 target은 OROTTests이며 OROT에는 포함되지 않는다.

막히면: `No such module 'Testing'` 또는 `No such module 'OROT'`는 먼저 target 소속·선택한 Xcode·Product Module Name을 확인한다. 패키지를 임의로 설치하지 않는다.

<a id="step-5"></a>
## 5. 서버 JSON을 Swift 데이터로 읽기

**목표:** 화면을 만들기 전에 데이터 모양이 맞는지 자동 테스트한다.

### 5.1 DTO 파일 만들기

DTO는 서버와 주고받는 데이터 구조다. 첫 구현은 공개 응답 중 화면에 필요한 필드만 읽는다. `String?`는 문자열 또는 값 없음, `Int?`는 정수 또는 값 없음이다.

**새 파일 / target: OROT**

```swift
// File: apps/ios/OROT/Core/Models/ReleaseDTO.swift
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

`CodingKeys`는 JSON의 `artist_name`을 Swift의 `artistName`에 연결한다. 따라서 이 실습에서는 디코더의 `.convertFromSnakeCase`를 추가하지 않는다. `Codable`은 JSON 읽기·쓰기를 제공하며 지금은 읽기에 사용한다. 원화는 소수점이 없는 정수로 보관한다.

날짜는 일단 원문 문자열이다. `release_date`는 달력 날짜, `preorder_*_at`는 시간대가 있는 시각이다. 아직 표시 함수가 없으므로 날짜를 임의로 `Date`로 바꾸지 않는다.

저장 후 `⌘B`. 화면은 여전히 기본 화면인 것이 정상이다.

### 5.2 공통 합성 데이터 만들기

**새 파일 / target: OROT**. `App/PreviewSupport/` 폴더를 이때 추가한다.

```swift
// File: apps/ios/OROT/App/PreviewSupport/SampleData.swift
import Foundation

#if DEBUG
@MainActor
enum SampleData {
    static let releaseJSON = #"""
    {
      "id": 101,
      "title": "연습용 음반 A",
      "artist_name": "OROT 연습 아티스트",
      "variant": "Black Vinyl",
      "is_limited": false,
      "curation": "MANUAL",
      "is_published": true,
      "schedule_status": "SCHEDULED",
      "until_sold_out": false,
      "release_date": "2026-10-01",
      "preorder_opens_at": "2026-09-30T15:00:00Z",
      "preorder_closes_at": null,
      "links": [
        {
          "id": 1001,
          "shop_name": "연습 판매처",
          "url": "https://example.com/records/101",
          "price_krw": 0
        }
      ]
    }
    """#

    static var feedJSON: String {
        """
        {
          "items": [{
            "kind": "UPCOMING",
            "at": "2026-09-30T15:00:00Z",
            "event_type": null,
            "release": \(releaseJSON)
          }],
          "generated_at": "2026-09-22T00:00:00Z"
        }
        """
    }

    static func page() throws -> FeedPageDTO {
        try JSONDecoder().decode(FeedPageDTO.self, from: Data(feedJSON.utf8))
    }

    static func release() throws -> ReleaseDTO {
        try JSONDecoder().decode(ReleaseDTO.self, from: Data(releaseJSON.utf8))
    }
}
#endif
```

위 JSON은 운영 데이터와 무관한 합성 예제다. `example.com`은 실제 판매처가 아니며 해당 경로는 오류 페이지가 나올 수도 있다. 날짜·종류도 고정된 디코딩 예제이므로 시간이 지나도 자동으로 현재 상태가 바뀌지 않는다.

`#if DEBUG` 안의 데이터는 Debug에서만 사용한다. 테스트와 Preview가 같은 예제를 쓸 수 있도록 앱 모듈에 두되, Release 앱에는 포함하지 않는다. `try`는 디코딩 실패가 가능하다는 뜻이다.

### 5.3 첫 의미 있는 테스트 작성하기

`apps/ios/OROTTests/Models/`를 만든다. 템플릿의 비어 있는 테스트 파일은 제거하거나 아래 파일로 대체한다.

**새 파일 / target: OROTTests**

```swift
// File: apps/ios/OROTTests/Models/ReleaseDTOTests.swift
import Foundation
import Testing
@testable import OROT

@MainActor
struct ReleaseDTOTests {
    @Test func decodesFeedAndPreservesZeroWon() throws {
        let page = try SampleData.page()
        let item = try #require(page.items.first)
        #expect(item.id == 101)
        #expect(item.release.title == "연습용 음반 A")
        #expect(item.release.artistName == "OROT 연습 아티스트")
        #expect(item.release.links.first?.priceKrw == 0)
        #expect(item.release.links.first?.safeURL?.scheme == "https")
    }

    @Test func missingOptionalArtistIsAllowed() throws {
        let json = #"""
        {"id": 102, "title": "아티스트 미정", "is_published": true, "links": []}
        """#
        let release = try JSONDecoder().decode(ReleaseDTO.self, from: Data(json.utf8))
        #expect(release.artistName == nil)
    }

    @Test func missingRequiredTitleIsRejected() {
        let json = #"""
        {"id": 102, "is_published": true, "links": []}
        """#
        #expect(throws: DecodingError.self) {
            try JSONDecoder().decode(ReleaseDTO.self, from: Data(json.utf8))
        }
    }

    @Test func unsafeLinkIsNotOpened() {
        let link = ReleaseLinkDTO(
            id: 1, shopName: "연습", url: "javascript:alert(1)", priceKrw: nil
        )
        #expect(link.safeURL == nil)
    }
}
```

`@Test`는 실행할 검증 하나다. `#expect`는 기대한 조건을 확인한다. `#require`는 값이 꼭 있어야 다음 줄을 검사할 수 있을 때 사용한다. 값이 없으면 크래시 대신 테스트 실패로 기록된다.

1. `⌘U`를 누른다.
2. `⌘6`에서 `ReleaseDTOTests`의 네 테스트가 통과했는지 확인한다.
3. 연습으로 첫 테스트의 `101`을 `999`로 바꾸고 그 테스트만 실행한다.
4. 예상대로 실패하는지 확인한 다음 **반드시 101로 복원**하고 다시 통과시킨다.

**완료 확인**

- [ ] 네 테스트가 통과한다.
- [ ] 일부러 바꾼 기대값이 실패하고 복원하면 통과한다.
- [ ] 테스트 실행 중 실제 서버를 호출하지 않는다.

막히면: `SampleData`를 찾지 못할 때는 Test 동작의 Build Configuration이 Debug인지, SampleData 파일이 앱 target에 들어갔는지 확인한다.

<a id="step-6"></a>
## 6. APIClient를 만들고 인터넷 없이 검사하기

**목표:** 요청 주소·쿼리, HTTP 오류, JSON 검증을 UI와 따로 확인한다.

### 6.1 서비스의 약속과 오류 정의하기

**새 파일 / target: OROT**

```swift
// File: apps/ios/OROT/Core/Networking/ReleaseService.swift
import Foundation

enum FeedSort: String, CaseIterable, Identifiable, Sendable {
    case imminent, recent
    var id: String { rawValue }
    var title: String { self == .imminent ? "발매 임박순" : "최근 변경순" }
}

enum APIError: Error, LocalizedError, Equatable {
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
```

`protocol`은 “피드와 상세를 가져오는 함수가 있어야 한다”는 약속이다. 화면은 실제 통신인지 가짜 데이터인지 몰라도 이 두 함수를 부를 수 있다. `async`는 기다리는 작업, `throws`는 실패할 수 있는 작업을 뜻한다.

저장하고 `⌘B`를 실행한다.

### 6.2 실제 통신을 담당하는 파일 만들기

**새 파일 / target: OROT**

```swift
// File: apps/ios/OROT/Core/Networking/APIClient.swift
import Foundation

@MainActor
final class APIClient: ReleaseService {
    typealias Transport = @MainActor (URLRequest) async throws -> (Data, URLResponse)

    private let baseURL: URL
    private let transport: Transport

    init(
        baseURL: URL,
        transport: @escaping Transport = { request in
            try await URLSession.shared.data(for: request)
        }
    ) {
        self.baseURL = baseURL
        self.transport = transport
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
        request.httpMethod = "GET"
        request.timeoutInterval = 12
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await transport(request)
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

`transport`는 요청을 전달하면 응답을 돌려주는 함수다. 평소에는 `URLSession`을 사용하고 테스트에서는 가짜 응답 함수를 전달한다. 테스트를 위해 실제 API에 연결할 필요가 없다. `@escaping`은 전달된 함수를 저장했다가 나중에 사용한다는 뜻이다.

HTTP 상태를 JSON보다 먼저 확인하므로 HTML 오류 페이지가 와도 502는 502 오류로 처리한다. 200인데 JSON이 아닌 경우와 JSON 자체가 깨진 경우도 구분한다. 취소된 요청은 이후 화면 상태를 덮어쓰지 않도록 위로 전달한다. [Apple 비동기 URLSession](https://developer.apple.com/documentation/foundation/urlsession/data(for:delegate:))

여기까지 저장하고 `⌘B`. 앱 진입점은 아직 APIClient를 사용하지 않으므로 앱을 실행해도 네트워크 요청은 없다.

### 6.3 APIClient 테스트 작성하기

`OROTTests/Networking/`을 만든다.

**새 파일 / target: OROTTests**

```swift
// File: apps/ios/OROTTests/Networking/APIClientTests.swift
import Foundation
import Testing
@testable import OROT

@MainActor
struct APIClientTests {
    private func baseURL() throws -> URL {
        try #require(URL(string: "https://example.com/api/mobile"))
    }

    private func response(
        to request: URLRequest,
        status: Int = 200,
        mime: String = "application/json",
        body: String
    ) throws -> (Data, URLResponse) {
        let url = try #require(request.url)
        let response = try #require(HTTPURLResponse(
            url: url, statusCode: status, httpVersion: nil,
            headerFields: ["Content-Type": mime]
        ))
        return (Data(body.utf8), response)
    }

    @Test func feedUsesPublicPathAndQuery() async throws {
        let client = APIClient(baseURL: try baseURL()) { request in
            let url = try #require(request.url)
            #expect(url.path == "/api/mobile/v1/feed")
            #expect(request.httpMethod == "GET")
            #expect(request.value(forHTTPHeaderField: "Accept") == "application/json")
            let parts = try #require(URLComponents(url: url, resolvingAgainstBaseURL: false))
            let query = parts.queryItems ?? []
            #expect(query.first(where: { $0.name == "sort" })?.value == "recent")
            #expect(query.first(where: { $0.name == "limit" })?.value == "50")
            return try response(to: request, body: SampleData.feedJSON)
        }
        let page = try await client.feed(sort: .recent)
        #expect(page.items.first?.id == 101)
    }

    @Test func detailUsesRequestedID() async throws {
        let client = APIClient(baseURL: try baseURL()) { request in
            #expect(request.url?.path == "/api/mobile/v1/releases/101")
            return try response(to: request, body: SampleData.releaseJSON)
        }
        let release = try await client.release(id: 101)
        #expect(release.id == 101)
    }

    @Test func httpErrorWinsOverHTMLBody() async throws {
        let client = APIClient(baseURL: try baseURL()) { request in
            try response(to: request, status: 502, mime: "text/html", body: "<h1>502</h1>")
        }
        await #expect(throws: APIError.http(502)) {
            try await client.feed(sort: .imminent)
        }
    }

    @Test func successfulHTMLIsRejected() async throws {
        let client = APIClient(baseURL: try baseURL()) { request in
            try response(to: request, mime: "text/html", body: "<h1>Home</h1>")
        }
        await #expect(throws: APIError.invalidResponse) {
            try await client.feed(sort: .imminent)
        }
    }

    @Test func malformedJSONIsRejected() async throws {
        let client = APIClient(baseURL: try baseURL()) { request in
            try response(to: request, body: "{broken")
        }
        await #expect(throws: APIError.decoding) {
            try await client.feed(sort: .imminent)
        }
    }

    @Test func unpublishedDetailIsRejected() async throws {
        let body = SampleData.releaseJSON.replacingOccurrences(
            of: "\"is_published\": true", with: "\"is_published\": false"
        )
        let client = APIClient(baseURL: try baseURL()) { request in
            try response(to: request, body: body)
        }
        await #expect(throws: APIError.invalidResponse) {
            try await client.release(id: 101)
        }
    }

    @Test func duplicateFeedIDsAreRejected() async throws {
        let original = try SampleData.page()
        let duplicate = FeedPageDTO(
            items: original.items + original.items, generatedAt: original.generatedAt
        )
        let body = String(decoding: try JSONEncoder().encode(duplicate), as: UTF8.self)
        let client = APIClient(baseURL: try baseURL()) { request in
            try response(to: request, body: body)
        }
        await #expect(throws: APIError.invalidResponse) {
            try await client.feed(sort: .imminent)
        }
    }
}
```

`example.com`이라는 문자열은 요청 주소 검사용이다. 모든 테스트가 `transport`를 교체했으므로 DNS·HTTP 연결은 일어나지 않는다. 이 검증은 HTTP 처리 로직을 검사하며 실제 TLS·Funnel·서버 가용성까지 증명하지 않는다.

**완료 확인**

- [ ] `⌘U`로 DTO 네 개와 APIClient 일곱 개가 통과한다.
- [ ] `/api/mobile/v1/feed` 경로와 `sort`, `limit` 쿼리의 의미를 설명할 수 있다.
- [ ] 공개 응답이 아니거나 ID가 중복되면 오류로 처리된다.

막히면: `Invalid redeclaration`은 같은 타입을 두 파일에 정의했을 가능성이 높다. 기존 개발 가이드의 통합 `APIClient.swift` 코드와 이 책의 분리된 `ReleaseService.swift` 코드를 중복해서 붙이지 않는다.

<a id="step-7"></a>
## 7. 화면에 공급할 가짜 서비스 만들기

**목표:** 성공·빈 목록·실패를 서버 조작 없이 재현한다.

**새 파일 / target: OROT**

```swift
// File: apps/ios/OROT/App/PreviewSupport/DemoReleaseService.swift
import Foundation

#if DEBUG
@MainActor
final class DemoReleaseService: ReleaseService {
    enum Mode: Equatable {
        case success, empty, failure, failOnce, missingDetail
    }

    private let mode: Mode
    private let delay: Duration
    private var feedCalls = 0

    init(mode: Mode = .success, delay: Duration = .milliseconds(300)) {
        self.mode = mode
        self.delay = delay
    }

    func feed(sort: FeedSort) async throws -> FeedPageDTO {
        feedCalls += 1
        let call = feedCalls
        try await Task.sleep(for: delay)

        if mode == .failure || (mode == .failOnce && call == 1) {
            throw APIError.http(502)
        }
        let page = try samplePage()
        if mode == .empty {
            return FeedPageDTO(items: [], generatedAt: page.generatedAt)
        }
        let items = sort == .recent ? Array(page.items.reversed()) : page.items
        return FeedPageDTO(items: items, generatedAt: page.generatedAt)
    }

    func release(id: Int) async throws -> ReleaseDTO {
        try await Task.sleep(for: delay)
        if mode == .missingDetail { throw APIError.http(404) }
        let page = try samplePage()
        guard let item = page.items.first(where: { $0.id == id }) else {
            throw APIError.http(404)
        }
        return item.release
    }

    private func samplePage() throws -> FeedPageDTO {
        let firstPage = try SampleData.page()
        let secondJSON = SampleData.releaseJSON
            .replacingOccurrences(of: "\"id\": 101", with: "\"id\": 102")
            .replacingOccurrences(of: "\"id\": 1001", with: "\"id\": 1002")
            .replacingOccurrences(of: "/records/101", with: "/records/102")
            .replacingOccurrences(of: "연습용 음반 A", with: "연습용 음반 B")
        let secondRelease = try JSONDecoder().decode(
            ReleaseDTO.self, from: Data(secondJSON.utf8)
        )
        let secondItem = FeedItemDTO(
            kind: "UPCOMING", at: "2026-09-30T15:00:00Z",
            eventType: nil, release: secondRelease
        )
        return FeedPageDTO(
            items: firstPage.items + [secondItem], generatedAt: firstPage.generatedAt
        )
    }
}
#endif
```

가짜 서비스의 최근 변경순은 시각 계산 없이 배열을 뒤집는다. 정렬 선택이 화면에 반영되는지 관찰하기 위한 장치다. 실제 정렬 책임은 서버에 있고 APIClient는 정렬값만 보낸다. 두 연습 음반의 판매처 URL도 화면 학습용 예제 주소다.

`Task.sleep`은 로딩 표시를 볼 시간을 만든다. 이 함수는 비동기로 기다리므로 UI를 동기적으로 멈추지 않는다. 자동 모델 테스트에서는 지연을 0으로 전달한다.

**완료 확인**

- [ ] `⌘B`, 기존 테스트 `⌘U`가 통과한다.
- [ ] 앱에는 아직 기본 화면이 뜬다. 가짜 서비스는 연결 전이므로 정상이다.

<a id="step-8"></a>
## 8. 피드의 상태를 관리하는 FeedModel 만들기

**목표:** 화면 없이도 로딩·결과·오류 상태를 검증한다.

### 8.1 모델 파일 작성

**새 파일 / target: OROT**

```swift
// File: apps/ios/OROT/Features/Feed/FeedModel.swift
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

    init(service: any ReleaseService) {
        self.service = service
    }

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

`@Observable`은 화면이 읽는 값이 바뀌었음을 알린다. `private(set)`은 화면에서 값은 읽되 직접 바꾸지는 못하게 한다. `defer`는 함수가 끝날 때 실행되므로 성공·실패 모두에서 로딩을 끝낼 수 있다.

`revision`은 요청 번호다. 정렬을 빠르게 바꿀 때 오래된 응답이 늦게 도착해도 최신 결과를 덮지 못하게 한다. 첫 실습에서는 로딩 때 기존 목록을 비운다. 마지막 성공 목록 보존·오프라인 캐시는 후속 과제다.

저장하고 `⌘B`.

### 8.2 모델 테스트 작성

**새 파일 / target: OROTTests**. `OROTTests/Features/`를 추가한다.

```swift
// File: apps/ios/OROTTests/Features/FeedModelTests.swift
import Foundation
import Testing
@testable import OROT

@MainActor
private final class ControlledReleaseService: ReleaseService {
    private var pending: [FeedSort: CheckedContinuation<FeedPageDTO, any Error>] = [:]
    private var started: Set<FeedSort> = []
    private var waiters: [FeedSort: CheckedContinuation<Void, Never>] = [:]

    func feed(sort: FeedSort) async throws -> FeedPageDTO {
        try await withCheckedThrowingContinuation { continuation in
            pending[sort] = continuation
            started.insert(sort)
            waiters.removeValue(forKey: sort)?.resume()
        }
    }

    func waitUntilStarted(_ sort: FeedSort) async {
        if started.contains(sort) { return }
        await withCheckedContinuation { continuation in
            waiters[sort] = continuation
        }
    }

    func finish(_ sort: FeedSort, with page: FeedPageDTO) {
        pending.removeValue(forKey: sort)?.resume(returning: page)
    }

    func release(id: Int) async throws -> ReleaseDTO {
        throw APIError.http(404)
    }
}

@MainActor
struct FeedModelTests {
    @Test func successLoadsItems() async {
        let model = FeedModel(service: DemoReleaseService(delay: .zero))
        await model.load(sort: .imminent)
        #expect(model.items.map(\.id) == [101, 102])
        #expect(model.message == nil)
        #expect(!model.isLoading)
    }

    @Test func emptyIsNotAnError() async {
        let model = FeedModel(service: DemoReleaseService(mode: .empty, delay: .zero))
        await model.load(sort: .imminent)
        #expect(model.items.isEmpty)
        #expect(model.message == nil)
        #expect(!model.isLoading)
    }

    @Test func retryRecoversFromError() async {
        let model = FeedModel(service: DemoReleaseService(mode: .failOnce, delay: .zero))
        await model.load(sort: .imminent)
        #expect(model.message != nil)
        #expect(model.items.isEmpty)
        await model.load(sort: .imminent)
        #expect(model.message == nil)
        #expect(model.items.count == 2)
        #expect(!model.isLoading)
    }

    @Test func olderResponseCannotReplaceNewerResult() async throws {
        let service = ControlledReleaseService()
        let model = FeedModel(service: service)
        let original = try SampleData.page()
        let empty = FeedPageDTO(items: [], generatedAt: original.generatedAt)

        let oldTask = Task { await model.load(sort: .imminent) }
        await service.waitUntilStarted(.imminent)
        #expect(model.isLoading)

        let newTask = Task { await model.load(sort: .recent) }
        await service.waitUntilStarted(.recent)
        service.finish(.recent, with: empty)
        await newTask.value
        #expect(model.items.isEmpty)

        service.finish(.imminent, with: original)
        await oldTask.value
        #expect(model.items.isEmpty)
        #expect(model.message == nil)
        #expect(!model.isLoading)
    }

    @Test func cancelledRequestDoesNotShowErrorOrItems() async throws {
        let service = ControlledReleaseService()
        let model = FeedModel(service: service)
        let page = try SampleData.page()
        let task = Task { await model.load(sort: .imminent) }
        await service.waitUntilStarted(.imminent)
        task.cancel()
        service.finish(.imminent, with: page)
        await task.value
        #expect(model.items.isEmpty)
        #expect(model.message == nil)
        #expect(!model.isLoading)
    }
}
```

`ControlledReleaseService`는 테스트가 응답 순서를 직접 정할 수 있게 한다. 고정된 몇 초를 기다리며 운에 맡기는 검증을 피한다. `CheckedContinuation`의 문법은 지금 외우지 않아도 된다. **두 번째 요청을 먼저 끝내고 첫 번째 요청을 나중에 끝낸다**는 테스트 흐름을 이해하면 된다. 이 도우미는 서로 다른 정렬값을 한 번씩 요청하는 위 테스트 전용이다.

**완료 확인**

- [ ] `⌘U`에서 새 모델 테스트 다섯 개가 통과한다.
- [ ] DTO·APIClient 테스트도 계속 통과한다.
- [ ] 빈 결과, 오류, 취소가 서로 다른 상황임을 설명할 수 있다.

막히면: 테스트가 끝나지 않으면 ControlledReleaseService의 `waitUntilStarted`와 `finish`의 정렬값이 짝을 이루는지 확인한다. `⌘.`로 중지한 뒤 오타를 고친다.

<a id="step-9"></a>
## 9. 피드 화면을 가짜 데이터에 연결하기

**목표:** 두 음반, 정렬 전환, 로딩, 빈 결과, 재시도를 눈으로 확인한다.

### 9.1 FeedView 만들기

**새 파일 / target: OROT**

```swift
// File: apps/ios/OROT/Features/Feed/FeedView.swift
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
                .accessibilityIdentifier("feed-sort")

                List {
                    if model.isLoading {
                        ProgressView("일정 불러오는 중")
                    } else if let message = model.message {
                        Text(message)
                            .accessibilityIdentifier("feed-error")
                        Button("다시 시도") { retryVersion += 1 }
                            .accessibilityIdentifier("feed-retry")
                    } else if model.items.isEmpty {
                        Text("아직 등록된 일정이 없습니다.")
                            .accessibilityIdentifier("feed-empty")
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
                            .accessibilityIdentifier("feed-release-\(item.id)")
                        }
                    }
                }
                .refreshable { await model.load(sort: sort) }
            }
            .navigationTitle("OROT")
            .navigationDestination(for: Int.self) { id in
                Text("상세 화면 준비 중 · ID \(id)")
            }
            .task(id: "\(sort.rawValue)-\(retryVersion)") {
                await model.load(sort: sort)
            }
        }
    }
}

#if DEBUG
#Preview {
    FeedView(service: DemoReleaseService())
}
#endif
```

상세 화면은 다음 장에서 만들므로 지금은 ID만 표시한다. 이 상태에서도 컴파일되고 목록의 화면 이동을 검증할 수 있다.

- `@State`는 정렬값·모델을 뷰 생명주기 동안 보관한다.
- `.task(id:)`는 화면이 나타나거나 ID가 바뀔 때 로딩하며 이전 작업을 취소한다.
- `.refreshable`은 목록을 아래로 당길 때 실행한다.
- `NavigationLink`는 선택한 발매 ID를 `NavigationStack`에 전달한다.
- `accessibilityIdentifier`는 이후 UI 테스트가 요소를 찾을 이름이다. 화면에 글자로 나타나지는 않는다.

저장하고 `⌘B`. 아직 앱 진입점은 ContentView이므로 실행 화면은 바뀌지 않는다.

### 9.2 진입 화면 교체하기

`App/OROTApp.swift`를 다음 코드로 **전체 교체**한다.

```swift
// File: apps/ios/OROT/App/OROTApp.swift
import SwiftUI
import Foundation

@main
@MainActor
struct OROTApp: App {
    #if DEBUG
    private let service: any ReleaseService

    init() {
        let arguments = ProcessInfo.processInfo.arguments
        let mode: DemoReleaseService.Mode
        if arguments.contains("--demo-empty") {
            mode = .empty
        } else if arguments.contains("--demo-error") {
            mode = .failure
        } else if arguments.contains("--demo-retry") {
            mode = .failOnce
        } else if arguments.contains("--demo-detail-missing") {
            mode = .missingDetail
        } else {
            mode = .success
        }
        service = DemoReleaseService(mode: mode)
    }
    #endif

    var body: some Scene {
        WindowGroup {
            #if DEBUG
            FeedView(service: service)
            #else
            ContentView()
            #endif
        }
    }
}
```

이 단계의 Release 빌드는 임시로 ContentView를 보여 준다. 12장에서 실제 서비스로 연결한 뒤 ContentView를 정리한다. 지금 삭제하지 않는다.

`⌘B` → `⌘R`. 기본 두 문구 대신 OROT 목록과 연습 음반 두 개가 보여야 한다. `최근 변경순`을 누르면 B → A, `발매 임박순`을 누르면 A → B가 된다.

### 9.3 실행 인자로 화면 상태 바꾸기

앱 코드를 매번 수정하는 대신 Xcode가 앱을 켤 때 값을 전달한다.

1. `⌘.`로 실행을 중지한다.
2. Product → Scheme → Edit Scheme을 연다.
3. 왼쪽 **Run → Arguments → Arguments Passed On Launch**를 찾는다.
4. `+`로 아래 인자 중 **하나만** 추가하고 체크한다.
5. 창을 닫고 `⌘R`로 다시 실행한다.

| 체크한 인자 | 기대 화면 |
|---|---|
| 없음 | 연습 음반 A·B |
| `--demo-empty` | 아직 등록된 일정이 없습니다 |
| `--demo-error` | 오류 안내와 다시 시도 버튼, 재시도해도 실패 |
| `--demo-retry` | 처음 실패, 다시 시도를 누르면 두 음반 표시 |
| `--demo-detail-missing` | 피드는 정상, 10장의 상세 조회는 404 |

여러 인자를 동시에 켜면 코드의 위쪽 조건이 먼저 적용되어 혼동하기 쉽다. **한 번에 하나만** 사용한다. 인자를 바꾼 뒤에는 기존 프로세스를 중지하고 다시 실행한다.

**완료 확인**

- [ ] 정상 목록과 A/B 정렬 전환을 확인했다.
- [ ] 목록을 아래로 당기면 다시 로딩한다.
- [ ] 빈 결과·지속 실패·한 번 실패 후 복구를 확인했다.
- [ ] 행을 누르면 해당 ID의 임시 상세 화면으로 이동한다.
- [ ] 확인 후 Run의 데모 인자를 모두 해제하고 `⌘U`가 통과한다.

막히면: 기본 문구만 보이면 진입점을 교체했는지, Run의 Build Configuration이 Debug인지 확인한다. Preview는 자체 DemoReleaseService를 사용하므로 Run의 실행 인자가 반영되지 않는 것이 정상이다.

<a id="step-10"></a>
## 10. 상세 화면과 판매처 링크 연결하기

**목표:** 목록 → 상세 재조회 → 외부 링크 → 목록 복귀 흐름을 만든다.

### 10.1 상세 파일 작성하기

**새 파일 / target: OROT**

```swift
// File: apps/ios/OROT/Features/ReleaseDetail/ReleaseDetailView.swift
import Foundation
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
                    Text(release.title)
                        .font(.title2)
                        .accessibilityIdentifier("detail-title")
                    Text(release.artistName ?? "아티스트 정보 없음")
                    if let variant = release.variant { Text(variant) }
                }
                Section("일정 · 연결 확인용 원문") {
                    Text("상태: \(release.scheduleStatus ?? "정보 없음")")
                    Text("발매일: \(release.releaseDate ?? "미정")")
                    Text("예약 시작: \(release.preorderOpensAt ?? "미정")")
                    if release.untilSoldOut == true {
                        Text("예약 마감: 품절 시까지")
                    } else {
                        Text("예약 마감: \(release.preorderClosesAt ?? "미정")")
                    }
                }
                Section("판매처") {
                    if release.links.isEmpty { Text("등록된 판매처가 없습니다.") }
                    ForEach(release.links) { link in
                        if let url = link.safeURL {
                            Link(destination: url) {
                                VStack(alignment: .leading) {
                                    Text(link.shopName)
                                    if let price = link.priceKrw {
                                        Text("\(price.formatted(.number.locale(Locale(identifier: "ko_KR"))))원")
                                    } else {
                                        Text("가격 정보 없음")
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
                    .accessibilityIdentifier("detail-error")
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

#if DEBUG
#Preview {
    NavigationStack {
        ReleaseDetailView(id: 101, service: DemoReleaseService())
    }
}
#endif
```

목록의 객체를 그대로 표시하는 대신 ID로 다시 조회한다. 실제 서버에서는 목록을 연 뒤 일정이 수정되거나 비공개로 전환될 수 있기 때문이다. 404이면 기존 상세를 보여 주지 않고 “일정을 찾을 수 없습니다”를 표시한다.

이 실습의 날짜와 상태는 **연결 확인용 원문**이다. 예를 들어 `2026-09-30T15:00:00Z`는 KST로 10월 1일 00:00이다. 이 원문 화면을 최종 사용자 화면으로 배포하지 않는다. 정확한 KST·TBA·ON_SALE 표시는 기존 가이드 10장의 후속 과제로 남긴다.

### 10.2 임시 상세 화면 교체하기

`FeedView.swift`에서 아래 부분을 찾는다.

```swift
.navigationDestination(for: Int.self) { id in
    Text("상세 화면 준비 중 · ID \(id)")
}
```

**이 부분만** 다음으로 교체한다. 새 `NavigationStack`을 추가하지 않는다.

```swift
.navigationDestination(for: Int.self) { id in
    ReleaseDetailView(id: id, service: service)
}
```

### 10.3 수동으로 동선 확인하기

1. Run의 인자를 모두 해제하고 `⌘B`, `⌘R`을 실행한다.
2. 연습 음반 A를 누른다. 상세 제목이 A인지 확인한다.
3. 판매처 가격 `0원`이 표시되는지 확인한다. 0과 값 없음을 구분해야 한다.
4. 판매처를 눌러 브라우저 전환을 확인한다. 이 동작만 예제 외부 사이트로 이동하며 실제 판매처·구매 동작은 아니다. 예제 URL의 404 페이지는 앱 통신 오류가 아니다.
5. 앱으로 돌아와 왼쪽 위 뒤로 버튼으로 피드에 돌아온다.
6. 음반 B를 누르면 제목이 B인지 확인한다.
7. 실행을 중지하고 `--demo-detail-missing` 인자 하나를 켜서 다시 실행한다.
8. 행을 누르면 “일정을 찾을 수 없습니다”가 보이고 앱이 종료되지 않는지 확인한다.

**완료 확인**

- [ ] A와 B가 각각 올바른 상세 제목을 보여 준다.
- [ ] 0원·판매처 링크·뒤로 이동을 확인했다.
- [ ] 상세 404가 오류 안내로 표시된다.
- [ ] 데모 인자를 해제하고 `⌘U`로 기존 테스트가 통과한다.

막히면: 상세가 계속 로딩 중이면 `load()`의 서비스 호출과 `.task`가 있는지 확인한다. `ReleaseDetailView`를 찾지 못하면 새 파일의 target 소속을 확인한다.

<a id="step-11"></a>
## 11. 화면 이동을 UI 테스트로 남기기

**목표:** 사람이 누르던 기본 동선을 자동으로 반복한다. 단위 테스트와 달리 실제 앱 UI를 실행하지만 데이터는 가짜 서비스를 쓴다.

### 11.1 UI 테스트 target 추가

1. File → New → Target → iOS **UI Testing Bundle**을 선택한다.
2. 이름은 `OROTUITests`, Target to be Tested는 `OROT`로 설정한다.
3. 실제 폴더가 `apps/ios/OROTUITests/`인지 확인한다.
4. Swift Language Version을 6.0, 최소 iOS를 17.0으로 맞춘다.
5. OROT scheme의 Test 또는 Test Plan에 이 target을 포함한다.
6. 생성된 템플릿 테스트 파일은 아래 파일로 교체한다. 자동 생성된 launch/performance 예제 파일은 이 실습에서 사용하지 않으므로 제거해도 된다.

UI 테스트는 XCTest를 사용한다. 여기에 Swift Testing의 `@Test`를 섞지 않는다. 앱 내부 타입을 직접 읽지 않으므로 `@testable import OROT`도 필요 없다.

**새 파일 / target: OROTUITests**

```swift
// File: apps/ios/OROTUITests/FeedFlowTests.swift
import XCTest

final class FeedFlowTests: XCTestCase {
    @MainActor
    func testFeedOpensDetailAndReturns() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing"]
        app.launch()

        let row = app.buttons["feed-release-101"]
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()

        let title = app.staticTexts["detail-title"]
        XCTAssertTrue(title.waitForExistence(timeout: 5))
        XCTAssertEqual(title.label, "연습용 음반 A")

        let back = app.navigationBars.buttons.element(boundBy: 0)
        XCTAssertTrue(back.exists)
        back.tap()
        XCTAssertTrue(row.waitForExistence(timeout: 5))
    }

    @MainActor
    func testRetryRecovers() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", "--demo-retry"]
        app.launch()

        let retry = app.buttons["feed-retry"]
        XCTAssertTrue(retry.waitForExistence(timeout: 5))
        retry.tap()
        XCTAssertTrue(app.buttons["feed-release-101"].waitForExistence(timeout: 5))
    }

    @MainActor
    func testEmptyFeed() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", "--demo-empty"]
        app.launch()
        XCTAssertTrue(app.staticTexts["feed-empty"].waitForExistence(timeout: 5))
    }

    @MainActor
    func testMissingDetail() {
        let app = XCUIApplication()
        app.launchArguments = ["--ui-testing", "--demo-detail-missing"]
        app.launch()
        let row = app.buttons["feed-release-101"]
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()
        let error = app.staticTexts["detail-error"]
        XCTAssertTrue(error.waitForExistence(timeout: 5))
        XCTAssertEqual(error.label, "일정을 찾을 수 없습니다.")
    }
}
```

`waitForExistence`는 요소가 나타날 때까지 제한 시간 안에서 기다린다. 앱의 비동기 로딩이 끝나기도 전에 버튼을 누르는 것을 방지한다. `--ui-testing`은 12장에서 실제 API 연결을 강제로 막는 표식으로도 사용한다.

Run의 데모 인자를 모두 해제하고 `⌘U`를 실행한다. UI 테스트가 앱을 여러 번 켜고 끄는 것은 정상이다. 외부 브라우저 이동은 자동 UI 테스트에 포함하지 않았으므로 10장의 수동 점검으로 별도 기록한다.

**완료 확인**

- [ ] UI 테스트 네 개가 통과한다.
- [ ] 기존 단위 테스트 열여섯 개도 통과한다.
- [ ] 실제 서버가 꺼져 있어도 이 테스트는 실행 가능하다.

막히면: 단위 테스트만 실행된다면 Test Plan에 UI target이 빠졌는지 확인한다. 요소를 찾지 못하면 앱이 올바른 데모 모드인지와 `accessibilityIdentifier` 오타부터 확인한다. UI 계층에서 버튼이 다른 요소로 노출되는 환경이라면 Xcode의 UI 디버깅 결과를 보고 쿼리를 맞춘다.

<a id="step-12"></a>
## 12. 실제 공개 API로 바꾸기

**목표:** 앱 코드는 검증된 상태로 두고 데이터 공급자만 실제 서버로 바꾼다.

이 단계는 인터넷을 사용하는 **수동 연결 점검**이다. 자동 테스트와 구분한다. 공개 API를 읽기만 하며 새 일정을 등록하거나 푸시를 보내지 않는다.

### 12.1 공개 주소 확인하기

서버 Mac의 공개 호스트를 확인한다. 서버 Mac에서 기존 운영자가 사용하는 `tailscale funnel status`로 확인하거나, 현재 운영 중인 공개 웹 주소를 사용한다. 이 명령을 개발 Mac에서 실행했다고 서버 Mac의 주소가 나오는 것은 아니다.

주소의 역할은 다음과 같다.

```text
공개 웹:       https://본인의-공개-호스트
앱의 baseURL: https://본인의-공개-호스트/api/mobile
피드 요청:    https://본인의-공개-호스트/api/mobile/v1/feed?sort=imminent&limit=50
상세 요청:    https://본인의-공개-호스트/api/mobile/v1/releases/공개된-ID
```

브라우저에서 피드 주소를 열어 `items`와 `generated_at`이 있는 JSON인지 확인한다. 공개 일정이 없으면 `items: []`도 정상 응답이다. 연습용 일정을 운영 DB에 올려 목록을 채우지 않는다. 7장의 합성 데이터로 화면을 검증할 수 있다.

`http://api:8000`은 Docker 내부 주소다. iPhone의 `localhost`는 iPhone 자신이다. 기존 공개 HTTPS 프록시를 사용하며 이 연결을 위해 API·DB 포트를 공개하거나 관리자 키를 앱에 넣지 않는다.

### 12.2 공개 주소를 한 파일로 모으기

**새 파일 / target: OROT**

```swift
// File: apps/ios/OROT/Core/Networking/AppConfiguration.swift
import Foundation

@MainActor
enum AppConfiguration {
    // https:// 또는 /api/mobile을 포함하지 말고 실제 공개 호스트만 넣는다.
    static let publicHost = "YOUR-PUBLIC-HOST"

    static func apiBaseURL() throws -> URL {
        guard publicHost != "YOUR-PUBLIC-HOST",
              !publicHost.isEmpty,
              !publicHost.contains("/"),
              !publicHost.contains(":") else {
            throw APIError.invalidURL
        }
        var parts = URLComponents()
        parts.scheme = "https"
        parts.host = publicHost
        parts.path = "/api/mobile"
        guard let url = parts.url,
              url.host == publicHost,
              url.user == nil, url.password == nil,
              url.query == nil, url.fragment == nil else {
            throw APIError.invalidURL
        }
        return url
    }
}
```

`YOUR-PUBLIC-HOST`를 실제 호스트로 교체한다. 예를 들어 주소가 `https://my-server.example.com`이라면 값은 `my-server.example.com`이다. 이 호스트 예시 역시 실제 OROT 서버가 아니다.

공개 주소는 비밀이 아니다. `.env`, APNs 키, 관리자 키는 여기 넣지 않는다. 이 코드는 기존 Funnel의 표준 HTTPS 호스트를 위한 실습 설정이며 포트·HTTP 개발 서버를 입력받는 범용 설정은 아니다.

### 12.3 진입점을 최종 형태로 교체하기

`App/OROTApp.swift`를 다음 코드로 **전체 교체**한다. 9장의 조건부 임시 ContentView 대신 모든 빌드가 FeedView를 사용한다.

```swift
// File: apps/ios/OROT/App/OROTApp.swift
import Foundation
import SwiftUI

@main
@MainActor
struct OROTApp: App {
    private let service: any ReleaseService

    init() {
        #if DEBUG
        let arguments = ProcessInfo.processInfo.arguments
        let isTesting = arguments.contains("--ui-testing")
            || ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil
        if arguments.contains("--live-api") && !isTesting {
            service = Self.makeLiveService()
        } else {
            let mode: DemoReleaseService.Mode
            if arguments.contains("--demo-empty") {
                mode = .empty
            } else if arguments.contains("--demo-error") {
                mode = .failure
            } else if arguments.contains("--demo-retry") {
                mode = .failOnce
            } else if arguments.contains("--demo-detail-missing") {
                mode = .missingDetail
            } else {
                mode = .success
            }
            service = DemoReleaseService(mode: mode)
        }
        #else
        service = Self.makeLiveService()
        #endif
    }

    var body: some Scene {
        WindowGroup {
            FeedView(service: service)
        }
    }

    private static func makeLiveService() -> APIClient {
        do {
            return APIClient(baseURL: try AppConfiguration.apiBaseURL())
        } catch {
            preconditionFailure("AppConfiguration.publicHost를 실제 공개 호스트로 설정하세요.")
        }
    }
}
```

이 `preconditionFailure`는 개발자가 공개 호스트를 설정하지 않은 경우를 찾기 위한 것이다. 실행 중 네트워크 실패·404·502는 화면 오류로 처리되며 여기로 오지 않는다. 배포 가능한 설정 관리로 확장할 때 Debug·Release 주소 검증을 별도 점검한다.

| 실행 환경 | 데이터 공급자 |
|---|---|
| Debug, 인자 없음 | 가짜 서비스 |
| Debug, `--demo-*` | 선택한 가짜 상태 |
| Debug, `--live-api`, 테스트 아님 | 실제 APIClient |
| Debug, `--ui-testing` | 항상 가짜 서비스 |
| Release | 실제 APIClient, 데모 코드는 제외 |

### 12.4 자동 테스트의 실행 인자 분리

실제 API 확인 전에 **Test 동작은 계속 Debug**로 둔다.

1. Edit Scheme → Test의 Arguments에서 Run의 인자·환경을 그대로 사용하는 옵션이 있다면 해제한다.
2. Test 동작의 인자에는 `--ui-testing`을 지정하고 `--live-api`는 넣지 않는다.
3. Test Plan을 사용한다면 해당 계획의 Configurations/Arguments 설정에서 같은 의도를 적용한다.
4. `⌘U`로 단위·UI 테스트를 실행한다. 앱이 열리더라도 데모 데이터를 사용해야 한다.

UI 테스트는 코드에서도 `launchArguments`를 지정한다. 환경 변수 감지는 보조 장치이며, 테스트 실행 인자를 명시적으로 분리하는 절차를 생략하지 않는다.

### 12.5 실제 연결 실행

1. Run → Arguments에서 모든 데모 인자를 해제한다.
2. **Run에만** `--live-api`를 추가하고 체크한다.
3. Run의 `--ui-testing`이 켜져 있지 않은지 확인한다.
4. `⌘B`, `⌘R`을 실행한다.
5. 연습 음반 대신 서버의 공개 일정 또는 정상 빈 화면이 나오는지 확인한다.
6. 공개 일정이 있으면 두 정렬, 당겨 새로고침, 상세, 실제 판매처 원문 링크를 확인한다.
7. Run의 `--live-api`를 해제하고 재실행하면 연습 음반으로 돌아오는지 확인한다.
8. 다시 `⌘U`를 실행해 자동 테스트가 서버 상태와 무관하게 유지되는지 확인한다.

실제 서버의 상태는 문서만으로 보장되지 않는다. 502 또는 연결 실패라면 먼저 브라우저에서 같은 공개 피드 주소를 확인한다. 서버 재시작·재배포·DB 작업은 이 앱 실습의 자동 복구 절차가 아니다.

**완료 확인**

- [ ] 브라우저에서 공개 피드 JSON을 확인했다.
- [ ] `--live-api`로 실제 공개 피드 또는 정상 빈 화면을 확인했다.
- [ ] 공개 일정이 있는 경우 상세와 판매처 링크를 확인했다.
- [ ] 실제 목록이 비어 있으면 실제 상세 검증은 미완료로 기록했다.
- [ ] 인자를 끄면 데모로 돌아오며 자동 테스트는 계속 가짜 데이터를 쓴다.

막히면: 여전히 연습 음반이 나오면 Run의 `--live-api`와 `--ui-testing` 상태를 확인한다. HTML이 오면 `/api/mobile` 접두사와 실제 공개 URL을 확인한다. 이 피드는 cursor가 없으므로 무한 스크롤을 덧붙이지 않는다.

<a id="step-13"></a>
## 13. 뼈대 마무리와 다음 작업 준비

### 13.1 사용하지 않는 기본 화면 정리

전체 검색 `⇧⌘F`로 `ContentView`를 찾는다. 최종 OROTApp에서 참조하지 않는 것을 확인한 뒤 이 실습에서 사용하던 `apps/ios/OROT/ContentView.swift`만 제거한다. 아직 9장의 임시 진입점을 사용한다면 먼저 12장의 교체를 완료한다.

`Assets.xcassets`에는 현재 기본 색상만 있다. 배포용 앱 아이콘은 후속 작업이다. Info.plist는 현재 `GENERATE_INFOPLIST_FILE = YES`이므로 파일이 안 보인다는 이유로 별도 생성하지 않는다.

### 13.2 최종 파일 구조와 책임

```text
apps/ios/
├── OROT.xcodeproj/
├── OROT/
│   ├── App/
│   │   ├── OROTApp.swift
│   │   └── PreviewSupport/
│   │       ├── SampleData.swift
│   │       └── DemoReleaseService.swift
│   ├── Core/
│   │   ├── Models/
│   │   │   └── ReleaseDTO.swift
│   │   └── Networking/
│   │       ├── ReleaseService.swift
│   │       ├── APIClient.swift
│   │       └── AppConfiguration.swift
│   ├── Features/
│   │   ├── Feed/
│   │   │   ├── FeedModel.swift
│   │   │   └── FeedView.swift
│   │   └── ReleaseDetail/
│   │       └── ReleaseDetailView.swift
│   └── Resources/
│       └── Assets.xcassets/
├── OROTTests/
│   ├── Models/ReleaseDTOTests.swift
│   ├── Networking/APIClientTests.swift
│   └── Features/FeedModelTests.swift
└── OROTUITests/
    └── FeedFlowTests.swift
```

| 파일·위치 | 책임 |
|---|---|
| OROTApp | 어떤 서비스를 사용할지 결정하고 첫 화면 열기 |
| ReleaseDTO | 서버 데이터의 모양 |
| ReleaseService | 실제·가짜 서비스가 지킬 함수 계약 |
| APIClient | URL·HTTP·JSON·공개 응답 검증 |
| AppConfiguration | 공개 호스트 설정 |
| FeedModel | 피드 결과·로딩·오류·요청 경쟁 처리 |
| FeedView | 정렬 선택·목록 표시·화면 이동 |
| ReleaseDetailView | 상세 조회·오류·판매처 링크 |
| PreviewSupport | Debug 전용 합성 데이터·가짜 상태 |
| OROTTests / OROTUITests | 데이터·통신·모델 / 사용자 동선 검증 |

파일 배치는 다음 기준으로 확장한다.

- 특정 화면에만 쓰는 코드는 `Features/그화면/`에 둔다.
- 피드와 상세가 함께 쓰는 날짜·가격 표시는 `Core/Formatting/`에 둔다.
- 여러 화면에 반복되는 모양은 `DesignSystem/Components/`에 둔다.
- 캐시 기능을 실제로 만들 때 `Core/Persistence/`를 추가한다.
- 상세 상태가 복잡해지면 `ReleaseDetailModel`을 추출하고 FeedModel처럼 테스트한다.

현재 크기에서는 별도 Swift Package·범용 Repository 계층을 먼저 만들 필요가 없다. 화면에서 `ReleaseService`를 받는 경계부터 유지한다.

### 13.3 Debug 테스트와 Release 빌드 구분

1. Run을 Debug, 데모 모드로 두고 기본 동선을 한 번 확인한다.
2. Test를 Debug와 테스트 인자로 두고 `⌘U`를 실행한다.
3. 통과한 테스트를 기록한다. 이 책의 템플릿을 정리했다면 단위 테스트 16개, UI 테스트 4개다.
4. Run → Info의 Build Configuration을 잠시 Release로 바꾸고 `⌘B`를 실행한다.
5. Release에서도 컴파일되는지 확인한다. 이 단계는 Archive나 배포가 아니다.
6. 다시 Run을 Debug로 복원한다. Test는 계속 Debug로 유지한다.

Release에는 SampleData·DemoReleaseService가 없으므로 앱에서 이 타입을 무조건 참조하면 컴파일 오류가 난다. 모든 데모 참조가 `#if DEBUG` 안에 있는지 확인한다. Release를 실제 실행하려면 12장의 공개 호스트가 설정되어 있어야 한다.

### 13.4 Git에 남길 내용 확인

저장소 루트에서 변경을 확인한다.

```sh
git status --short
git diff -- .gitignore
git status --short --untracked-files=all apps/ios
```

새 파일은 아직 미추적이면 일반 `git diff`에 내용이 나오지 않는다. 파일 자체와 미추적 목록도 함께 확인한다. 이 책 작성 시 `.gitignore`에는 이미 아래 규칙이 추가되어 있었다. 현재 파일을 확인하고, 없을 때만 추가한다.

```gitignore
# Xcode
xcuserdata/
*.xcuserstate
DerivedData/
```

소스·리소스·`project.pbxproj`·공유 scheme·사용 중인 Test Plan은 버전 관리 대상이다. 개인 Xcode 상태·빌드 결과물·비밀은 제외한다. `*.xcodeproj` 전체를 무시하지 않는다.

다른 Mac에서도 같은 실행·테스트 대상을 사용하려면 Product → Scheme → Manage Schemes에서 OROT의 Shared를 체크하고 생성된 공유 scheme을 확인한다. 기존 개인 scheme이 있다고 프로젝트가 잘못된 것은 아니지만 공유 설정은 협업과 재현에 도움이 된다.

이 실습 때문에 기존 Expo 폴더나 서버 코드를 정리하지 않는다. 현재까지 만들어진 iOS 뼈대의 변경만 검토한다.

### 13.5 실습 완료 기록

각 항목은 실제 확인 후 체크한다. 실패·미검증을 성공으로 기록하지 않는다.

- [ ] 개발 Mac / Xcode 버전 / Simulator 모델과 OS를 기록했다.
- [ ] 기본 화면과 폴더 이동 후 실행을 확인했다.
- [ ] DTO 네 테스트, APIClient 일곱 테스트, FeedModel 다섯 테스트가 통과했다.
- [ ] UI 네 테스트가 통과했다.
- [ ] 빈 목록·오류·재시도·상세 404를 데모에서 확인했다.
- [ ] 실제 공개 API의 피드를 읽었다.
- [ ] 실제 공개 일정의 상세·판매처 링크를 확인했다. 또는 일정이 없어 미검증으로 남겼다.
- [ ] Debug 자동 테스트와 Release 빌드를 구분해 확인했다.
- [ ] 큰 글자·다크 모드에서 기본 화면이 읽히는지 수동으로 확인했다.
- [ ] Git 변경에 개인 Xcode 상태·비밀이 섞이지 않았다.

```text
검증일:
개발 Mac:
Xcode:
Simulator 모델 / iOS:
Debug 빌드:
단위 테스트:
UI 테스트:
Release 빌드:
실제 공개 피드:
실제 상세 / 판매처 링크:
실기기 검증: 미실시 / 실시한 내용
남은 오류와 재현 순서:
```

여기까지 완료하면 앱 시작점, 데이터 계약, 통신, 상태 모델, 화면 이동, 오류 처리, 테스트가 연결된 **읽기 앱의 뼈대**를 갖춘 것이다. 날짜 원문 표시·캐시 부재·푸시 부재 때문에 출시 완료 상태는 아니다.

## 14. 다음 기능은 어떤 순서로 붙일까

기존 [개발 가이드](IOS_NATIVE_DEVELOPMENT_GUIDE.ko.md)를 다음 순서로 이어 읽는다. 각 작업에서도 파일 하나 또는 작은 기능 하나를 만든 뒤 테스트한다.

| 순서 | 다음 작업 | 먼저 만들 파일·검증 |
|---|---|---|
| 1 | KST 날짜·상태·가격 표시 | `Core/Formatting/ScheduleFormatter.swift`; 날짜 경계·소수 초·TBA·ON_SALE·품절 시까지 테스트 |
| 2 | 표지·테마·접근성 | `DesignSystem/Theme.swift`, 반복되는 컴포넌트; 큰 글자·VoiceOver·다크 모드 확인 |
| 3 | 마지막 성공 데이터 보관 | `Core/Persistence/FeedCache.swift`; 손상 파일·host/정렬 분리·404 무효화 테스트 |
| 4 | 설정 화면 | `Features/Settings/`; 실제 기능의 상태와 오류를 먼저 정의 |
| 5 | 실기기 읽기 검증 | 서명·설치 후 Wi-Fi/셀룰러·외부 링크 확인 |
| 6 | 네이티브 푸시 | 서버 등록 인증·토큰·APNs sender 계약을 먼저 결정한 뒤 가이드 13장 |
| 7 | 배포 | 앱 아이콘·개인정보·Archive·TestFlight를 가이드 15장으로 검증 |

현재 APIClient는 429를 설명하지만 `Retry-After` 기반 대기, 오프라인 보관, 자동 재시도는 구현하지 않는다. 피드에는 cursor가 없어 무한 스크롤도 제공하지 않는다. 기존 Web Push 동작과 Swift 네이티브 푸시는 별개다.

## 15. 오류가 났을 때 돌아갈 위치

| 증상 | 먼저 확인할 것 | 돌아갈 단계 |
|---|---|---|
| Simulator가 없음 | 런타임 설치, 가상 기기 생성, 실행 대상 | 1 |
| 새 코드를 넣었는데 예전 화면 | 선택한 로컬 프로젝트, 진입점, 저장·재실행 | 2·9 |
| `@main` 중복 | MyApp과 OROTApp을 둘 다 남겼는지 | 3 |
| 타입을 찾을 수 없음 | 파일 위치·target membership·앞 단계 누락 | 해당 파일 작성 단계 |
| 테스트가 0개 | Test target, scheme/Test Plan, `@Test` | 4 |
| `SampleData`를 찾을 수 없음 | Debug 구성, 앱 target 포함 여부 | 5 |
| 디코딩 오류 | JSON 필수 필드·CodingKeys·null | 5·6 |
| actor isolation 오류 | Swift 6·MainActor 설정과 예제의 `@MainActor` | 1·4 |
| 테스트가 무한 대기 | controlled 서비스의 요청·응답 짝 | 8 |
| 빈 목록인데 오류가 없음 | 정상 빈 응답 또는 `--demo-empty` | 9·12 |
| 재시도해도 항상 실패 | `--demo-error`와 `--demo-retry` 구분 | 9 |
| 실제 API를 켰는데 연습 데이터 | Run 인자, 테스트 표식, 재실행 | 12 |
| 호스트 설정 오류로 시작 시 중단 | `YOUR-PUBLIC-HOST` 교체, 호스트만 입력 | 12 |
| HTML·502 응답 | 공개 API 경로·서버 프록시 상태 | 12 |
| Release만 컴파일 실패 | `#if DEBUG` 밖에서 데모 타입 사용 | 13 |
| 날짜가 9시간 또는 하루 달라 보임 | UTC 원문과 KST 표시, 날짜 전용 필드 구분 | 기존 가이드 10장 |

컴파일 오류는 `⌘5`에서 가장 먼저 발생한 것부터 해결한다. 실행 중 오류는 어떤 인자로 어떤 화면을 열었는지 기록한다. 문제를 줄이기 위해 DB를 초기화하거나 Docker 볼륨을 지울 필요는 없다.

## 16. 참고와 이 문서의 검증 범위

현재 계약은 다음 소스와 대조했다.

- [공개 Release 응답](../apps/api/src/orot_api/schemas/release.py): nullable 필드·정수 원화·공개 응답.
- [피드 응답과 정렬](../apps/api/src/orot_api/routers/feed.py): `items`, `generated_at`, 발매당 한 줄·두 정렬·cursor 없음.
- [공개 모바일 프록시](../apps/web/lib/mobile-read.ts): 허용된 GET 경로·쿼리·내부 서버 경계.
- [OpenAPI 스냅샷](api/openapi.json): API 응답 스키마.
- [기존 iOS 개발 가이드](IOS_NATIVE_DEVELOPMENT_GUIDE.ko.md): 앱 구조·동시성 설정·후속 표시·캐시·푸시·배포.

작성 시 정적 점검에서는 단계 링크 13개와 로컬 문서·소스 링크 10개, 코드 블록의 구분자, 전체 파일 예제 17개의 선행 타입 참조를 확인했다. 합성 JSON은 OpenAPI의 필수 필드·타입·enum 값과 대조했다. 단위 테스트 16개·UI 테스트 4개는 **문서에 작성된 테스트 수**이며, 실행해 통과한 수가 아니다.

Apple 공식 자료는 해당 설명 옆에 연결했다. 메뉴·지원 버전은 설치된 Xcode에서 최종 확인한다. 문서 작성 검증은 Markdown 구조·링크·예제의 참조 순서·API 계약에 대한 정적 검토다. **이 책의 Swift 예제에 대한 컴파일, 단위/UI 테스트, Simulator·실기기 실행, 실제 서버 연결은 독자가 체크포인트에서 실행해 확인한다.** 문서 검토만을 위해 Python·웹 서비스를 시작하거나 재빌드하지 않는다.
