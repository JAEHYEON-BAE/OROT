import Link from "next/link";
import { notFound } from "next/navigation";
import { apiBase, type Release } from "@/lib/api";
import { formatDate, formatDateTime, relativeFromNow, releaseLabel } from "@/lib/format";

export const dynamic = "force-dynamic";

async function getRelease(id: string): Promise<Release | null> {
  const res = await fetch(`${apiBase}/v1/releases/${id}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json() as Promise<Release>;
}

export default async function ReleasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const release = await getRelease(id);
  // 초안은 API 가 404 를 준다 — 여기서도 없는 것으로 다룬다.
  if (!release) notFound();

  const rows: [string, string][] = [];
  if (release.label) rows.push(["레이블", release.label]);
  if (release.variant) rows.push(["바리언트", release.variant]);
  if (release.preorder_opens_at)
    rows.push([
      "예약 시작",
      `${formatDateTime(release.preorder_opens_at)} · ${relativeFromNow(release.preorder_opens_at)}`,
    ]);
  if (release.preorder_closes_at)
    rows.push(["예약 마감", formatDateTime(release.preorder_closes_at)]);
  if (release.release_date) rows.push(["발매일", formatDate(release.release_date)]);

  return (
    <>
      <Link href="/" className="text-sm text-neutral-500 hover:underline">
        ← 목록
      </Link>

      <div className="mt-4 flex items-baseline gap-2">
        <h1 className="text-xl font-semibold tracking-tight">{releaseLabel(release)}</h1>
        {release.is_limited && (
          <span className="rounded border border-amber-500 px-1.5 py-0.5 text-xs text-amber-600 dark:text-amber-400">
            한정반
          </span>
        )}
      </div>

      {rows.length > 0 && (
        <dl className="mt-5 divide-y divide-neutral-200 text-sm dark:divide-neutral-800">
          {rows.map(([label, value]) => (
            <div key={label} className="flex gap-4 py-2">
              <dt className="w-24 shrink-0 text-neutral-500">{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {release.links.length > 0 && (
        <section className="mt-7">
          <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-500">구매처</h2>
          <ul className="mt-2 space-y-2">
            {release.links.map((link) => (
              <li key={link.id}>
                <a
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 rounded border border-neutral-200 px-3 py-2 text-sm hover:bg-neutral-50 dark:border-neutral-800 dark:hover:bg-neutral-900"
                >
                  <span>{link.shop_name}</span>
                  {link.price_krw && (
                    <span className="ml-auto tabular-nums">
                      {Number(link.price_krw).toLocaleString("ko-KR")}원
                    </span>
                  )}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
