import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function loadTS(path) {
  const source = await readFile(new URL(path, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}

const { readPushBody } = await loadTS("../lib/push-request.ts");
const { forward } = await loadTS("../lib/proxy.ts");
function request(body, headers = {}) {
  return new Request("https://test.example/api/push/subscribe", {
    method: "POST", body, duplex: "half",
    headers: { "content-type": "application/json", ...headers },
  });
}

test("normal JSON and service-worker requests remain supported", async () => {
  assert.equal(await readPushBody(request('{"endpoint":"test"}')), '{"endpoint":"test"}');
});
test("cross-site JSON and simple form requests are rejected", async () => {
  assert.equal((await readPushBody(request("{}", { "sec-fetch-site": "cross-site" }))).status, 403);
  assert.equal((await readPushBody(request("{}", { "content-type": "text/plain" }))).status, 415);
});
test("length header is checked before the stream is read", async () => {
  assert.equal((await readPushBody(request("{}", { "content-length": "9000" }))).status, 413);
});
test("chunked or falsely small content-length cannot bypass byte limit", async () => {
  for (const headers of [{}, { "content-length": "2" }]) {
    const stream = new ReadableStream({ start(controller) {
      controller.enqueue(new Uint8Array(4096));
      controller.enqueue(new Uint8Array(4097));
      controller.close();
    } });
    assert.equal((await readPushBody(request(stream, headers))).status, 413);
  }
});
test("byte limit counts multibyte text", async () => {
  assert.equal((await readPushBody(request("한".repeat(3000)))).status, 413);
});
test("slow body is timed out", async () => {
  const stream = new ReadableStream({ start() {} });
  assert.equal((await readPushBody(request(stream))).status, 408);
});
test("proxy preserves retry information and avoids caching capabilities", async (t) => {
  t.mock.method(globalThis, "fetch", async (_url, init) => {
    assert.equal(init.redirect, "error");
    assert.ok(init.signal instanceof AbortSignal);
    return new Response("busy", { status: 429, headers: { "Retry-After": "40", Server: "private" } });
  });
  const response = await forward("/v1/push/subscribe");
  assert.equal(response.status, 429);
  assert.equal(response.headers.get("retry-after"), "40");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("server"), null);
});
test("upstream body errors produce JSON 502", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(new ReadableStream({
    start(controller) { controller.error(new Error("internal connection details")); },
  })));
  const response = await forward("/v1/push/subscribe");
  assert.equal(response.status, 502);
  assert.ok(!(await response.text()).includes("internal connection details"));
});
