import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "OROT — 바이닐 발매·예약 일정",
  description:
    "국내 바이닐(LP) 신규 발매와 예약판매 일정을 한곳에서. 한정반 예약 시작을 놓치지 마세요.",
  // app/manifest.ts 가 /manifest.webmanifest 로 제공된다.
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    // iOS 홈 화면에서 주소창 없이 실행된다. 홈 화면 추가는 아이폰에서
    // 알림을 받기 위한 전제 조건이다 (ADR-0006).
    capable: true,
    title: "OROT",
    statusBarStyle: "default",
  },
  // iOS 는 매니페스트의 icons 를 홈 화면에 쓰지 않는다. 이 링크가 따로 필요하다.
  icons: { apple: "/apple-touch-icon.png" },
};

export const viewport: Viewport = {
  themeColor: "#0a0a0a",
  // 홈 화면에서 실행될 때 브라우저 UI 없이 화면을 꽉 채운다.
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
        <header className="border-b border-neutral-200 dark:border-neutral-800">
          <nav className="mx-auto flex max-w-3xl items-center gap-5 px-4 py-4">
            <Link href="/" className="font-semibold tracking-tight">
              OROT
            </Link>
            <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100">
              피드
            </Link>
            <Link href="/calendar" className="text-sm text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100">
              캘린더
            </Link>
            <span className="ml-auto flex gap-3 text-sm">
              <a href="/subscribe" className="text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100">
                구독
              </a>
            </span>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t border-neutral-200 px-4 py-6 text-center text-xs text-neutral-500 dark:border-neutral-800">
          일정은 운영자가 직접 등록합니다. 구매는 각 판매처에서 진행하세요.
        </footer>
      </body>
    </html>
  );
}
