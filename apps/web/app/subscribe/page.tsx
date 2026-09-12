import PushToggle from "./PushToggle";

export const metadata = { title: "구독 — OROT" };
export const dynamic = "force-dynamic";

export default function SubscribePage() {
  // 브라우저에 보여 줄 주소는 컨테이너 내부 주소가 아니라 공개 주소여야 한다.
  const publicBase = (process.env.PUBLIC_WEB_URL ?? "http://localhost:3000").replace(/\/$/, "");
  const ics = `${publicBase}/v1/releases.ics`;
  const rss = `${publicBase}/v1/feed.rss`;

  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">구독</h1>
      <p className="mt-1 text-sm text-neutral-500">
        계정 없이 구독할 수 있습니다. 캘린더 앱은 예약 시작 <strong>30분 전</strong>에 알려 줍니다.
      </p>

      <PushToggle />

      <section className="mt-7">
        <h2 className="font-medium">캘린더 (iCalendar)</h2>
        <code className="mt-2 block overflow-x-auto rounded bg-neutral-100 px-3 py-2 text-xs dark:bg-neutral-900">
          {ics}
        </code>
        <ul className="mt-3 space-y-1 text-sm text-neutral-600 dark:text-neutral-400">
          <li>
            <strong>iPhone</strong> — 설정 → 앱 → 캘린더 → 계정 → 계정 추가 → 기타 → 구독 캘린더 추가
          </li>
          <li>
            <strong>macOS</strong> — 캘린더 → 파일 → 새로운 캘린더 구독
          </li>
          <li>
            <strong>Google</strong> — 다른 캘린더 + → URL로 만들기
          </li>
        </ul>
      </section>

      <section className="mt-7">
        <h2 className="font-medium">RSS</h2>
        <code className="mt-2 block overflow-x-auto rounded bg-neutral-100 px-3 py-2 text-xs dark:bg-neutral-900">
          {rss}
        </code>
        <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
          새 일정이 등록되면 리더에 올라옵니다.
        </p>
      </section>

      <section className="mt-7 border-t border-neutral-200 pt-5 text-sm text-neutral-600 dark:border-neutral-800 dark:text-neutral-400">
        <p>
          <strong>푸시와 캘린더를 함께 쓰시길 권합니다.</strong> 캘린더 앱은 구독한 주소를
          하루에 한두 번만 다시 읽어서(구글은 12~24시간), 오늘 급히 등록된 일정이나 바뀐
          시각을 놓칩니다. 푸시는 그 공백을 메웁니다.
        </p>
      </section>
    </>
  );
}
