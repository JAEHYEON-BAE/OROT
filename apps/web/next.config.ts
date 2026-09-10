import type { NextConfig } from "next";

// 콘텐츠 보안 정책 (T-121).
//
// `script-src` 에 'unsafe-inline' 이 남아 있다. Next 가 하이드레이션 데이터를
// 인라인 스크립트로 넣기 때문인데, 없애려면 요청마다 nonce 를 발급해야 한다.
// **그래도 의미가 있다** — 외부 스크립트 로드를 막아 XSS 페이로드의 주된 통로를 끊고,
// frame-ancestors·object-src·base-uri 로 클릭재킹과 base 태그 주입을 막는다.
//
// `img-src` 에 https: 를 연 것은 커버 이미지가 판매처 도메인을 가리키기 때문이다.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https:",
  "font-src 'self'",
  "connect-src 'self'",
  "form-action 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  // 스택과 버전을 광고할 이유가 없다.
  poweredByHeader: false,
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
          { key: "Content-Security-Policy", value: CSP },
          // 운영 빌드에서만. 개발은 http://localhost 로 접근한다.
          //
          // **`includeSubDomains` 와 `preload` 를 넣지 않는다.** 이 앱은 공용 도메인의
          // 하위 도메인(`<호스트>.<테일넷>.ts.net`)에 있어서, 그 지시자를 켜면
          // 같은 도메인을 쓰는 다른 기기까지 강제하게 된다.
          ...(process.env.NODE_ENV === "production"
            ? [{ key: "Strict-Transport-Security", value: "max-age=31536000" }]
            : []),
        ],
      },
    ];
  },
};

export default nextConfig;
