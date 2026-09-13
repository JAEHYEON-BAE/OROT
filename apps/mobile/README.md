# OROT 모바일 개발 앱

T-033 첫 단계: Expo Router + React Native + TypeScript mock 화면입니다.
목록 정렬, 상세 이동, 없는 상세 안내, 설정 탭을 제공합니다. 모든 음반은 가상 예시이며 서버 요청·기기 등록·실제 푸시는 없습니다.

## 개발 환경

- Node **22.23.2** (`.nvmrc`, `.node-version`), npm, Xcode **26.2**, CocoaPods **1.17.0**.
- Expo **55.0.31**, React Native **0.83.10**, React **19.2.0**. 정확한 전이 버전은 package-lock.json을 사용합니다.
- 현재 Xcode에 맞춰 SDK 55를 선택했습니다. SDK 57은 Xcode 26.4 이상이 필요하므로 Xcode 업데이트 후 SDK 업그레이드와 회귀 검증을 진행합니다.
- 앱 ID `com.orot.mobile.dev`, scheme `orot-dev`는 로컬 개발용입니다. production ID·서명·EAS 프로젝트는 아직 없습니다.
- `app.config.ts`는 production EAS profile을 거부합니다. 이 예시 앱을 배포하지 않도록 하는 제한입니다.

## 실행

Node 22가 활성화되어 있다면:

```sh
cd /Users/jaehyeon/PersonalProjects/OROT/apps/mobile
npm ci
npm run ios -- --device
```

선택 목록에서 Simulator를 선택합니다. 개발용 `OROT iPhone 14` Simulator가 준비되어 있습니다. 실제 iPhone 설치는 USB 신뢰, Developer Mode, Xcode 서명 Team을 추가로 준비해야 하며 아직 검증하지 않았습니다.

이미 설치된 Simulator 앱은 다음으로 재실행합니다.

```sh
npm run start:simulator
```

이 명령은 로컬 Metro만 시작하고 iOS 앱을 엽니다. IPv6 localhost만 listen하면서 IPv4 번들 URL을 제공하는 현상을 피하기 위해 IPv4 DNS 우선순위를 지정했습니다. 기존 Metro가 8081을 점유하면 해당 개발 터미널에서 Ctrl+C로 종료한 뒤 실행하세요. 첫 실행 시 Expo 안내의 Continue를 누르면 앱 화면이 나타납니다.

현재 Mac의 기본 Node가 25인 경우, 전역 설정을 바꾸지 않는 실행 방법:

```sh
npm exec --yes --package=node@22.23.2 -- npm ci
npm exec --yes --package=node@22.23.2 -- npm run start:simulator
```

처음부터 native 컴파일이 필요하다면 마지막 줄 대신 아래를 사용합니다.

```sh
npm exec --yes --package=node@22.23.2 -- npm run ios -- --device
```

실기기 개발에서는 `npm start`로 LAN Metro를 사용합니다. `start:simulator`의 localhost는 실기기용 주소가 아닙니다. 앱 최초 설치 후 코드만 바꾸면 Fast Refresh로 반영됩니다. native 모듈·plugin 설정을 변경하면 재빌드합니다. `ios/`와 `android/`는 생성 파일이며 Git에서 제외합니다.

## 검사

```sh
npm run check
npx expo install --check
npx expo-doctor
```

Node 25 환경에서는 각 명령을 Node 22 npm exec로 실행합니다. doctor는 `npm exec --yes --package=node@22.23.2 --package=expo-doctor -- expo-doctor`로 실행할 수 있습니다. 테스트는 네트워크를 금지하고 Router 이동·잘못된 ID·KST 날짜 경계를 검증합니다.

## 다음 단계

[모바일 블루프린트](../../docs/MOBILE_BLUEPRINT.ko.md)의 T-033 공개 읽기 프록시와 API 타입 생성·실제 데이터 연결입니다. 현재 앱은 서버 .env 또는 공개 API 주소를 요구하지 않습니다. 서버 .env를 복사하지 마세요.

[검증 기록과 남은 경고](../../docs/mobile-validation/T-033-scaffold.ko.md)를 참고하세요. 이번 구현은 T-033 전체 또는 모바일 MVP 완료가 아닙니다.
