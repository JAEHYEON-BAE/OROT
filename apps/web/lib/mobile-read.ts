/** Local implementation; production requires a separate web image deployment. */
export async function mobileRead(request: Request, resource: "feed" | "releases" | "detail", id?: string): Promise<Response> {
  const bad = () => Response.json({ detail: "잘못된 조회 요청입니다." }, { status: 400 });
  if (request.method !== "GET") return new Response(null, { status: 405 });
  if (resource === "detail" && (!id || !/^[1-9]\d{0,14}$/.test(id))) return bad();
  const input = new URL(request.url).searchParams;
  if (input.toString().length > 2048) return bad();
  const allowed = resource === "feed" ? ["limit", "sort"] : resource === "releases" ? ["limit", "cursor", "from", "to", "format", "is_limited"] : [];
  for (const key of input.keys()) if (!allowed.includes(key) || input.getAll(key).length !== 1) return bad();
  const limit = input.get("limit");
  if (limit !== null && (!/^\d{1,3}$/.test(limit) || Number(limit) < 1 || Number(limit) > 100)) return bad();
  if (resource === "feed" && input.has("sort") && !["recent", "imminent"].includes(input.get("sort")!)) return bad();
  if (input.has("is_limited") && !["true", "false"].includes(input.get("is_limited")!)) return bad();
  for (const key of ["from", "to"]) if (input.has(key) && !/^\d{4}-\d{2}-\d{2}$/.test(input.get(key)!)) return bad();
  const query = input.toString();
  const path = resource === "detail" ? `/v1/releases/${id}` : `/v1/${resource}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const upstream = await fetch(`${process.env.API_BASE_URL ?? "http://localhost:8000"}${path}${query ? `?${query}` : ""}`, {
      method: "GET", headers: { Accept: "application/json" }, cache: "no-store", redirect: "error", signal: controller.signal,
    });
    if (!upstream.headers.get("content-type")?.includes("application/json")) throw new Error("Unexpected response");
    const reader = upstream.body?.getReader(); if (!reader) throw new Error("Missing body");
    const chunks: Uint8Array[] = []; let size = 0;
    while (true) {
      const chunk = await reader.read(); if (chunk.done) break;
      size += chunk.value.length;
      if (size > 4 * 1024 * 1024) { await reader.cancel(); throw new Error("Response too large"); }
      chunks.push(chunk.value);
    }
    const body = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
    const headers = new Headers({ "Content-Type": "application/json", "Cache-Control": "no-store" });
    const retry = upstream.headers.get("retry-after"); if (retry) headers.set("Retry-After", retry);
    return new Response(body, { status: upstream.status, headers });
  } catch {
    return Response.json({ detail: "서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요." }, { status: 502, headers: { "Cache-Control": "no-store" } });
  } finally { clearTimeout(timeout); }
}
