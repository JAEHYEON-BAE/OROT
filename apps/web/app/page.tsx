import Link from "next/link";
import { getFeed, type FeedItem } from "@/lib/api";
import { eventLabel, formatDateTime, relativeFromNow, releaseLabel } from "@/lib/format";

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
          {link.price_krw ? ` · ${Number(link.price_krw).toLocaleString("ko-KR")}원` : ""}
        </a>
      ))}
    </div>
  );
}

function Row({ item }: { item: FeedItem }) {
  const upcoming = item.kind === "UPCOMING";
  return (
    <li className="border-b border-neutral-200 py-4 dark:border-neutral-800">
      <div className="flex items-baseline gap-2">
        {upcoming ? (
          <span className="rounded bg-emerald-600 px-1.5 py-0.5 text-xs font-medium text-white">
            예약 시작
          </span>
        ) : (
          <span className="rounded bg-neutral-200 px-1.5 py-0.5 text-xs text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
            {eventLabel(item.event_type)}
          </span>
        )}
        {item.release.is_limited && (
          <span className="rounded border border-amber-500 px-1.5 py-0.5 text-xs text-amber-600 dark:text-amber-400">
            한정반
          </span>
        )}
        <time className="ml-auto text-xs text-neutral-500" dateTime={item.at}>
          {formatDateTime(item.at)}
          {upcoming && ` · ${relativeFromNow(item.at)}`}
        </time>
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

export default async function FeedPage() {
  const feed = await getFeed();
  const upcoming = feed.items.filter((i) => i.kind === "UPCOMING");
  const recent = feed.items.filter((i) => i.kind === "EVENT");

  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">발매·예약 일정</h1>
      <p className="mt-1 text-sm text-neutral-500">
        예약이 임박한 순으로 보여 줍니다.{" "}
        <a href="/subscribe" className="underline">
          캘린더·RSS 구독
        </a>
      </p>

      {feed.items.length === 0 ? (
        <p className="mt-10 text-center text-sm text-neutral-500">
          아직 등록된 일정이 없습니다.
        </p>
      ) : (
        <>
          {upcoming.length > 0 && (
            <section className="mt-6">
              <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                다가오는 예약
              </h2>
              <ul>
                {upcoming.map((item) => (
                  <Row key={`u-${item.release.id}`} item={item} />
                ))}
              </ul>
            </section>
          )}
          {recent.length > 0 && (
            <section className="mt-8">
              <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                최근 등록
              </h2>
              <ul>
                {recent.map((item, i) => (
                  <Row key={`e-${item.release.id}-${i}`} item={item} />
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </>
  );
}
