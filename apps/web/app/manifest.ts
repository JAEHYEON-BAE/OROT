import type { MetadataRoute } from "next";

/**
 * 웹 앱 매니페스트 (T-117).
 *
 * **iOS 는 이것이 있어야 홈 화면에 추가할 수 있고, 홈 화면에 추가해야
 * 알림 권한을 요청할 수 있다** (ADR-0006 에서 감수하기로 한 마찰).
 * 즉 이 파일은 아이폰 사용자에게 푸시의 전제 조건이다.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "OROT — 바이닐 발매·예약 일정",
    short_name: "OROT",
    description:
      "국내 바이닐(LP) 신규 발매와 예약판매 일정을 한곳에서. 한정반 예약 시작을 놓치지 마세요.",
    // 알림을 눌러 들어온 뒤에도 홈으로 돌아갈 수 있도록 루트로 둔다.
    start_url: "/",
    scope: "/",
    display: "standalone",
    lang: "ko",
    background_color: "#ffffff",
    theme_color: "#0a0a0a",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // maskable 은 OS 가 원·사각형 등으로 잘라 낸다. 안전 영역 안에 그려 둔 별도 파일이다.
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "다가오는 일정", url: "/calendar" },
      { name: "구독 설정", url: "/subscribe" },
    ],
  };
}
