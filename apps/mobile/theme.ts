/** OROT 모바일 디자인 설정. 사용 방법: THEME.md
 * Node에서 읽는 app.config.ts도 이 파일을 사용하므로 runtime import는 두지 않습니다.
 */
import type { ImageSourcePropType, TextStyle } from "react-native";

// undefined는 iOS/Android의 기본 시스템 글꼴입니다.
// 로컬 폰트를 쓸 때 files와 각 굵기의 실제 font family 이름을 함께 설정하세요.
const fonts = {
  files: [] as string[],
  families: {
    regular: undefined as string | undefined,
    semibold: undefined as string | undefined,
    bold: undefined as string | undefined,
    extraBold: undefined as string | undefined,
  },
};

function textStyle(
  size: number,
  face: keyof typeof fonts.families = "regular",
  lineHeight?: number,
): Pick<TextStyle, "fontFamily" | "fontSize" | "fontWeight" | "lineHeight"> {
  const family = fonts.families[face];
  const weights = {
    regular: "400",
    semibold: "600",
    bold: "700",
    extraBold: "800",
  } as const;
  return {
    fontFamily: family,
    fontSize: size,
    // 별도 굵기 파일의 family를 선택했다면 시스템 합성 굵기를 중복 적용하지 않습니다.
    fontWeight: family ? "normal" : weights[face],
    ...(lineHeight === undefined ? {} : { lineHeight }),
  };
}

const light = {
  background: "#F7F4ED",
  surface: "#FFFFFF",
  text: "#222820",
  secondary: "#62675D",
  border: "#DEDCD3",
  accent: "#A44420",
  tint: "#F5E5D9",
  recordCover: "#516D64",
  recordDisc: "#242723",
  recordGroove: "#61635C",
  recordHole: "#F7F4ED",
};
export type Palette = typeof light;
const dark: Palette = {
  background: "#171C18",
  surface: "#242B25",
  text: "#F5F2E9",
  secondary: "#BCC4B8",
  border: "#3E473D",
  accent: "#F1AA80",
  tint: "#413025",
  recordCover: "#516D64",
  recordDisc: "#242723",
  recordGroove: "#61635C",
  recordHole: "#F7F4ED",
};

export const theme = {
  colors: { light, dark },
  fonts,
  typography: {
    brand: { ...textStyle(27, "extraBold"), letterSpacing: 4 },
    hero: textStyle(32, "bold", 43),
    screenTitle: textStyle(30, "bold"),
    detailTitle: textStyle(29, "bold"),
    cardTitle: textStyle(18, "bold"),
    sectionTitle: textStyle(18, "semibold"),
    value: textStyle(17, "semibold"),
    body: textStyle(15, "regular", 25),
    intro: textStyle(14, "regular", 23),
    button: textStyle(14, "semibold"),
    label: textStyle(13),
    caption: textStyle(12),
    captionStrong: textStyle(12, "semibold"),
    // 탭 기호는 사용자 지정 글꼴의 글리프 범위에 의존하지 않도록 시스템 폰트 사용.
    tabIcon: {
      fontFamily: undefined,
      fontSize: 22,
      fontWeight: "400",
    } as TextStyle,
  },
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, section: 48 },
  radius: {
    small: 8,
    notice: 10,
    button: 12,
    card: 16,
    cover: 18,
    pill: 24,
    circle: 999,
  },
  layout: { feedPadding: 22, screenPadding: 24, contentBottom: 48 },
  images: {
    appIcon: "./assets/icon.png",
    // 커버가 없거나 로드 실패한 경우 사용. 미설정 시 기존 레코드 그래픽을 표시합니다.
    // 예: () => require("./assets/cover-placeholder.png")
    // 함수 내부에 정적 require를 두어 Expo config가 PNG를 Node로 읽지 않게 합니다.
    recordPlaceholder: (): ImageSourcePropType | undefined => undefined,
  },
  recordArt: {
    thumbnailWidth: 72,
    thumbnailHeight: 80,
    detailHeight: 230,
    disc: 60,
    groove: 46,
    label: 22,
    hole: 5,
  },
  icons: { feed: "◉", settings: "☷" },
};
export type TextVariant = keyof typeof theme.typography;
