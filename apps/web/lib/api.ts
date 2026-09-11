/**
 * API 클라이언트.
 *
 * 서버 컴포넌트에서 호출하므로 컨테이너 내부 주소(`http://api:8000`)를 쓴다.
 * 브라우저에서 직접 부르지 않으므로 CORS 설정이 필요 없다.
 */

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export type ReleaseLink = {
  id: number;
  shop_name: string;
  url: string;
  source_id: string | null;
  price_krw: number | null;
};

export type Release = {
  id: number;
  title: string;
  artist_name: string | null;
  label: string | null;
  format: string | null;
  variant: string | null;
  is_limited: boolean;
  release_date: string | null;
  preorder_opens_at: string | null;
  preorder_closes_at: string | null;
  cover_url: string | null;
  links: ReleaseLink[];
};

export type FeedItem = {
  kind: "UPCOMING" | "EVENT";
  at: string;
  event_type: string | null;
  release: Release;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    // **캐시하지 않는다.** "예약 시작을 놓치지 않게" 가 이 제품의 약속인데
    // 60초 캐시는 그 약속과 어긋난다 — 운영자가 방금 공개한 일정이 안 보이거나,
    // 이미 지난 예약이 "다가오는 예약"에 남는다.
    // 트래픽이 적고 응답이 작아 캐시로 얻을 것도 거의 없다.
    // API 쪽 ETag / Cache-Control 은 그대로 있으므로 CDN 계층에서는 여전히 캐시된다.
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

export function getFeed(limit = 50, sort: "recent" | "imminent" = "imminent") {
  return get<{ items: FeedItem[]; generated_at: string }>(`/v1/feed?limit=${limit}&sort=${sort}`);
}

export function getReleases(params: Record<string, string> = {}) {
  const query = new URLSearchParams({ limit: "100", ...params }).toString();
  return get<{ items: Release[]; next_cursor: string | null }>(`/v1/releases?${query}`);
}

export const apiBase = API_BASE;

/** Calendar must follow the cursor; a first-page limit silently hides later dates. */
export async function getAllReleases() {
  const items: Release[] = [];
  const seen = new Set<string>();
  let cursor: string | null = null;
  do {
    const page = await getReleases(cursor ? { cursor } : {});
    items.push(...page.items);
    cursor = page.next_cursor;
    if (cursor && seen.has(cursor)) throw new Error("반복된 페이지 커서입니다.");
    if (cursor) seen.add(cursor);
  } while (cursor);
  return { items };
}
