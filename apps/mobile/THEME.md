# OROT 모바일 테마 편집

공통 디자인 값은 **`apps/mobile/theme.ts`** 한 곳에서 관리합니다. 이미지·폰트 파일은 `assets/`에 두고 테마에서 참조합니다. 기본 시스템 글꼴과 기존 팔레트를 유지했으며 새 폰트·이미지를 내려받지는 않았습니다.

## 바꾸는 위치

| 설정 | 역할 |
|---|---|
| `colors.light` / `colors.dark` | 배경, 카드, 글자, 보조 글자, 테두리, 강조색, 레코드 그래픽 색상 |
| `fonts.files` / `fonts.families` | 앱에 포함할 폰트 파일과 굵기별 글꼴 이름 |
| `typography` | 제목·본문·버튼·설명 등의 글자 크기, 굵기, 행간 |
| `spacing` / `radius` / `layout` | 공통 간격·모서리·화면 좌우 여백 |
| `images.appIcon` | 홈 화면 앱 아이콘 파일 경로 |
| `images.recordPlaceholder` | 커버가 없거나 실패했을 때 표시할 공통 이미지 |
| `recordArt` | 커버 크기와 기본 레코드 그래픽 크기 |
| `icons` | 하단 메뉴 기호 |

테마에 모든 화면의 좌표를 넣지는 않습니다. 화면별 배치·데이터·문구는 해당 화면 파일에 남겨 두고, 여러 화면이 공유하는 디자인 값을 테마에서 관리합니다. 음반별 커버는 서버 데이터이므로 테마에 고정하지 않습니다.

## 색상과 글자 크기

예를 들어 강조색을 바꾸려면 theme.ts의 light와 dark에서 `accent`를 각각 수정합니다. dark는 어두운 배경에서도 읽기 쉬운 색을 선택합니다.

```ts
// light
accent: "#A44420",
// dark
accent: "#F1AA80",
```

목록 카드 제목은 `typography.cardTitle`, 메인 문구는 `typography.hero`, 상세 제목은 `typography.detailTitle`입니다. 예를 들어 `cardTitle: textStyle(18, "bold")`의 18을 바꾸면 해당 스타일을 쓰는 화면에 반영됩니다. 색상은 OS 라이트·다크 모드에 따라 자동 전환합니다.

개발 앱과 Metro가 켜져 있으면 저장 후 화면이 갱신됩니다. 공통 모듈 변경은 전체 새로고침으로 반영될 수도 있습니다. 업데이트가 보이지 않으면 Metro에서 `r`을 누르세요. 테마 수정을 위해 TestFlight에 올릴 필요는 없습니다.

## 글꼴 파일 추가

기본 `fonts.files`는 빈 배열이고 family는 undefined입니다. 따라서 현재는 iOS·Android의 시스템 글꼴을 사용합니다.

사용할 권한이 있는 정적 TTF/OTF 파일을 `apps/mobile/assets/fonts/`에 넣은 뒤 다음처럼 등록합니다. 아래 이름은 예시이며 실제 파일과 폰트 내부 이름으로 교체해야 합니다.

```ts
const fonts = {
  files: [
    "./assets/fonts/OROT-Regular.ttf",
    "./assets/fonts/OROT-SemiBold.ttf",
    "./assets/fonts/OROT-Bold.ttf",
    "./assets/fonts/OROT-ExtraBold.ttf",
  ],
  families: {
    regular: "OROT-Regular",
    semibold: "OROT-SemiBold",
    bold: "OROT-Bold",
    extraBold: "OROT-ExtraBold",
  },
};
```

