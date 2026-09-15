# OROT 모바일 개발 앱

T-033 실제 서비스 연결 단계입니다. 기본적으로 아래 공개 API를 사용합니다.

`https://jaehyeonui-macmini.tail598a5f.ts.net/api/mobile`

웹과 동일한 공개 일정의 피드·상세·커버·판매처 링크를 읽습니다. 로딩·오류·재시도·당겨서 새로고침을 지원하며 실패 시 mock 데이터로 대체하지 않습니다. 모바일 푸시 등록은 아직 제공하지 않습니다.

## 개발 환경

- Node **22.23.2** (`.nvmrc`, `.node-version`), npm, Xcode **26.2**, CocoaPods **1.17.0**.
- Expo **55.0.31**, React Native **0.83.10**, React **19.2.0**. 정확한 전이 버전은 package-lock.json을 사용합니다.
- 현재 Xcode에 맞춰 SDK 55를 선택했습니다. SDK 57은 Xcode 26.4 이상이 필요하므로 Xcode 업데이트 후 SDK 업그레이드와 회귀 검증을 진행합니다.
- 앱 ID `com.orot.mobile.dev`, scheme `orot-dev`는 로컬 개발용입니다. production ID·서명·EAS 프로젝트는 아직 없습니다.
- `app.config.ts`는 production EAS profile을 거부합니다. 서명·푸시 검증 전 스토어 배포를 막도록 하는 제한입니다.

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

### 편집기에서 테스트 파일에 붉은 밑줄이 나타나는 경우

프로젝트 TypeScript와 VS Code 내장 TypeScript 버전이 다를 수 있습니다. TypeScript 6부터는 전역 타입 패키지를 자동으로 포함하지 않으므로, `tsconfig.json`의 `compilerOptions.types`에 `jest`, `node`, `react`를 명시합니다. 이는 `test`·`expect`·`jest`·`global` 및 테스트 matcher의 타입을 인식하도록 하는 설정입니다. 테스트 파일도 `npm run typecheck`의 검사 대상입니다.

의존성을 처음 설치할 때는 `npm ci`를 실행합니다. 설정 변경 후에도 이전 오류가 남으면 VS Code 명령 팔레트(`Cmd+Shift+P`)에서 **TypeScript: Restart TS Server**를 실행하세요. 이 변경에는 앱 재설치나 native 재빌드가 필요하지 않습니다.

## API 설정과 타입

기본 URL은 `src/lib/api/client.ts`에 있습니다. 다른 HTTPS 서버를 사용하려면 `.env.example`을 참고해 앱 디렉터리의 `.env.local`에 `EXPO_PUBLIC_API_BASE_URL`을 설정하고 Metro를 재시작합니다. 주소만 공개 설정이며 서버의 `.env`·관리자 키는 넣지 않습니다.

`npm run generate:api`는 저장소 `docs/api/openapi.json`에서 타입만 생성합니다. 생성 타입은 번들 실행 코드가 아니며, 실제 응답은 별도 런타임 검증을 거칩니다. API 변경 시 OpenAPI snapshot과 타입을 함께 갱신하세요.

[실제 서비스 연결 검증](../../docs/mobile-validation/T-033-live-api.ko.md) · [첫 단계 빌드 기록](../../docs/mobile-validation/T-033-scaffold.ko.md)

다음 단계는 iPhone 14 실기기 조회 검증과 모바일 푸시입니다. 웹 PWA의 알림 구독을 앱에 그대로 사용할 수는 없습니다.

## 공통 테마

글꼴·라이트/다크 팔레트·이미지·간격은 [`theme.ts`](theme.ts)에서 관리합니다. [테마 편집 안내](THEME.md)에 변경 예시와 재빌드가 필요한 항목을 정리했습니다.
