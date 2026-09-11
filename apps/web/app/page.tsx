import Link from "next/link";
import { getFeed, type FeedItem } from "@/lib/api";
import { formatDate, formatDateTime, releaseLabel } from "@/lib/format";
import { feedDisplay } from "@/lib/feed-display";

// 예약 시각이 중요한 서비스라 정적 생성하지 않는다.
export const dynamic = "force-dynamic";

function ShopLinks({ item }: { item: FeedItem }) {
  if (item.release.links.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {item.release.links.map((link) => (
        <a
          key={link.id}
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded border border-neutral-300 px-2 py-0.5 text-xs hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          {link.shop_name}
          {link.price_krw != null ? ` · ${Number(link.price_krw).toLocaleString("ko-KR")}원` : ""}
        </a>
      ))}
    </div>
  );
}

function Row({ item, now }: { item: FeedItem; now: number }) {
  const display = feedDisplay(item.release, now);
  return (
    <li className="border-b border-neutral-200 py-4 dark:border-neutral-800">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="rounded bg-neutral-200 px-1.5 py-0.5 text-xs text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
          {display.status}
        </span>
        {item.release.is_limited && (
          <span className="rounded border border-amber-500 px-1.5 py-0.5 text-xs text-amber-600 dark:text-amber-400">
            한정반
          </span>
        )}
        {display.at ? (
          <time className="ml-auto text-xs text-neutral-500" dateTime={display.at}>
            {display.label} · {display.dateOnly ? formatDate(display.at) : formatDateTime(display.at)}
          </time>
        ) : <span className="ml-auto text-xs text-neutral-500">시작 일정 미정</span>}
      </div>

      <h2 className="mt-1.5 text-[15px] font-medium">
        <Link href={`/releases/${item.release.id}`} className="hover:underline">
          {releaseLabel(item.release)}
        </Link>
      </h2>

      {item.release.variant && (
        <p className="mt-0.5 text-xs text-neutral-500">{item.release.variant}</p>
      )}
      <ShopLinks item={item} />
    </li>
  );
}

export default async function FeedPage({ searchParams }: {
  searchParams: Promise<{ sort?: string | string[] }>;
}) {
  const params = await searchParams;
  const sort = params.sort === "recent" ? "recent" : "imminent";
  const feed = await getFeed(50, sort);
  const now = Date.parse(feed.generated_at);

  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">발매·예약 일정</h1>
      <p className="mt-1 text-sm text-neutral-500">
        예약 시작과 발매 일정을 확인하세요.{" "}
        <Link href="/subscribe" className="underline">캘린더·RSS 구독</Link>
      </p>
      <nav aria-label="피드 정렬" className="mt-5 flex gap-2">
        {([['recent', '최근 변경순'], ['imminent', '발매 임박순']] as const).map(([value, label]) => (
          <Link key={value} href={`/?sort=${value}`} aria-current={sort === value ? "true" : undefined}
            className={`rounded border px-3 py-1.5 text-sm ${sort === value
              ? "border-neutral-900 bg-neutral-900 text-white dark:border-neutral-100 dark:bg-neutral-100 dark:text-neutral-900"
              : "border-neutral-300 text-neutral-600 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"}`}>
            {label}
          </Link>
        ))}
      </nav>
      {feed.items.length === 0 ? (
        <p className="mt-10 text-center text-sm text-neutral-500">아직 등록된 일정이 없습니다.</p>
      ) : (
        <ul className="mt-2" aria-label="발매·예약 일정 목록">
          {feed.items.map((item) => <Row key={item.release.id} item={item} now={now} />)}
        </ul>
      )}
    </>
  );
}
