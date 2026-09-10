/** Bound anonymous writes before buffering or forwarding them to the API. */
const MAX_BODY_BYTES = 8192;
const BODY_TIMEOUT_MS = 5000;

export async function readPushBody(request: Request): Promise<string | Response> {
  // JSON is not a CORS-safelisted media type. Never turn a cross-site text/plain
  // form submission into an authenticated-looking same-origin JSON request.
  if (request.headers.get("sec-fetch-site") === "cross-site") {
    return Response.json({ detail: "다른 사이트의 요청은 허용하지 않습니다." }, { status: 403 });
  }
  const mediaType = request.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase();
  if (mediaType !== "application/json") {
    return Response.json({ detail: "application/json 요청이 필요합니다." }, { status: 415 });
  }
  const length = request.headers.get("content-length");
  if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_BODY_BYTES)) {
    return Response.json({ detail: "요청 본문이 너무 큽니다." }, { status: 413 });
  }
  const reader = request.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let size = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error("timeout")), BODY_TIMEOUT_MS);
  });
  try {
    while (true) {
      const { done, value } = await Promise.race([reader.read(), timeout]);
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BODY_BYTES) {
        void reader.cancel().catch(() => {});
        return Response.json({ detail: "요청 본문이 너무 큽니다." }, { status: 413 });
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch (error) {
    void reader.cancel().catch(() => {});
    const status = error instanceof Error && error.message === "timeout" ? 408 : 400;
    return Response.json({ detail: "요청 본문을 읽을 수 없습니다." }, { status });
  } finally {
    clearTimeout(timer);
  }
}
