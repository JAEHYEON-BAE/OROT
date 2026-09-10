/**
 * 브라우저 → 웹서버 → API 프록시 (ADR-0007).
 *
 * 브라우저가 API 를 직접 부르면 CORS 허용 출처를 환경마다 관리해야 하고,
 * 목록이 어긋나면 **구독만 조용히 실패한다** — 나머지 화면은 서버 렌더라 멀쩡해서
 * 알아채기 어렵다. 같은 출처로 받아 서버가 대신 부르면 그 실패 경로가 사라진다.
 */

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

/** API 응답을 그대로 흘려보낸다. 상태 코드와 본문을 바꾸지 않는다. */
export async function forward(path: string, init: RequestInit = {}): Promise<Response> {
  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(10_000),
    });
    // Read under the same timeout, including when upstream stalls after headers.
    const body = upstream.status === 204 ? null : await upstream.text();
    const headers = new Headers({
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
      "Cache-Control": "no-store",
    });
    for (const name of ["Retry-After", "ETag"]) {
      const value = upstream.headers.get(name);
      if (value) headers.set(name, value);
    }
    return new Response(body, { status: upstream.status, headers });
  } catch {
    // API 가 죽었을 때 502 를 돌려준다. 여기서 던지면 Next 가 HTML 오류 페이지를
    // 내보내고, 클라이언트의 res.json() 이 파싱 오류로 바뀌어 원인을 가린다.
    return Response.json({ detail: "API 서버에 연결할 수 없습니다." }, { status: 502 });
  }
}
