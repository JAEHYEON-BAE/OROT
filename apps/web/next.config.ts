import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 개발 서버는 기본적으로 localhost 외의 출처를 막는다. 실제 기기 시험용
  // 터널(HTTPS)에서 열려면 그 도메인을 허용해야 한다. **개발에서만 적용된다.**
  // iOS 는 유효한 인증서 없이는 서비스워커를 등록하지 않아 터널이 불가피하다.
  allowedDevOrigins: ["*.trycloudflare.com"],
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          // **서비스워커를 캐시하면 안 된다.** 캐시된 낡은 워커가 남으면 알림 로직
          // 수정이 며칠씩 반영되지 않고, 그 사이 사용자는 구독 중인데 알림만
          // 이상하게 오는 상태가 된다. 원인을 추적하기 가장 어려운 종류의 버그다.
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
