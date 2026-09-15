import type { components } from "./schema";
export type Release = components["schemas"]["ReleaseOut"];
export type FeedPage = components["schemas"]["FeedPage"];
export type FeedSort = "imminent" | "recent";
export const PUBLIC_SERVICE_URL =
  "https://jaehyeonui-macmini.tail598a5f.ts.net";
const configured =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? `${PUBLIC_SERVICE_URL}/api/mobile`;
const url = new URL(configured);
if (
  url.protocol !== "https:" ||
  url.username ||
  url.password ||
  url.search ||
  url.hash
)
  throw new Error("모바일 API는 올바른 HTTPS 주소가 필요합니다.");
const base = configured.replace(/\/$/, "");
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
const object = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
export function validRelease(v: unknown): v is Release {
  if (
    !object(v) ||
    !Number.isSafeInteger(v.id) ||
    (v.id as number) <= 0 ||
    typeof v.title !== "string" ||
    v.is_published !== true ||
    typeof v.is_limited !== "boolean" ||
    !["MANUAL", "CRAWLED"].includes(String(v.curation))
  )
    return false;
  if (v.schedule_status !== undefined && !["SCHEDULED", "TBA", "ON_SALE"].includes(String(v.schedule_status))) return false;
  if (v.until_sold_out !== undefined && typeof v.until_sold_out !== "boolean") return false;
  for (const key of [
    "artist_name",
    "label",
    "format",
    "variant",
    "release_date",
    "preorder_opens_at",
    "preorder_closes_at",
    "cover_url",
  ])
    if (v[key] != null && typeof v[key] !== "string") return false;
  for (const key of ["release_date", "preorder_opens_at", "preorder_closes_at"])
    if (v[key] && !Number.isFinite(Date.parse(v[key] as string))) return false;
  return (
    Array.isArray(v.links) &&
    v.links.every(
      (link) =>
        object(link) &&
        Number.isSafeInteger(link.id) &&
        typeof link.shop_name === "string" &&
        typeof link.url === "string" &&
        (link.price_krw == null ||
          (Number.isSafeInteger(link.price_krw) &&
            (link.price_krw as number) >= 0)),
    )
  );
}
function validFeed(v: unknown): v is FeedPage {
  return (
    object(v) &&
    typeof v.generated_at === "string" &&
    Array.isArray(v.items) &&
    v.items.every(
      (item) =>
        object(item) &&
        ["UPCOMING", "EVENT"].includes(String(item.kind)) &&
        typeof item.at === "string" &&
        validRelease(item.release),
    )
  );
}
async function get<T>(
  path: string,
  valid: (value: unknown) => value is T,
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort);
  if (signal?.aborted) controller.abort();
  const timer = setTimeout(abort, 12_000);
  try {
    const response = await fetch(`${base}${path}`, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok)
      throw new ApiError(
        response.status,
        response.status === 404
          ? "일정을 찾을 수 없습니다."
          : response.status === 429
            ? "요청이 많습니다. 잠시 후 다시 시도해주세요."
            : "일정을 불러오지 못했습니다. 다시 시도해주세요.",
      );
    if (!response.headers.get("content-type")?.includes("application/json"))
      throw new ApiError(0, "서버 응답을 확인할 수 없습니다.");
    const data: unknown = await response.json();
    if (!valid(data))
      throw new ApiError(0, "일정 정보의 형식이 올바르지 않습니다.");
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      0,
      "서버에 연결할 수 없습니다. 네트워크를 확인하고 다시 시도해주세요.",
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}
export const getFeed = (sort: FeedSort, signal?: AbortSignal) =>
  get(`/v1/feed?limit=100&sort=${sort}`, validFeed, signal);
export function getRelease(id: string, signal?: AbortSignal) {
  if (!/^[1-9]\d{0,14}$/.test(id))
    return Promise.reject(new ApiError(404, "일정을 찾을 수 없습니다."));
  return get(`/v1/releases/${id}`, validRelease, signal);
}
export function sellerUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}