`app.config.ts`가 이 목록으로 expo-font 플러그인을 구성합니다. **폰트 파일 추가·변경 후에는 native 앱 재빌드가 필요합니다.** iOS는 폰트 내부 family 이름, Android의 단순 파일 등록은 파일 이름을 사용하므로 두 이름이 맞는지 확인하세요. 미설정한 굵기는 시스템 글꼴을 사용합니다. 현재 모든 굵기는 시스템 기본값입니다. 실제 사용자 지정 폰트는 제공되지 않아 실기기 렌더링을 검증하지 않았습니다. [Expo SDK 55 글꼴 안내](https://docs.expo.dev/versions/v55.0.0/sdk/font/)

OS의 글자 확대 기능은 비활성화하지 않습니다. 폰트를 바꾼 뒤 큰 글자 설정과 한글·영문·숫자 줄바꿈을 확인하세요.

## 공통 이미지 바꾸기

앱 아이콘은 기존 `assets/icon.png`를 사용합니다. `images.appIcon`에서 다른 로컬 PNG 경로를 지정할 수 있습니다. 앱 아이콘은 native 설정이므로 재빌드해야 설치된 앱에 반영됩니다.

커버 대체 이미지는 파일을 추가한 후 다음과 같이 수정합니다.

```ts
images: {
  appIcon: "./assets/icon.png",
  recordPlaceholder: () => require("./assets/cover-placeholder.png"),
},
```

`require` 안에는 실제 경로 문자열을 직접 적습니다. `require(variable)`은 Metro가 정적으로 파일을 찾을 수 없어 사용하지 않습니다. 함수 안에 두는 이유는 같은 테마를 읽는 Expo 설정이 Node 환경에서 이미지 바이너리를 실행하지 않도록 하기 위해서입니다. [React Native 이미지 안내](https://reactnative.dev/docs/images)

커버는 **서버 이미지 → 테마 대체 이미지 → 기본 레코드 그래픽** 순서로 표시합니다. `recordPlaceholder`가 undefined를 반환하는 현재 설정에서는 바로 기본 그래픽으로 넘어갑니다. 새 대체 이미지는 Metro 번들에 포함되며 일반적으로 JS 새로고침으로 반영됩니다.

## 적용되는 화면과 사용 예

목록·상세·설정·로딩/오류·하단 탭·상단 헤더에 테마를 적용했습니다. `src/lib/theme.ts`는 OS 색상 모드에 맞는 팔레트를 반환하는 얇은 연결 모듈입니다. 디자인 값은 그 파일에 추가하지 않습니다.

```tsx
import { View } from "react-native";
import { ThemeText } from "@/components/theme-text";
import { theme, usePalette } from "@/lib/theme";

// 컴포넌트 내부
const colors = usePalette();
return (
  <View style={{ backgroundColor: colors.surface, padding: theme.spacing.lg }}>
    <ThemeText variant="cardTitle">앨범 제목</ThemeText>
    <ThemeText variant="caption" style={{ color: colors.secondary }}>
      예약 일정
    </ThemeText>
  </View>
);
```

`ThemeText`는 기본 본문 글꼴과 현재 모드의 글자색을 제공합니다. 기존 Text의 접근성 속성을 전달하고, 필요하면 style로 화면별 값을 추가할 수 있습니다. 새 화면에서도 색상 코드나 글자 크기를 직접 반복하기보다 테마를 참조하세요.

## 다시 빌드해야 하는 변경

| 변경 | 필요한 작업 |
|---|---|
| 화면의 팔레트·글자 크기·간격·대체 이미지 | 개발 앱 저장/새로고침 |
| 폰트 파일·앱 아이콘 | native 재빌드·재설치 |
| 앱 시작 화면 배경 | native 재빌드·재설치 |

시작 화면 배경은 `theme.colors.light.background`와 dark의 값을 사용합니다. 실행 중 화면 배경은 바로 바뀌지만 설치된 native 시작 화면은 재빌드 전까지 기존 색을 유지합니다. [Expo 시작 화면 안내](https://docs.expo.dev/versions/v55.0.0/sdk/splash-screen/)

재빌드할 때는 다음을 실행하고 원하는 Simulator/기기를 선택합니다.

```sh
cd /Users/jaehyeon/PersonalProjects/OROT/apps/mobile
npm exec --yes --package=node@22.23.2 -- npm run ios -- --device
```

## 검증 범위

테마 변경 후 모바일 lint·TypeScript·기존 동선과 테마 테스트를 실행합니다. 이미지 요청은 테스트에서 실제 전송하지 않습니다. 다크 모드 전환과 커버 실패 대체 경로를 자동 검사합니다. iOS·Android JavaScript 번들 생성은 native 컴파일이나 실기기 화면 검증을 대신하지 않습니다. T-034의 VoiceOver·큰 글자 실기기 확인은 후속입니다.


2026-09-14 구현 검증: 모바일 lint/typecheck 통과, 5 suites / 16 tests 통과, Expo doctor 20/20 통과, iOS·Android Hermes JavaScript 번들 생성 성공, Expo 설정의 테마 아이콘·시작 배경 해석 확인. 서버 회귀는 427 passed / 2 xfailed이며 기존 Starlette/httpx 경고 1개가 남아 있습니다. Simulator 실행·native 재빌드·실기기 시각 검증은 수행하지 않았습니다.
