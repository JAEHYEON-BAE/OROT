import Link from "next/link";
import { getReleases, type Release } from "@/lib/api";
import { releaseLabel } from "@/lib/format";

export const dynamic = "force-dynamic";

const KST = "Asia/Seoul";
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/** UTC 로 저장된 시각을 **KST 기준 날짜**로 바꾼다. 이걸 빠뜨리면 9시간 차이로 날짜가 밀린다. */
function kstDayKey(iso: string): string {
  return new Date(iso).toLocaleDateString("en-CA", { timeZone: KST });
}

type Marker = { release: Release; kind: "preorder" | "release" };

/** `YYYY-MM` 만 받아들인다. 형식이나 범위가 어긋나면 null. */
function parseMonth(month: string | undefined): Date | null {
  if (!month || !/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) return null;
  const parsed = new Date(`${month}-01T00:00:00+09:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export default async function CalendarPage({
  searchParams,
}: {
  searchParams: Promise<{ month?: string }>;
}) {
  const { month } = await searchParams;
  const today = new Date();
  // **쿼리 문자열은 인증 없이 누구나 넣는다.** 검증 없이 Date 에 넘기면 Invalid Date 가
  // 되고, 그 NaN 이 아래 Array 길이로 흘러 `RangeError` → 500 이 된다 (T-121).
  // 잘못된 값은 오류가 아니라 **이번 달**로 다룬다 — 링크를 잘못 눌렀을 뿐이다.
  const base = parseMonth(month) ?? today;
  const year = base.getFullYear();
  const monthIndex = base.getMonth();

  const { items } = await getReleases();

  // 하루에 여러 일정이 걸릴 수 있으므로 날짜별로 모은다.
  const byDay = new Map<string, Marker[]>();
  for (const release of items) {
    if (release.preorder_opens_at) {
      const key = kstDayKey(release.preorder_opens_at);
      byDay.set(key, [...(byDay.get(key) ?? []), { release, kind: "preorder" }]);
    }
    if (release.release_date) {
      const key = release.release_date;
      byDay.set(key, [...(byDay.get(key) ?? []), { release, kind: "release" }]);
    }
  }

  const first = new Date(year, monthIndex, 1);
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
  const leading = first.getDay();
  const cells: (number | null)[] = [
    ...Array<null>(leading).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const monthKey = (offset: number) => {
    const d = new Date(year, monthIndex + offset, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  };
  const todayKey = today.toLocaleDateString("en-CA", { timeZone: KST });

  return (
    <>
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight">
          {year}년 {monthIndex + 1}월
        </h1>
        <div className="ml-auto flex gap-2 text-sm">
          <Link href={`/calendar?month=${monthKey(-1)}`} className="text-neutral-500 hover:underline">
            ← 이전
          </Link>
          <Link href="/calendar" className="text-neutral-500 hover:underline">
            이번 달
          </Link>
          <Link href={`/calendar?month=${monthKey(1)}`} className="text-neutral-500 hover:underline">
            다음 →
          </Link>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-7 gap-px overflow-hidden rounded border border-neutral-200 bg-neutral-200 text-sm dark:border-neutral-800 dark:bg-neutral-800">
        {WEEKDAYS.map((w) => (
          <div
            key={w}
            className="bg-neutral-50 py-1.5 text-center text-xs font-medium text-neutral-500 dark:bg-neutral-900"
          >
            {w}
          </div>
        ))}
        {cells.map((day, i) => {
          const key = day
            ? `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`
            : null;
          const markers = key ? (byDay.get(key) ?? []) : [];
          const isToday = key === todayKey;
          return (
            <div
              key={i}
              className={`min-h-24 bg-white p-1.5 align-top dark:bg-neutral-950 ${
                day ? "" : "opacity-40"
              }`}
            >
              {day && (
                <div
                  className={`text-xs ${
                    isToday
                      ? "inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-600 font-medium text-white"
                      : "text-neutral-500"
                  }`}
                >
                  {day}
                </div>
              )}
              <ul className="mt-1 space-y-1">
                {markers.map((m, j) => (
                  <li key={j}>
                    <Link
                      href={`/releases/${m.release.id}`}
                      className={`block truncate rounded px-1 py-0.5 text-[11px] leading-tight ${
                        m.kind === "preorder"
                          ? "bg-emerald-600/10 text-emerald-700 dark:text-emerald-400"
                          : "bg-neutral-500/10 text-neutral-600 dark:text-neutral-400"
                      }`}
                      title={releaseLabel(m.release)}
                    >
                      {m.kind === "preorder" ? "예약 " : "발매 "}
                      {m.release.artist_name ?? m.release.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      <p className="mt-4 flex gap-4 text-xs text-neutral-500">
        <span>
          <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-emerald-600/60" />
          예약 시작
        </span>
        <span>
          <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-neutral-500/60" />
          발매일
        </span>
      </p>
    </>
  );
}
